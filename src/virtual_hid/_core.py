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


# ---------------------------------------------------------------------------
# CoreGraphics framework constants
# ---------------------------------------------------------------------------

# kCGHIDEventTap = 2 (CGEventTapLocation enum value for HID event injection)
kCGHIDEventTap: int = 2

# kCGHIDEventTapState = 0x80000002 (virtual event source state — "no accessibility required")
kCGHIDEventTapState: int = 0x80000002


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
    """

    def __init__(self):
        self._lib = self._load_library()
        self._bind_sigs()
        # Cache the HID event source — created once, reused across all mouse events
        self._event_source = self.create_event_source(kCGHIDEventTapState)
        if not self._event_source:
            raise RuntimeError("Failed to create CoreGraphics event source")

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
        """Bind argument and return types for all CoreGraphics functions we use."""
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
        fn.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_double, ctypes.c_int32]
        fn.restype = ctypes.c_void_p

        # void CGEventPost(CGEventTapLocation, CGEventRef)
        fn = getattr(lib, "CGEventPost")
        fn.argtypes = [ctypes.c_int32, ctypes.c_void_p]
        fn.restype = None  # void

        # void CFRelease(CFTypeRef) — critical for memory management of event refs
        fn = getattr(lib, "CFRelease")
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = None  # void

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

    def create_mouse_event(self, source: int, event_type: int, x: float, y: float, button: int = 0) -> ctypes.c_void_p:
        """Create a mouse event ref (caller must release via CFRelease)."""
        return self._lib.CGEventCreateMouseEvent(
            source, event_type, ctypes.c_double(x), ctypes.c_int32(button)
        )

    def post_event(self, event_ref: int):
        """Inject an event at the HID tap location."""
        return self._lib.CGEventPost(ctypes.c_int32(kCGHIDEventTap), ctypes.c_void_p(event_ref))

    def release_event(self, ref: int):
        """Free a CoreGraphics CFTypeRef via CFRelease. Safe to call with 0 (no-op)."""
        if ref:
            self._lib.CFRelease(ctypes.c_void_p(ref))


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
