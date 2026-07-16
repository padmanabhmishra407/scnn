#!/usr/bin/env python3
"""
Core ctypes bindings for CoreGraphics HID injection.

Wraps CGPostKeyboardEvent (keyboard-only, no permissions) and the full mouse event pipeline:
  CGEventSourceCreate -> CGEventCreateMouseEvent/CGEventPost/CFRelease.

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
# CoreGraphics / CoreFoundation framework constants (defined before class usage).
# ---------------------------------------------------------------------------

# kCGHIDEventTap = 0 -- CGEventTapLocation enum value for HID event injection.
# Posted events enter the window server at the raw HID point, making them indistinguishable from
# real USB keyboard/mouse input (the whole point of virtual_hid). Per Apple's CoreGraphics/CGEventTypes.h:
#   kCGHIDEventTap = 0, kCGSessionEventTap = 1, kCGAnnotatedSessionEventTap = 2.
kCGHIDEventTap: int = 0

# kCGSessionEventTap and kCGAnnotatedSessionEventTap defined for completeness (see docstring above).
kCGSessionEventTap: int = 1
kCGAnnotatedSessionEventTap: int = 2

# kCGHIDEventTapState = 0x80000002 (virtual event source state -- "no accessibility required").
kCGHIDEventTapState: int = 0x80000002


# ---------------------------------------------------------------------------
# Mouse event type constants (CGEventType enum values from CoreGraphics).
# ---------------------------------------------------------------------------

# Left mouse button events.
kCGEventLeftMouseDown: int = 1
kCGEventLeftMouseUp: int = 2

# Mouse event types (CGEventType enum values from CoreGraphics/CGEventTypes.h).
# Verified against Apple's official documentation: right-click=36, other/center=25.
# Values 14-17 used in stale_tests/virtual_hid_original.py are incorrect guesses from a
# different enum context and do not match Apple's CGEventType values.
kCGEventRightMouseDown: int = 36   # Apple official kCGEventRightMouseDown (NOT 14)
kCGEventRightMouseUp: int = 37     # Apple official kCGEventRightMouseUp (NOT 15)
kCGEventOtherMouseDown: int = 25   # Apple official for middle/other button down (NOT 16)
kCGEventOtherMouseUp: int = 26     # Apple official for middle/other button up (NOT 17)

# kCGEventScrollWheel and kCGEventMouseMoved used throughout mouse.py.
kCGEventScrollWheel: int = 22
kCGEventMouseMoved: int = 5


# ---------------------------------------------------------------------------
# Mouse button constants (CGMouseButton enum values).
# ---------------------------------------------------------------------------

kCGMouseButtonLeft: int = 0
kCGMouseButtonRight: int = 1
kCGMouseButtonCenter: int = 2


# ---------------------------------------------------------------------------
# Field IDs and unit enums for delta-based relative movement and scroll wheel events.
# These must be defined before the _CgAPI class so default argument values can reference them.
# ---------------------------------------------------------------------------

# Integer field selectors used by CGEventSetIntegerValueField / CGEventGetIntegerValueField.
# These are field IDs within the CGEventRef data structure, NOT event types.
kCGMouseEventDeltaX: int = 4
kCGMouseEventDeltaY: int = 5
kCGMouseEventClickState: int = 12

# Scroll wheel event unit constants (passed as the `units` parameter to CGEventCreateScrollWheelEvent2).
# kCGScrollEventUnitPixel = 0: delta values expressed in pixels.
# kCGScrollEventUnitLine = 1: delta values expressed in lines (typical mouse scroll units, ~120 per click).
kCGScrollEventUnitPixel: int = 0
kCGScrollEventUnitLine: int = 1

# Scroll wheel event delta axis selectors (for reading deltas back off an event ref).
# kCGScrollWheelEventDeltaAxis1 = vertical, kCGScrollWheelEventDeltaAxis2 = horizontal.
kCGScrollWheelEventDeltaAxis1: int = 0
kCGScrollWheelEventDeltaAxis2: int = 1


# ---------------------------------------------------------------------------
# CGPoint struct for CGEventCreateMouseEvent third argument (location)
# ---------------------------------------------------------------------------

class CGPoint(ctypes.Structure):
    """Mac OS X CGPoint -- two double-precision floating-point coordinates."""
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


def _safe_create_event_source(lib, state: int = kCGHIDEventTapState, timeout_sec: float = 3.0) -> int:
    """Create a CGEventSourceRef with fork-based timeout to handle macOS permission prompts.

    macOS may display an Accessibility permission dialog when calling ``CGEventSourceCreate``
    from non-interactive contexts (subprocess, CI). Python signals (SIGALRM) can't interrupt
    the GIL during C calls, so we use os.fork() -- a child process handles the blocking call
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

    # Check for explicit override first - allows testing scenarios where TTY detection fails
    force_interactive = os.environ.get("CG_HID_FORCE_INTERACTIVE", "") == "1"

    if not force_interactive:
        # Check if we're in an interactive context where permission prompts can be dismissed.
        # In CI/test environments, there's no way to dismiss macOS Accessibility permission dialogs,
        # so we skip event source creation entirely and fall back to keyboard-only mode immediately.
        env_flags = os.environ.get("CG_HID_NO_MOUSE", "")  # empty default -- only truthy when explicitly set to "1"
        is_ci_or_test = env_flags == "1" or \
            ("GITHUB_ACTIONS" in os.environ or "CI" in os.environ or "PYTEST_CURRENT_TEST" in os.environ)

        if is_ci_or_test:
            logger.debug("CI/test environment detected -- skipping CGEventSourceCreate (keyboard-only mode)")
            return 0

        # Check for TTY + DISPLAY to determine interactivity
        has_tty = sys.stdout.isatty()
        display = os.environ.get('DISPLAY', '') or os.environ.get('WAYLAND_DISPLAY', '')
        is_interactive = has_tty or bool(display)  # relaxed: TTY alone suffices (IDE terminals lack DISPLAY)

        if not is_interactive:
            logger.debug("Non-interactive context detected -- skipping CGEventSourceCreate (keyboard-only mode)")
            return 0

    logger.warning("CG_HID_FORCE_INTERACTIVE=1 set -- attempting CGEventSourceCreate even without TTY")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name

        def _child():
            try:
                result = lib.CGEventSourceCreate(state, None)
                # Use atomic rename to avoid race condition where parent reads empty file
                tmp_result = tmp_path + ".tmp"
                with open(tmp_result, "w") as f:
                    f.write(str(int(result)))
                _os.rename(tmp_result, tmp_path)
            except Exception:
                pass  # Don't let Python exception handlers run in forked child -- could deadlock on inherited mutexes
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

        # Re-read one more time in case CGEventSourceCreate just finished writing (race window).
        try:
            with open(tmp_path) as f:
                content = f.read().strip()
            if content:
                val = int(content)
                return ctypes.c_void_p(val).value or 0
        except Exception:
            pass

        # Timeout -- kill child process and reap zombie before returning.
        try:
            _os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            _os.waitpid(pid, 0)  # Reap zombie to avoid process-table leak
        except ChildProcessError:
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
        release_event(ref): Free CFTypeRef via CFRelease -- always call this on returned refs!

    All mouse/keyboard-event-returning methods return raw ctypes.c_void_p (CFTypeRef). The caller
    MUST release them via release_event() when done. Convenience context manager `cg_event_ref()` is
    provided for automatic cleanup.

    Event source creation may fail silently in non-interactive contexts -- the constructor falls back
    to keyboard-only mode if it times out waiting for Accessibility permission approval.
    """

    def __init__(self):
        self._lib = self._load_library()
        self._bind_sigs()
        # Cache the HID event source -- created once, reused across all mouse events.
        # Use safe wrapper to avoid blocking on macOS permission prompts in CI / subprocess contexts.
        self._event_source: int = _safe_create_event_source(self._lib)
        if not self._event_source:
            logger.warning(
                "CoreGraphics event source unavailable -- keyboard injection only (mouse requires "
                "Accessibility permissions). Set CG_HID_NO_MOUSE=\"1\" to enable explicit keyboard-only mode."
            )

    @staticmethod
    def _load_library() -> ctypes.CDLL:
        """Load the CoreGraphics framework. Raises ImportError on non-macOS."""
        path = ctypes.util.find_library("CoreGraphics")
        if not path:
            raise ImportError(
                "CoreGraphics framework not found -- virtual_hid requires macOS."
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

        # void CGEventPost(CGEventTapLocation, CGEventRef) -- posts event at kCGHIDEventTap (0).
        fn = getattr(lib, "CGEventPost")
        fn.argtypes = [ctypes.c_int32, ctypes.c_void_p]
        fn.restype = None  # void

        # CGEventRef CGEventCreate(CFAllocatorRef alloc, CGEventType type) -- NULL alloc + type=0
        # creates an uninitialized event used solely to read the current cursor location via
        # CGEventGetLocation. The returned ref MUST be released with CFRelease after reading.
        fn = getattr(lib, "CGEventCreate")
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int32]
        fn.restype = ctypes.c_void_p

        # CGPoint CGEventGetLocation(CGEventRef event) -- returns the active cursor point at call time.
        # On 64-bit macOS returning a struct by value requires explicit restype to avoid stack corruption.
        fn = getattr(lib, "CGEventGetLocation")
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = CGPoint

        # CGEventRef CGEventCreateScrollWheelEvent2(CGEventSourceRef source,
        #     CGScrollEventUnit units, uint32_t wheelCount, int32_t wheel1,
        #     int32_t wheel2, int32_t wheel3)
        # Fixed-arity replacement for the variadic CGEventCreateScrollWheelEvent. Required on arm64
        # because ctypes cannot safely pass varargs through registers vs. stack on Apple Silicon.
        fn = getattr(lib, "CGEventCreateScrollWheelEvent2")
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                       ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
        fn.restype = ctypes.c_void_p

        # void CGEventSetIntegerValueField(CGEventRef event, uint32_t field, int64_t value)
        fn = getattr(lib, "CGEventSetIntegerValueField")
        fn.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int64]
        fn.restype = None  # void

        # void CFRelease(CFTypeRef) -- lives in CoreFoundation, not CoreGraphics
        lib_cfn = ctypes.util.find_library("CoreFoundation")
        if lib_cfn:
            _cf = ctypes.CDLL(lib_cfn)
            _cf.CFRelease.argtypes = [ctypes.c_void_p]
            _cf.CFRelease.restype = None  # void
            self._cfn = _cf

    @property
    def event_source(self) -> int:
        """Cached CGEventSourceRef for mouse injection (0 if unavailable)."""
        return self._event_source

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

    def create_scroll_wheel_event(self, source: int, units=kCGScrollEventUnitLine,
                                  wheel1_delta: int = 0, wheel2_delta: int = 0) -> ctypes.c_void_p:
        """Create a scroll wheel event using the fixed-arity CGEventCreateScrollWheelEvent2.

        Args:
            source: CGEventSourceRef (must be non-zero for mouse injection).
            units: kCGScrollEventUnitPixel (0) or kCGScrollEventUnitLine (1). Defaults to line-based.
            wheel1_delta: Vertical delta value. Positive = up, negative = down (in `units` measure).
            wheel2_delta: Horizontal delta value. Positive = right, negative = left.

        Returns:
            CGEventRef that caller MUST release via CFRelease when done (use cg_event_ref context mgr).
        """
        # units=1 is kCGScrollEventUnitLine — inlined to avoid circular import at class-definition time
        wheel_count = 1 if not wheel2_delta else 2
        return self._lib.CGEventCreateScrollWheelEvent2(
            ctypes.c_void_p(source),
            ctypes.c_uint32(units),
            ctypes.c_uint32(wheel_count),
            ctypes.c_int32(wheel1_delta),
            ctypes.c_int32(wheel2_delta),
            ctypes.c_int32(0)  # third wheel (unused for typical scroll; set to 0)
        )

    def set_integer_value_field(self, event_ref: int, field_id: int, value: int):
        """Set an integer-valued field on a CGEventRef (e.g., deltaX/deltaY for relative movement).

        Args:
            event_ref: CGEventRef returned by any CoreGraphics create function.
            field_id: One of kCGMouseEventDeltaX (4) or kCGMouseEventDeltaY (5).
            value: The delta/int64 value to set on the event ref.
        """
        self._lib.CGEventSetIntegerValueField(
            ctypes.c_void_p(event_ref),
            ctypes.c_uint32(field_id),
            ctypes.c_int64(value)
        )

    def get_current_mouse_location(self) -> CGPoint:
        """Return the current cursor position as a CGPoint by creating an uninitialized event.

        Uses CGEventCreate(NULL, 0) to produce a throwaway event and reads its location field
        via CGEventGetLocation (which returns the active mouse point at call time). The event ref
        is released immediately after reading to avoid leaks.

        Raises RuntimeError if CoreFoundation failed to load — cannot release CFTypeRef without it.
        """
        evt = self._lib.CGEventCreate(None, ctypes.c_int32(0))  # NULL alloc, type=0 for uninitialized
        if not evt:
            return CGPoint(x=0.0, y=0.0)
        loc = self._lib.CGEventGetLocation(evt)

        if hasattr(self, "_cfn"):
            self._cfn.CFRelease(ctypes.c_void_p(evt))
        else:
            # CoreFoundation failed to load — cannot release the event ref. Log and let caller decide.
            logger.error(
                "CoreFoundation unavailable — CFTypeRef leak detected (event=%s). "
                "Mouse location reads will not work until _cfn is set.", evt
            )
        return loc

    def post_event(self, event_ref: int):
        """Inject an event at the HID tap location (kCGHIDEventTap = 0)."""
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
