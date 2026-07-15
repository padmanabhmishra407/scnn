#!/usr/bin/env python3
"""
Core ctypes bindings for CoreGraphics HID injection.

Wraps CGPostKeyboardEvent (keyboard-only, no permissions) and the full mouse event pipeline:
  CGEventSourceCreate → CGEventCreateMouseEvent/CGEventPost/CFRelease.

Memory management is critical: every CFTypeRef returned by CoreGraphics MUST be released via
CFRelease to prevent leaks. All public methods handle this automatically via context managers.
"""

import ctypes
import ctypes.util
import logging
import os
import signal
import sys

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CoreGraphics / CoreFoundation framework constants
# ---------------------------------------------------------------------------

# kCGHIDEventTap = 2 (CGEventTapLocation enum value for HID event injection)
kCGHIDEventTap: int = 2

# kCGHIDEventTapState = 0x80000002 (virtual event source state — "no accessibility required")
kCGHIDEventTapState: int = 0x80000002


# ---------------------------------------------------------------------------
# CGPoint struct for CGEventCreateMouseEvent third argument (location)
# ---------------------------------------------------------------------------

class CGPoint(ctypes.Structure):
    """Mac OS X CGPoint — two double-precision floating-point coordinates."""
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


def _safe_create_event_source(lib, state: int = kCGHIDEventTapState, timeout_sec: float = 3.0) -> int:
    """Create a CGEventSourceRef with fork-based timeout to handle macOS permission prompts.

    macOS may display an Accessibility permission dialog when calling ``CGEventSourceCreate``
    from non-interactive contexts (subprocess, CI). Python signals (SIGALRM) can't interrupt
    the GIL during C calls, so we use os.fork() — a child process handles the blocking call
    while the parent kills it on timeout.

    Args:
        lib: Loaded CoreGraphics ctypes.CDLL handle.
        state: Event source state constant (default kCGHIDEventTapState = 0x80000002).
        timeout_sec: Maximum seconds to wait for the child process (default 3s).

    Returns:
        The CGEventSourceRef integer, or 0 on timeout/failure.
    """
    import os as _os
    import time as _time
    import tempfile

    # Check if we're in an interactive context where permission prompts can be dismissed.
    # In CI/test environments, there's no way to dismiss macOS Accessibility permission dialogs,
    # so we skip event source creation entirely and fall back to keyboard-only mode immediately.
    env_flags = os.environ.get("CG_HID_NO_MOUSE", "0") or ""
    is_ci_or_test = bool(env_flags) or \
        ("GITHUB_ACTIONS" in os.environ or "CI" in os.environ or "PYTEST_CURRENT_TEST" in os.environ)

    if is_ci_or_test:
        logger.debug("CI/test environment detected — skipping CGEventSourceCreate (keyboard-only mode)")
        return 0

    # Check for TTY + DISPLAY to determine interactivity
    has_tty = sys.stdout.isatty()
    display = os.environ.get('DISPLAY', '') or os.environ.get('WAYLAND_DISPLAY', '')
    is_interactive = has_tty and bool(display)

    if not is_interactive:
        logger.debug("Non-interactive context detected — skipping CGEventSourceCreate (keyboard-only mode)")
        return 0

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        def _child():
            result = lib.CGEventSourceCreate(state, None)
            # Use atomic rename to avoid race condition where parent reads empty file
            tmp_result = tmp_path + ".tmp"
            with open(tmp_result, "w") as f:
                f.write(str(int(result)))
            _os.rename(tmp_result, tmp_path)
            _os._exit(0)  # Use C-level exit to avoid Python cleanup in child

        pid = _os.fork()
        if pid == 0:
            _child()
            _os._exit(127)  # Should never reach here

        start = _time.monotonic()
        while _time.monotonic() - start < timeout_sec:
            try:
                ret, status = _os.waitpid(pid, _os.WNOHANG)
                if ret == pid:
                    with open(tmp_path) as f:
                        content = f.read().strip()
                    if not content:
                        return 0  # Empty file means child crashed before writing
                    val = int(content)
                    return ctypes.c_void_p(val).value or 0
            except ChildProcessError:
                pass
            _time.sleep(0.05)

        # Timeout — kill child process
        try:
            _os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return 0

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


