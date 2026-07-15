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
import subprocess
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

    Notes:
        CoreGraphics returns raw pixel data with per-row padding (bytes_per_row >= width * 4).
        Each row is aligned to a 16-byte boundary so that SIMD-friendly loads work correctly.
        We must account for this padding when converting the flat byte buffer into an image array,
        otherwise rows will be misaligned and pixels will be garbled. The alpha channel in CG data
        is stored last (RGBA or premultiplied BGRA), so we strip it and reorder channels to RGB.
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

    # Validate bytes_per_row is consistent with expected row size (width * 4 for RGBA).
    if bytes_per_row < width * 4:
        logger.debug("bytes_per_row %d < width*4=%d; refusing to interpret as valid CG data.", bytes_per_row, width * 4)
        return None

    try:
        # Extract raw pixel bytes from CGDataProvider via ctypes.
        # cg_data is a pyobjc NSData object — get pointer and length without going through Python bytes.
        import ctypes
        cf = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))
        fn_GetPtr = getattr(cf, "CFDataGetBytePtr", None)
        fn_GetLength = getattr(cf, "CFDataGetLength", None)

        if not (fn_GetPtr and fn_GetLength):
            logger.debug("CoreFoundation CFData functions unavailable; falling back to screencapture.")
            return None

        ptr_val = int(fn_GetPtr(cg_data))
        length_val = int(fn_GetLength(cg_data))

        if not ptr_val or length_val == 0:
            return None

        # Copy the raw bytes into a numpy uint8 array (the CG data pointer is read-only; we need
        # a mutable contiguous copy for safe reshape/slicing).
        raw = np.ctypeslib.as_array(
            ctypes.cast(ptr_val, ctypes.POINTER(ctypes.c_uint8)), shape=(length_val,)
        ).copy()

        if len(raw) != height * bytes_per_row:
            logger.debug(
                "CG data length mismatch: got %d bytes, expected %d (height=%d * bytes_per_row=%d).",
                len(raw), height * bytes_per_row, height, bytes_per_row,
            )
            return None

        # Reshape into a 2D array: (height, bytes_per_row) — this includes padding bytes at the end of each row.
        frame = raw.reshape(height, bytes_per_row)

        # Slice out only the pixel columns and drop alpha channel.
        # CGWindowListCreateImage returns kCGWindowImageDefault format which is RGBA with alpha last.
        pixels = frame[:, : width * 4]            # (H, W*4) — drop padding bytes from each row
        rgba = pixels.reshape(height, width, 4)    # (H, W, 4)

        rgb_array = np.empty((height, width, 3), dtype=np.uint8)
        rgb_array[:, :, 0] = rgba[:, :, 2]         # Blue → R channel
        rgb_array[:, :, 1] = rgba[:, :, 1]         # Green stays Green
        rgb_array[:, :, 2] = rgba[:, :, 0]         # Red → B channel (RGBA order: R, G, B, A)

        return Image.frombuffer("RGB", (width, height), rgb_array.tobytes(), "raw", "RGB", 0, 1)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Pixel conversion from CG data failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Internal screencapture CLI fallback helper
# ---------------------------------------------------------------------------


def _capture_one_screencapture(
    region: Optional[Tuple[int, int, int, int]] = None,
    timeout: float = 2.0,
) -> Optional[Image.Image]:
    """Capture a single frame using the ``screencapture`` CLI (from ``screen.py``).

    This is the fallback path when CG capture is unavailable. It invokes
    :func:`src.virtual_hid.screen.capture_screen` and returns the raw PIL image on success.

    Args:
        region: Optional ``(x, y, width, height)`` rectangle to capture.
        timeout: Maximum seconds to wait for screencapture subprocess (prevents hanging).

    Returns:
        A PIL ``Image.Image`` in RGB mode on success, or ``None`` if screencapture fails/times out.
    """
    try:
        from .screen import capture_screen, ScreenCaptureError
        result = capture_screen(region=region)
        if result is not None and result.image is not None:
            return result.image
        logger.debug("screencapture returned empty or None result.")
        return None
    except (ScreenCaptureError, PermissionError, OSError, subprocess.SubprocessError) as exc:  # pragma: no cover — defensive
        logger.warning(
            "LiveDisplayFeed screencapture failed (accessibility/permission/subprocess error): %s",
            exc,
        )
        return None
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("Unexpected exception during screencapture fallback: %s", exc)
        return None


def _capture_one_cg_with_timeout(
    region: Optional[Tuple[int, int, int, int]] = None,
    timeout: float = 1.0,
) -> Optional[Image.Image]:
    """Wrapper around ``_capture_one_cg`` with a hard timeout to prevent hanging.

    CGWindowListCreateImage via pyobjc should be fast but can occasionally block on
    system resources (e.g., when display is locked or permission denied). This wrapper
    ensures we never hang more than ``timeout`` seconds per frame capture attempt.

    Args:
        region: Optional ``(x, y, width, height)`` rectangle to capture.
        timeout: Maximum seconds to wait for CG capture (default 1s).

    Returns:
        A PIL ``Image.Image`` in RGB mode on success, or ``None`` if CG capture fails/times out.
    """
    result = [None]
    error = [None]

    def target():
        try:
            result[0] = _capture_one_cg(region)
        except Exception as exc:
            error[0] = str(exc)

    t = threading.Thread(target=target); t.daemon = True; t.start()
    t.join(timeout)
    if t.is_alive():
        logger.debug("CG capture timed out after %.1fs", timeout)
        return None
    if error[0]:
        logger.debug("CG capture failed: %s", error[0])
        return None
    return result[0]


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
