#!/usr/bin/env python3
"""
Live Display Feed — continuous screen capture module.

Provides a background capture loop that grabs frames at configurable FPS using the fast
CoreGraphics `CGWindowListCreateImage` API (pyobjc Quartz bindings). Frames are stored in a
double-buffered lock so consumer threads (OCR, UI analysis, display) can read the latest frame
without blocking the producer thread.

If CG capture is unavailable or fails, the feed falls back to the screencapture CLI from
``screen.py``.

Usage:
    feed = get_live_feed(fps=15, region=(0, 0, 640, 480))
    feed.start()
    try:
        while True:
            frame = feed.get_frame()
            if frame is None: continue
            # process frame …
    finally:
        feed.stop()

Requires macOS with pyobjc (``Quartz`` module) and ``numpy``.
"""

from __future__ import annotations

import logging
import time as _time
import threading
from dataclasses import dataclass, asdict
from typing import Optional, Tuple

# ``numpy`` is only required for the CG pixel-conversion path; import lazily so that
# importing this module (e.g., in tests or non-macOS environments) does not fail when numpy
# is absent. The screencapture CLI fallback works with pure-PIL decoding and needs no numpy.
try:
    import numpy as np  # noqa: F401 — referenced inside _capture_one_cg via the local name
except ImportError:
    np = None  # type: ignore[assignment]

from PIL import Image


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LiveFeedError(RuntimeError):
    """Raised when the live display feed encounters a recoverable failure."""


# ---------------------------------------------------------------------------
# FeedStats — lightweight stats tracked by the capture loop
# ---------------------------------------------------------------------------


@dataclass
class FeedStats:
    """Statistics about the current live feed state.

    Attributes:
        frames_captured: Total frames successfully captured since ``start()`` was called.
        frames_dropped:  Frames that were skipped (capture failed or thread stopped mid-loop).
        last_frame_time: Unix timestamp of the most recent successful frame capture.
        method:          Capture method currently in use — ``"cgwindow_loop"`` or
                         ``"screencapture_cli"``.
    """

    frames_captured: int = 0
    frames_dropped: int = 0
    last_frame_time: float = 0.0
    method: str = "unknown"


# ---------------------------------------------------------------------------
# Internal CG capture helper (pyobjc Quartz)
# ---------------------------------------------------------------------------


def _capture_one_cg(region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Image.Image]:
    """Capture a single frame using CoreGraphics ``CGWindowListCreateImage`` via pyobjc.

    Args:
        region: Optional ``(x, y, width, height)`` rectangle to capture. If ``None``, captures the
                full composite desktop.

    Returns:
        A PIL ``Image.Image`` in RGB mode on success, or ``None`` if CG capture fails for any reason.
    """
    if np is None:
        logger.debug(
            "numpy not installed — CG pixel conversion path unavailable. "
            "Install numpy (``pip install -r requirements.txt``) for fast CG capture."
        )
        return None

    try:
        from Quartz import (
            CGWindowListCreateImage,
            CGRectMake,
            kCGWindowListOptionAll,
            kCGWindowListExcludeDesktopElements,
            kCGWindowImageDefault,
            kCGNullWindowID,
            CGImageGetDataProvider,
            CGDataProviderCopyData,
            CGImageGetWidth,
            CGImageGetHeight,
            CGImageGetBytesPerRow,
        )
    except ImportError as exc:
        logger.debug("Quartz module unavailable for CG capture: %s", exc)
        return None

    try:
        if region is not None:
            x, y, w, h = region
            rect = CGRectMake(x, y, w, h)
        else:
            rect = None

        options = kCGWindowListOptionAll | kCGWindowListExcludeDesktopElements
        cg_image = CGWindowListCreateImage(rect, options, kCGNullWindowID, kCGWindowImageDefault)
    except Exception as exc:  # pragma: no cover — defensive, CG calls can raise ObjC errors
        logger.debug("CGWindowListCreateImage call failed: %s", exc)
        return None

    if cg_image is None:
        return None

    try:
        provider = CGImageGetDataProvider(cg_image)
        cg_data = CGDataProviderCopyData(provider)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("CGDataProviderCopyData failed: %s", exc)
        return None

    if not cg_data:
        return None

    try:
        width = int(CGImageGetWidth(cg_image))
        height = int(CGImageGetHeight(cg_image))
        bytes_per_row = int(CGImageGetBytesPerRow(cg_image))
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("CG image dimension query failed: %s", exc)
        return None

    if width <= 0 or height <= 0:
        logger.warning(
            "CG capture returned zero-size image (%dx%d); skipping.", width, height
        )
        return None

    try:
        raw = np.frombuffer(bytes(cg_data), dtype=np.uint8)
        # CG returns data in BGRA/BGRX layout — strides are row-major with padding.
        array = np.lib.stride_tricks.as_strided(
            raw,
            shape=(height, width, 4),
            strides=(bytes_per_row, 4, 1),
            writeable=False,
        )

        # Drop the alpha channel and convert BGRX → RGB.
        bgr = array[:, :, :3]                    # (H, W, 3) in BGR order
        rgb = np.ascontiguousarray(bgr[:, :, ::-1], dtype=np.uint8)

        return Image.frombuffer("RGB", (width, height), rgb.tobytes(), "raw", "RGB", 0, 1)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Pixel conversion from CG data failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Internal screencapture CLI fallback helper