class _CgAPI:
    """Thin ctypes wrapper around CoreGraphics C API for HID event injection.

    Methods:
        keyboard_down(vkey) / keyboard_up(vkey): Post via CGPostKeyboardEvent (no alloc needed).
        create_keyboard_event(source, vkey, down): Post via CGEventCreateKeyboardEvent (requires source).
        create_mouse_event(source, type, point, button): Create mouse event ref.
        post_event(event): Inject event at HID tap location.
        release_event(ref): Free CFTypeRef via CFRelease — always call this on returned refs!

    All mouse/keyboard-event-returning methods return raw ctypes.c_void_p (CFTypeRef). The caller
    MUST release them via release_event() when done. Convenience context manager `cg_event_ref()` is
    provided for automatic cleanup.

    Event source creation may fail silently in non-interactive contexts — the constructor falls back
    to keyboard-only mode if it times out waiting for Accessibility permission approval.
    """

    def __init__(self):
        self._lib = self._load_library()
        self._bind_sigs()
        # Cache the HID event source — created once, reused across all mouse events.
        # Use safe wrapper to avoid blocking on macOS permission prompts in CI / subprocess contexts.
        self._event_source: int = _safe_create_event_source(self._lib)
        if not self._event_source:
            logger.warning(
                "CoreGraphics event source unavailable — keyboard injection only (mouse requires "
                "Accessibility permissions). Set CG_HID_MOUSE_ONLY=1 to disable this warning."
            )

    @staticmethod
    def _load_library() -> ctypes.CDLL:
        """Load the CoreGraphics framework. Raises ImportError on non-macOS."""
        path = ctypes.util.find_library("CoreGraphics")
        if not path:
            raise ImportError(
                "CoreGraphics framework not found — virtual_hid requires macOS."
            )
        return ctypes.CDLL(path)

    def _bind_sigs(self):
        """Bind argument and return types for all CoreGraphics/CoreFoundation functions we use."""
        lib = self._lib

        # void CGPostKeyboardEvent(UInt8, Boolean)
        fn = getattr(lib, "CGPostKeyboardEvent")
        fn.argtypes = [ctypes.c_uint8, ctypes.c_bool]
        fn.restype = None  # void

        # CFTypeRef CGEventSourceCreate(CGEventType, CFAllocatorRef)
        fn = getattr(lib, "CGEventSourceCreate")
        fn.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
        fn.restype = ctypes.c_void_p

        # CGEventRef CGEventCreateKeyboardEvent(CFAllocatorRef, CGKeyCode, Boolean)
        fn = getattr(lib, "CGEventCreateKeyboardEvent")
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
        fn.restype = ctypes.c_void_p

        # CGEventRef CGEventCreateMouseEvent(CFAllocatorRef, CGEventType, CGPoint, CGMouseButton)
        fn = getattr(lib, "CGEventCreateMouseEvent")
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int32, CGPoint, ctypes.c_int32]
        fn.restype = ctypes.c_void_p

        # void CGEventPost(CGEventTapLocation, CGEventRef)
        fn = getattr(lib, "CGEventPost")
        fn.argtypes = [ctypes.c_int32, ctypes.c_void_p]
        fn.restype = None  # void

        # void CFRelease(CFTypeRef) — lives in CoreFoundation, not CoreGraphics
        lib_cfn = ctypes.util.find_library("CoreFoundation")
        if lib_cfn:
            _cf = ctypes.CDLL(lib_cfn)
            _cf.CFRelease.argtypes = [ctypes.c_void_p]
            _cf.CFRelease.restype = None  # void
            self._cfn = _cf

    def create_event_source(self, state: int = kCGHIDEventTapState) -> ctypes.c_void_p:
        """Create a virtual event source (no accessibility required for posting)."""
        return self._lib.CGEventSourceCreate(state, None)

    def keyboard_down(self, vkey: int):
        """Post key-down via CGPostKeyboardEvent (simpler, no alloc needed)."""
        return self._lib.CGPostKeyboardEvent(ctypes.c_uint8(vkey), True)

    def keyboard_up(self, vkey: int):
        """Post key-up via CGPostKeyboardEvent."""
        return self._lib.CGPostKeyboardEvent(ctypes.c_uint8(vkey), False)

    def create_keyboard_event(self, source: int, vkey: int, down: bool) -> ctypes.c_void_p:
        """Create a keyboard event ref (caller must release via CFRelease)."""
        return self._lib.CGEventCreateKeyboardEvent(source, ctypes.c_uint16(vkey), down)

    def create_mouse_event(self, source: int, event_type: int, point, button: int = 0) -> ctypes.c_void_p:
        """Create a mouse event ref (caller must release via CFRelease).

        Args:
            source: Event source reference.
            event_type: Mouse event type constant (e.g. kCGEventLeftMouseDown).
            point: ``(x, y)`` tuple/list of floats, or a ``CGPoint`` struct.
            button: Mouse-button code (default 0 = left).
        """
        if not isinstance(point, CGPoint):
            point = CGPoint(x=float(point[0]), y=float(point[1]))
        return self._lib.CGEventCreateMouseEvent(source, event_type, point, ctypes.c_int32(button))

    def post_event(self, event_ref: int):
        """Inject an event at the HID tap location."""
        return self._lib.CGEventPost(ctypes.c_int32(kCGHIDEventTap), ctypes.c_void_p(event_ref))

    def release_event(self, ref: int):
        """Free a CoreGraphics CFTypeRef via CFRelease. Safe to call with 0 (no-op)."""
        if ref and hasattr(self, "_cfn"):
            self._cfn.CFRelease(ctypes.c_void_p(ref))


# ---------------------------------------------------------------------------
# Context manager for automatic CFRelease cleanup
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def cg_event_ref(api: _CgAPI, event: int):
    """Yield a CoreGraphics event ref and auto-release it on exit.

    Usage:
        with cg_event_ref(api, evt) as ref:
            api.post_event(ref)
    """
    try:
        yield event
    finally:
        if event:
            api.release_event(event)


# ---------------------------------------------------------------------------
# Mouse event type constants (CGEventType enum values from CoreGraphics)
# ---------------------------------------------------------------------------

kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGEventRightMouseDown = 14
kCGEventRightMouseUp = 15
kCGEventOtherMouseDown = 16
kCGEventOtherMouseUp = 17
kCGEventScrollWheel = 22

# Mouse button constants (CGMouseButton enum)
kCGMouseButtonLeft = 0
kCGMouseButtonRight = 1
kCGMouseButtonCenter = 2
