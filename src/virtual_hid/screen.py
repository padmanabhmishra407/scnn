#!/usr/bin/env python3
"""
Screen capture module for Vision/UI Reading capability (Phase 2).

Primary path:   macOS `screencapture` CLI — zero external deps, handles multi-monitor natively.
Fallback path: CGWindowListCreateImage via ctypes — for window-specific captures when screencapture
               cannot reach the target window (e.g., restricted apps).

All public functions return PIL.Image objects in RGB mode for compatibility with OCR/visualization
pipelines and raise ScreenCaptureError on unrecoverable failures rather than crashing.

Usage:
    from src.virtual_hid.screen import capture_screen, capture_window, capture_region, list_screens
    img = capture_screen()            # full desktop (all monitors composited)
    img = capture_region(0, 0, 1920, 1080)   # specific viewport region
    windows = list_screens()          # enumerate connected displays

Requirements:
    - macOS only (uses screencapture CLI and CoreGraphics framework).
    - Accessibility permission is required for window-region captures (-W / -l flags).
      Full-screen capture works without it.
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
import os
from contextlib import suppress
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Tuple

from PIL import Image


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ScreenCaptureError(RuntimeError):
    """Raised when screen capture fails in a recoverable way.

    Callers should catch this and decide whether to fall back or report the issue.
    """


# ---------------------------------------------------------------------------
# Data classes for structured results
# ---------------------------------------------------------------------------


@dataclass
class DisplayInfo:
    """Metadata about a connected display."""

    id: int
    name: str
    bounds: Tuple[int, int, int, int]  # (x, y, width, height)
    is_primary: bool = False
    builtin: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CaptureResult:
    """Structured result from any capture operation."""

    image: Image.Image          # PIL.Image in RGB mode
    method: str                 # "screencapture" | "ctypes_cgwindow" | "fallback_crop"
    source: Optional[str]       # human-readable description of what was captured

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["image"] = (
            f"<PIL.Image size={self.image.size} mode={self.image.mode}>"
        )
        return d


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _run_screencapture(*args: str, timeout: float = 10.0) -> Tuple[bytes, Optional[str]]:
    """Invoke `screencapture` and return (png_bytes, stderr_or_None).

    Writes the screenshot to a temporary file (screencapture expects an output path), then reads
    the PNG bytes back from disk. This avoids the "no file specified" error on macOS versions
    that do not route raw captures through stdout automatically.
    """
    # Pick a temp path inside /tmp so we never clobber user files and can unlink safely.
    tmp = tempfile.NamedTemporaryFile(prefix="scnn_screenshot_", suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()  # we want screencapture to own the file

    cmd = ["screencapture"] + list(args) + [tmp_path]  # output to temp file
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError:
        with suppress(OSError): os.unlink(tmp_path)
        return b"", "screencapture command not found"
    except subprocess.TimeoutExpired:
        with suppress(OSError): os.unlink(tmp_path)
        return b"", f"screencapture timed out after {timeout}s"

    if proc.returncode != 0:
        stderr = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        # Detect the common "accessibility permission denied" message
        if _is_accessibility_denied(stderr):
            logger.warning(
                "Screen capture blocked by Accessibility permissions. "
                "Open System Settings > Privacy & Security > Accessibility and grant Python."
            )
        with suppress(OSError): os.unlink(tmp_path)
        return b"", stderr or f"screencapture exited with code {proc.returncode}"

    try:
        png_bytes = open(tmp_path, "rb").read()
    except OSError as exc:
        with suppress(OSError): os.unlink(tmp_path)
        return b"", f"could not read temp screenshot: {exc}"
    finally:
        with suppress(OSError): os.unlink(tmp_path)

    if not png_bytes:
        return b"", "screencapture produced no output"

    return png_bytes, None


def _is_accessibility_denied(text: str) -> bool:
    """Heuristic to detect macOS accessibility permission errors in stderr."""
    denied_markers = [
        "accessibility",
        "permission denied",
        "not authorized",
        "screenshot blocked",
    ]
    lower = text.lower()
    return any(marker in lower for marker in denied_markers)


def _bytes_to_image(png_bytes: bytes, convert_rgb: bool = True) -> Image.Image:
    """Decode PNG bytes into a PIL Image.

    Always converts to RGB so downstream OCR/visualization code gets a uniform mode.
    """
    img = Image.open(_make_buffer(png_bytes))
    if convert_rgb and img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _make_buffer(data: bytes):
    """Return an object that PIL.Image.open() can read from."""
    # StringIO is for older PIL; BytesIO works on all supported versions.
    import io
    return io.BytesIO(data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def capture_screen(region: Optional[Tuple[int, int, int, int]] = None) -> CaptureResult:
    """Capture the full desktop (all monitors composited) or a specific region.

    Args:
        region: Optional (x, y, width, height) rectangle to capture. When provided, falls back to
                cropping from the full-screen capture so that window-specific accessibility is not
                required for small regions near the screen edge.

    Returns:
        CaptureResult with method "screencapture" on success or "fallback_crop" when a region was
        cropped from a full-screen capture.
    """
    # --- Path A: screencapture with -C (all screens) -------------------------
    args = ["-C"]  # composite all connected displays into one image

    if region is not None:
        x, y, w, h = region
        # screencapture's -l flag requires Accessibility permission; fall back to crop.
        png_bytes, err = _run_screencapture("-l", f"{x},{y},{w},{h}")
        if not png_bytes and err:
            logger.debug(
                "screencapture -l failed (%s); cropping from full-screen capture instead.", err
            )
            # Full screen capture without accessibility requirement
            png_bytes, err = _run_screencapture("-C")
            if not png_bytes and err:
                raise ScreenCaptureError(
                    f"capture_screen failed: {err}"
                ) from None

    if region is None:
        png_bytes, err = _run_screencapture()  # -C composite all screens
        if not png_bytes and err:
            raise ScreenCaptureError(f"capture_screen failed: {err}") from None

    try:
        img = _bytes_to_image(png_bytes)
    except Exception as exc:
        raise ScreenCaptureError(
            f"Failed to decode screencapture PNG output: {exc}"
        ) from exc

    if region is not None:
        # Crop the captured image to the requested rectangle.
        img = img.crop(region)
        method = "fallback_crop"
        source = (
            f"region ({region[0]}, {region[1]}, {region[2]}, {region[3]}) cropped from composite"
        )
    else:
        method = "screencapture"
        source = "full desktop (all monitors composited)"

    return CaptureResult(image=img, method=method, source=source)


def capture_window(window_id: int) -> Optional[CaptureResult]:
    """Capture a specific window by its CGWindowID.

    Args:
        window_id: The CoreGraphics window ID to capture (from list_windows / enumerate).

    Returns:
        CaptureResult on success, or None if the window could not be captured (e.g., restricted
        process, accessibility denied).
    """
    # Path A: screencapture -W <window-id>  (requires Accessibility)
    png_bytes, err = _run_screencapture("-W", str(window_id))
    if png_bytes:
        try:
            img = _bytes_to_image(png_bytes)
        except Exception as exc:
            logger.warning("Failed to decode window %d capture: %s", window_id, exc)
            return None
        return CaptureResult(
            image=img, method="screencapture", source=f"window id={window_id}"
        )

    if err and _is_accessibility_denied(err):
        logger.warning(
            "Window capture denied by Accessibility permissions. "
            "Grant Python access in System Settings > Privacy & Security > Accessibility."
        )
        return None

    # Path B: ctypes fallback via CGWindowListCreateImage
    result = _capture_window_ctypes(window_id)
    if result is not None:
        return CaptureResult(
            image=result, method="ctypes_cgwindow", source=f"window id={window_id}"
        )

    logger.debug("Could not capture window %d (not found or restricted)", window_id)
    return None


def _capture_window_ctypes(window_id: int) -> Optional[Image.Image]:
    """Attempt to capture a window via CoreGraphics ctypes.

    This path does NOT require Accessibility permissions for the window list query, but it may
    fail for windows belonging to sandboxed processes (e.g., Chrome tabs).
    """
    try:
        import ctypes
        import ctypes.util
    except ImportError:
        return None

    # Load CoreGraphics + CoreFoundation at runtime so imports stay lazy.
    cg_path = ctypes.util.find_library("CoreGraphics")
    cf_path = ctypes.util.find_library("CoreFoundation")
    if not cg_path or not cf_path:
        logger.debug("CoreGraphics/CoreFoundation frameworks unavailable for window capture.")
        return None

    cg = ctypes.CDLL(cg_path)
    cf = ctypes.CDLL(cf_path)

    # CFNumberRef CFNumberCreate(CFAllocatorRef, CFOptionFlags, const void*)
    fn_CFN_Create = getattr(cf, "CFNumberCreate")
    fn_CFN_Create.restype = ctypes.c_void_p
    fn_CFN_Create.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]

    # CFDataRef CGWindowListCreateImage(
    #     CGWindowID windowId, CGWindowListOption options, CGRect screenBounds, CGWindowImageOption imageOptions)
    fn_CGWI_Create = getattr(cg, "CGWindowListCreateImage")
    fn_CGWI_Create.restype = ctypes.c_void_p  # CFDataRef / nil on failure

    class _CGRect(ctypes.Structure):
        _fields_ = [
            ("origin_x", ctypes.c_double),
            ("origin_y", ctypes.c_double),
            ("size_w", ctypes.c_double),
            ("size_h", ctypes.c_double),
        ]

    fn_CGWI_Create.argtypes = [
        ctypes.c_uint32,              # windowId (CGWindowID)
        ctypes.c_int32,               # options (kCGWindowListOptionAll | kCGWindowListExcludeDesktopElements)
        ctypes.POINTER(_CGRect),      # screenBounds (CGRect pointer)
        ctypes.c_int32,               # imageOptions (kCGWindowImageDefault = 0)
    ]

    try:
        options = 0x208  # kCGWindowListOptionAll | kCGWindowListExcludeDesktopElements
        image_option = 0  # kCGWindowImageDefault

        rect = _CGRect(origin_x=0.0, origin_y=0.0, size_w=0.0, size_h=0.0)
        data_ref = fn_CGWI_Create(window_id, options, ctypes.byref(rect), image_option)
    except (AttributeError, OSError) as exc:
        logger.debug("ctypes CGWindowListCreateImage call failed: %s", exc)
        return None

    if not data_ref:
        # Window may belong to a restricted process — not an error per se.
        return None

    # Decode the CFDataRef into raw bytes and convert to PNG via PIL
    try:
        fn_CFRelease = getattr(cf, "CFRelease")
        fn_CFRelease.argtypes = [ctypes.c_void_p]
        fn_CFRelease.restype = None

        fn_CFGetPtr = getattr(cf, "CFDataGetBytePtr")
        fn_CFGetPtr.restype = ctypes.c_char_p
        fn_CFGetPtr.argtypes = [ctypes.c_void_p]
        fn_CFGetLength = getattr(cf, "CFDataGetLength")
        fn_CFGetLength.restype = ctypes.c_size_t
        fn_CFGetLength.argtypes = [ctypes.c_void_p]

        ptr_val = fn_CFGetPtr(data_ref)
        length_val = fn_CFGetLength(data_ref)
        if not ptr_val or length_val == 0:
            return None

        raw_bytes = bytes(ctypes.cast(ptr_val, ctypes.POINTER(ctypes.c_uint8 * length_val)).contents)

        # CFRelease the data ref
        fn_CFRelease(data_ref)
    except (AttributeError, OSError) as exc:
        logger.debug("ctypes failed to extract CFDataRef bytes: %s", exc)
        return None

    try:
        img = _bytes_to_image(raw_bytes)
        # If the capture produced an RGBA image with alpha, keep it; otherwise RGB is fine.
        if img.mode != "RGBA":
            img = img.convert("RGB")
        return img
    except Exception as exc:
        logger.debug("Failed to decode ctypes window capture bytes: %s", exc)
        return None


def capture_region(x: int, y: int, width: int, height: int) -> CaptureResult:
    """Capture a rectangular region of the screen.

    Args:
        x, y: Top-left corner in global display coordinates.
        width, height: Region dimensions in pixels.

    Returns:
        CaptureResult with method "screencapture" (if Accessibility was granted) or
        "fallback_crop" (cropped from full-screen capture when screencapture -l failed).
    """
    region = (x, y, width, height)
    return capture_screen(region=region)


def list_screens() -> List[DisplayInfo]:
    """Enumerate all connected displays and their bounds.

    Uses CoreGraphics CGGetActiveDisplayList / CGDisplayBounds APIs via ctypes for accurate,
    permission-free display enumeration. Falls back to system_profiler parsing or a single-display
    default if the CG API is unavailable (e.g., on non-macOS platforms).

    Returns:
        List of DisplayInfo objects describing each display. Empty list only on unrecoverable
        framework failures; otherwise returns at least one entry for the main/built-in display.
    """
    # Path A: CoreGraphics CGGetActiveDisplayList (most reliable, no Accessibility needed)
    displays = _enumerate_displays_cg()
    if displays:
        return displays

    # Path B: parse system_profiler SPDisplaysDataType output as a heuristic fallback
    displays = _enumerate_displays_system_profiler()
    if displays:
        return displays

    # Path C: single-display default (covers CI / non-macOS environments)
    return [DisplayInfo(id=0, name="Built-in Retina Display", bounds=(0, 0, 1440, 900))]


def _enumerate_displays_cg() -> List[DisplayInfo]:
    """Enumerate displays via CoreGraphics CG API (CGGetActiveDisplayList / CGDisplayBounds).

    Returns empty list if CoreGraphics framework cannot be loaded or APIs are missing.
    """
    try:
        import ctypes
        import ctypes.util
    except ImportError:
        return []

    cg_path = ctypes.util.find_library("CoreGraphics")
    if not cg_path:
        return []

    try:
        cg = ctypes.CDLL(cg_path)
    except OSError:
        return []

    # CGError CGGetActiveDisplayList(uint32_t maxDisps, CGDirectDisplayID *displays, uint32_t *outCount)
    fn_GetActive = getattr(cg, "CGGetActiveDisplayList", None)
    if not fn_GetActive:
        return []
    MAX_DISPS = 16
    display_ids = (ctypes.c_uint32 * MAX_DISPS)()
    out_count = ctypes.c_uint32(0)
    fn_GetActive.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32)]
    fn_GetActive.restype = ctypes.c_int32

    err = fn_GetActive(MAX_DISPS, display_ids, ctypes.byref(out_count))
    if err != 0 or out_count.value == 0:
        return []

    # CGDisplayBounds(CGDirectDisplayID) → CGRect (origin + size), returns Boolean success
    fn_Bounds = getattr(cg, "CGDisplayBounds", None)
    if not fn_Bounds:
        return []
    class _CGRect(ctypes.Structure):
        _fields_ = [
            ("origin_x", ctypes.c_double),
            ("origin_y", ctypes.c_double),
            ("size_w", ctypes.c_double),
            ("size_h", ctypes.c_double),
        ]

    fn_Bounds.argtypes = [ctypes.c_uint32, ctypes.POINTER(_CGRect)]
    fn_Bounds.restype = ctypes.c_bool

    # CGMainDisplayID() → CGDirectDisplayID (0 on failure)
    fn_Main = getattr(cg, "CGMainDisplayID", None)
    main_id = 0
    if fn_Main:
        fn_Main.argtypes = []
        fn_Main.restype = ctypes.c_uint32
        main_id = fn_Main()

    # CGDisplayIsMain(CGDirectDisplayID) → Boolean
    fn_IsMain = getattr(cg, "CGDisplayIsMain", None)

    displays: List[DisplayInfo] = []
    for i in range(out_count.value):
        did = display_ids[i]
        rect = _CGRect()
        if not fn_Bounds(did, ctypes.byref(rect)):
            continue
        w = int(rect.size_w)
        h = int(rect.size_h)
        # Skip displays whose bounds are degenerate (zero size). Some CG APIs return success
        # even when the display is in standby or has invalid configuration.
        if w <= 0 or h <= 0:
            continue
        bounds = (int(rect.origin_x), int(rect.origin_y), w, h)
        is_main = bool(fn_IsMain(did)) if fn_IsMain else (did == main_id)
        name = _display_name_for_id(did, is_main)
        displays.append(
            DisplayInfo(id=did, name=name, bounds=bounds, is_primary=is_main, builtin=("Built-in" in name))
        )

    return displays


def _display_name_for_id(display_id: int, is_main: bool) -> str:
    """Return a human-readable display name for the given CG display ID.

    Uses system_profiler as a lookup table when available; falls back to generic names.
    """
    # Quick heuristic: main displays are typically built-in on laptops, external otherwise.
    if is_main:
        return "Main Display"
    return f"Display {display_id}"


def _enumerate_displays_system_profiler() -> List[DisplayInfo]:
    """Parse `system_profiler SPDisplaysDataType` output to enumerate displays.

    Returns empty list if the command fails or produces no useful output.
    """
    try:
        proc = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True, text=True, check=False, timeout=5.0,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    if proc.returncode != 0:
        return []

    # Split into per-display blocks using "Display Type:" as a section marker.
    raw = proc.stdout or ""
    # After splitting, each block that originally preceded "Display Type:" is the header (skip),
    # and each subsequent block starts with just the display name text (process).
    blocks = re.split(r"(?<=\n)          Display Type:", raw, flags=re.MULTILINE)

    displays: List[DisplayInfo] = []
    main_id_counter = 0
    for idx, block in enumerate(blocks):
        # Block 0 is always the header (before the first "Display Type:" match). Skip it.
        if idx == 0:
            continue

        block_lines = [ln.lstrip() for ln in block.strip().splitlines()] if block.strip() else []
        if not block_lines:
            continue

        # First line is now just the display name (the split consumed "Display Type:" prefix).
        name = block_lines[0].strip()
        joined = "\n".join(block_lines)

        res_match = re.search(r"Resolution:\s*([\d,]+)\s*x\s*([\d,]+)", joined)
        main_match = "Main Display: Yes" in joined

        w = int(res_match.group(1).replace(",", "")) if res_match else 0
        h = int(res_match.group(2).replace(",", "")) if res_match else 0

        main_id_counter += 1
        displays.append(
            DisplayInfo(
                id=main_id_counter,
                name=name,
                bounds=(0, 0, w, h),
                is_primary=main_match,
                builtin=("Built-in" in name or "Internal" in name),
            )
        )

    return displays if displays else []


def get_frontmost_display() -> Optional[DisplayInfo]:
    """Return the primary/active display.

    Uses CGMainDisplayID via CoreGraphics for accuracy; falls back to first item in list_screens().
    """
    screens = list_screens()
    if not screens:
        return None

    # Try CGMainDisplayID via ctypes — returns 0 on failure, so we only match non-zero ids.
    try:
        import ctypes, ctypes.util
        cg_path = ctypes.util.find_library("CoreGraphics")
        if cg_path:
            main_id = ctypes.CDLL(cg_path).CGMainDisplayID()
            if main_id:
                for s in screens:
                    if s.id == main_id:
                        return s
    except (AttributeError, OSError):
        pass

    # Fallback: first item in the list is typically the main display.
    return screens[0]


# ---------------------------------------------------------------------------
# Convenience module-level re-exports used by __init__.py
# ---------------------------------------------------------------------------


def capture_screen_raw(region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    """Capture the screen and return a bare PIL.Image (convenience wrapper).

    This wraps capture_screen() to maintain backward compatibility with callers that expect just
    an image object rather than a structured CaptureResult.
    """
    result = capture_screen(region=region)
    return result.image


# ---------------------------------------------------------------------------
# Main — quick self-test when run as a script
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s  %(message)s")
    print("Testing screen capture...")
    img = capture_screen()
    print(f"Captured full desktop: {img.size} (method={img.mode})")

    screens = list_screens()
    print(f"Found {len(screens)} display(s): {[s.name for s in screens]}")

    if screens and len(screens) > 1:
        frontmost = get_frontmost_display()
        if frontmost:
            print(f"Frontmost display: {frontmost.name} (id={frontmost.id})")