# ---------------------------------------------------------------------------


def _capture_one_screencapture(
    region: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Image.Image]:
    """Capture a single frame using the ``screencapture`` CLI (from ``screen.py``).

    This is the fallback path when CG capture is unavailable. It invokes
    :func:`src.virtual_hid.screen.capture_screen` and returns the raw PIL image on success.

    Args:
        region: Optional ``(x, y, width, height)`` rectangle to capture.

    Returns:
        A PIL ``Image.Image`` in RGB mode on success, or ``None`` if screencapture fails.
    """
    try:
        from .screen import capture_screen
        result = capture_screen(region=region)
        return result.image
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("screencapture fallback failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# LiveDisplayFeed — the main capture loop class
# ---------------------------------------------------------------------------


class LiveDisplayFeed:
    """Continuous background screen-capture feed.

    Runs a daemon thread that captures frames at ``fps`` using CoreGraphics (primary path),
    falling back to ``screencapture`` CLI on failure. The latest frame is double-buffered in a
    lock so consumer threads can read it safely without blocking the producer.

    Args:
        fps: Target frames per second for the capture loop (default 15). Must be > 0.
        max_queue_depth: Reserved parameter kept for API compatibility with future queue-based
            buffering. Currently unused — only the latest frame is retained.
        region: Optional ``(x, y, width, height)`` rectangle to capture. When set, CG captures
            a smaller area which yields higher effective FPS on Apple Silicon.

    Raises:
        LiveFeedError: If ``fps`` is not positive or if initial frame capture fails completely.
    """

    def __init__(
        self,
        fps: float = 15,
        max_queue_depth: int = 3,
        region: Optional[Tuple[int, int, int, int]] = None,
    ) -> None:
        if fps <= 0:
            raise LiveFeedError(f"fps must be positive; got {fps}")

        self._fps = float(fps)
        self._max_queue_depth = max_queue_depth
        self._region = region

        # Lock-protected shared state
        self._lock = threading.Lock()
        self._latest_frame: Optional[Image.Image] = None
        self._stats = FeedStats()

        # Shutdown control — set via Event so the daemon thread can be interrupted mid-sleep.
        self._stop_event = threading.Event()

        # Background capture thread (daemon = won't block process exit)
        self._thread: Optional[threading.Thread] = None

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def start(self) -> None:
        """Start the background capture thread.

        If a feed is already running, this is a no-op (prevents duplicate threads).
        Performs an initial frame grab to verify that at least one capture method works; if both
        CG and screencapture fail immediately, raises ``LiveFeedError`` so callers can detect
        configuration problems early.
        """
        if self._thread is not None and self.is_running:
            logger.debug("LiveDisplayFeed already running — ignoring start() call.")
            return

        # Quick probe: try CG first, then screencapture fallback.
        frame = _capture_one_cg(self._region) or _capture_one_screencapture(self._region)
        if frame is None:
            raise LiveFeedError(
                "LiveDisplayFeed: initial capture probe failed — both CG and screencapture "
                "paths returned no frames. Check Accessibility permissions."
            )

        # Store the probed frame as the first available frame so consumers don't see a stale empty state.
        with self._lock:
            self._latest_frame = frame
            self._stats.frames_captured = 1
            self._stats.last_frame_time = _time.time()
            self._stats.method = "cgwindow_loop" if _capture_one_cg(self._region) is not None else "screencapture_cli"

        # Spawn the daemon capture thread.
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_capture_loop,
            name="LiveDisplayFeed-Capture",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "LiveDisplayFeed started at %.1f FPS%s.",
            self._fps,
            f" region={self._region}" if self._region else "",
        )

    def stop(self) -> None:
        """Stop the background capture thread and wait for it to exit.

        This sets the shutdown event, joins the daemon thread (with a short timeout), then clears
        the reference so ``start()`` can be called again cleanly.
        """
        if self._thread is None or not self.is_running:
            logger.debug("LiveDisplayFeed.stop(): no running capture thread.")
            return

        self._stop_event.set()

        # Give the thread up to 5 seconds to finish; beyond that, just detach and move on.
        deadline = _time.monotonic() + 5.0
        while _time.monotonic() < deadline and self._thread.is_alive():
            self._thread.join(timeout=0.1)

        if self._thread.is_alive():
            logger.warning("LiveDisplayFeed: capture thread did not exit within timeout; detaching.")
        else:
            logger.info("LiveDisplayFeed stopped cleanly.")

        self._thread = None

    def __del__(self) -> None:
        """Best-effort cleanup — stop the feed if it is still running."""
        try:
            if hasattr(self, "_stop_event"):
                self.stop()
        except Exception:  # pragma: no cover — __del__ must not raise
            pass

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the capture thread is currently alive."""
        return self._thread is not None and self._thread.is_alive()

    # -----------------------------------------------------------------------
    # Frame access — thread-safe
    # -----------------------------------------------------------------------

    def get_frame(self) -> Optional[Image.Image]:
        """Return a copy of the latest captured frame.

        Safe to call from any consumer thread (OCR, UI analysis, display). The returned image is
        always a fresh copy so callers can mutate or close it without affecting the feed.

        Returns:
            A PIL ``Image.Image`` in RGB mode on success, or ``None`` if no frame has been captured
            yet (e.g., before ``start()`` returns from its initial probe).
        """
        with self._lock:
            img = self._latest_frame
        if img is None:
            return None
        # Always return a copy so consumers can safely mutate or close the image.
        return img.copy()

    def get_stats(self) -> FeedStats:
        """Return a snapshot of current feed statistics.

        The returned :class:`FeedStats` object is a copy — mutating it does not affect internal state.
        """
        with self._lock:
            return FeedStats(**asdict(self._stats))

    # -----------------------------------------------------------------------
    # Internal capture loop (runs in daemon thread)
    # -----------------------------------------------------------------------

    def _run_capture_loop(self) -> None:
        """Background loop that captures frames at the target FPS.

        Each iteration:
          1. Computes the sleep interval to hit ``self._fps``.
          2. Attempts CG capture; falls back to screencapture CLI on failure.
          3. Stores the latest frame in the double-buffered lock and increments stats.
          4. Sleeps for the remaining cycle time (interruptible via ``_stop_event``).
        """
        interval = 1.0 / max(self._fps, 1e-9)

        while not self._stop_event.is_set():
            t0 = _time.perf_counter()

            # Primary path: CG capture
            img = _capture_one_cg(self._region)

            if img is None:
                logger.debug("CG capture failed; trying screencapture fallback.")
                # Fallback path: screencapture CLI
                img = _capture_one_screencapture(self._region)
                if self._stats.method == "cgwindow_loop":
                    self._stats.method = "screencapture_cli"

            if img is None:
                logger.warning("LiveDisplayFeed: frame capture failed (both paths).")
                with self._lock:
                    self._stats.frames_dropped += 1
                _time.sleep(interval)
                continue

            # Store the new frame under lock (non-blocking — acquire/release is fast).
            with self._lock:
                self._latest_frame = img
                self._stats.frames_captured += 1
                self._stats.last_frame_time = _time.time()

            # Pace the loop to hit target FPS.
            elapsed = _time.perf_counter() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                # Use ``wait`` with a timeout so we can respond to shutdown events promptly.
                self._stop_event.wait(timeout=sleep_time)

        logger.debug("LiveDisplayFeed capture loop exited cleanly.")


# ---------------------------------------------------------------------------
# Cached factory — returns the same feed instance for identical (fps, region) params
# ---------------------------------------------------------------------------


_FEED_CACHE: dict = {}
_FEED_LOCK = threading.Lock()


def get_live_feed(
    fps: float = 15,
    region: Optional[Tuple[int, int, int, int]] = None,
) -> LiveDisplayFeed:
    """Return a cached :class:`LiveDisplayFeed` instance for the given parameters.

    Multiple calls with identical ``(fps, region)`` return the same object — useful when many
    consumer threads need to share one feed without each starting their own capture loop.

    Args:
        fps: Target frames per second (default 15).
        region: Optional ``(x, y, width, height)`` rectangle to capture.

    Returns:
        A ``LiveDisplayFeed`` instance that has already been started via ``start()``. Callers
        should call ``stop()`` when done (typically in a ``finally`` block or via ``__del__``).
    """
    key = (fps, region)
    with _FEED_LOCK:
        feed = _FEED_CACHE.get(key)
        if feed is not None and feed.is_running:
            return feed

        # Create a fresh instance and start it.
        new_feed = LiveDisplayFeed(fps=fps, region=region)
        try:
            new_feed.start()
        except LiveFeedError as exc:
            logger.error("Failed to start LiveDisplayFeed: %s", exc)
            raise

        _FEED_CACHE[key] = new_feed
        return new_feed


def invalidate_cache() -> None:
    """Remove all cached feeds. Useful for testing or when params change mid-run."""
    with _FEED_LOCK:
        keys = list(_FEED_CACHE.keys())
        for key in keys:
            feed = _FEED_CACHE.pop(key)
            try:
                feed.stop()
            except Exception as exc:  # pragma: no cover — defensive cleanup
                logger.debug("Error stopping cached feed during invalidation: %s", exc)
