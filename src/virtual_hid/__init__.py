#!/usr/bin/env python3
"""
Virtual HID Device for macOS — injects keyboard/mouse events at the system HID level.

Uses CoreGraphics (via ctypes) to post CGEvents through kCGHIDEventTap, which makes them
indistinguishable from real USB keyboard/mouse input to the operating system.

No PyObjC IOKit dependency needed. No root required. No external API keys.

Usage:
    import virtual_hid as hid
    hid.type_string("Hello World")
    hid.click(button="left", x=500, y=300)
    hid.scroll(clicks=3, direction="up")

Reference:
  - CGEvent virtual key codes (Carbon): ApplicationServices/Events.h
  - CoreGraphics framework: /System/Library/Frameworks/CoreGraphics.framework
"""

import time as _time

from ._core import (
    _CgAPI, kCGHIDEventTap, kCGHIDEventTapState,
    # New mouse event type constants for right/other button injection.
    kCGEventRightMouseDown, kCGEventRightMouseUp,
    kCGEventOtherMouseDown, kCGEventOtherMouseUp,
    # kCGEventMouseMoved (5) used with delta fields for RELATIVE movement.
    kCGEventMouseMoved,
    # Delta field IDs and scroll unit enums.
    kCGMouseEventDeltaX, kCGMouseEventDeltaY,
    kCGScrollEventUnitLine, kCGScrollEventUnitPixel,
)
from ._vkeys import get_vkey as _get_vkey_key
from .keyboard import KeyboardMixin
from .mouse import MouseMixin

# Phase 2: Vision/UI Reading modules (import lazily to avoid CG deps unless needed)
try:
    from .screen import capture_screen, capture_window, capture_region, list_screens
    from .windows import (
        list_windows, get_frontmost_window, find_window_by_name,
        find_window_by_app, get_app_pid,
    )
    from .ocr import ocr_image, ocr_text_from_region, bpe_tokenize
    from .agent import VisionAgent, Observation, Action

    # Live display feed (optional — fails gracefully if unavailable)
    try:
        from .live_feed import (
            LiveDisplayFeed,
            get_live_feed,
            FeedStats,
            LiveFeedError,
        )
    except ImportError:
        LiveDisplayFeed = None  # type: ignore[assignment]
        get_live_feed = None  # type: ignore[assignment]
        FeedStats = None  # type: ignore[assignment]
        LiveFeedError = None  # type: ignore[assignment]

    _VISION_MODULES_LOADED = True
except ImportError as e:
    print(f"⚠️  Phase 2 modules failed to load: {e}")
    _VISION_MODULES_LOADED = False


def is_vision_available() -> bool:
    """Check if Phase 2 Vision/UI Reading modules are available."""
    return _VISION_MODULES_LOADED


# ---------------------------------------------------------------------------
# Public API: VirtualHID class (composition of keyboard + mouse mixins)
# ---------------------------------------------------------------------------

class VirtualHID(KeyboardMixin, MouseMixin):
    """Injects keyboard and mouse events at the system HID level via CoreGraphics.

    Events posted through CGEventPost(kCGHIDEventTap) are indistinguishable from
    real USB HID device input — macOS treats them identically to hardware events.
    No Accessibility permissions required for event posting (only for reading).

    Attributes:
        _api (_CgAPI): The low-level ctypes wrapper around CoreGraphics functions.
            Event source is accessed directly via ``self._api.event_source``.
    """

    def __init__(self):
        super().__init__()  # sets up _letter_vkeys, modifier map
        self._api = _CgAPI()  # skips CGEventSourceCreate in CI/subprocess (keyboard-only mode)

    # -- Convenience wrappers for common operations --------------------------

    def run_demo(self):
        """Quick demo: type a message, click the top-left corner, scroll."""
        print("🎬 Running virtual HID demo...\n")

        # Type something
        print("⌨️  Typing 'Hello from SCNN Virtual HID'...")
        self.type_string("Hello from SCNN Virtual HID\n")
        _time.sleep(0.5)

        # Click somewhere safe (top-left corner — won't hit anything important)
        print("🖱️  Clicking at (100, 100)...")
        self.click(button="left", x=100, y=100)
        _time.sleep(0.3)

        # Scroll up once
        print("🔄 Scrolling up 2 clicks...")
        self.scroll(clicks=2, direction="up")
        _time.sleep(0.3)

        # Move mouse relative by 50 points right -- visible cursor displacement confirms injection.
        print("🖱️  Moving mouse 50 points right (relative)...")
        self.move_mouse(dx=50, dy=0)
        _time.sleep(0.2)

        print("\n✅ Demo complete. Virtual HID is live and injecting events.")


# ---------------------------------------------------------------------------
# Singleton convenience instance
# ---------------------------------------------------------------------------

_hid_singleton = None


def get_virtual_hid() -> VirtualHID:
    """Return a shared VirtualHID singleton (creates one on first call)."""
    global _hid_singleton
    if _hid_singleton is None:
        _hid_singleton = VirtualHID()
    return _hid_singleton


# ---------------------------------------------------------------------------
# Re-export key constants for user convenience
# ---------------------------------------------------------------------------

from ._vkeys import (
    _KVK_A, _KVK_B, _KVK_C, _KVK_D, _KVK_E, _KVK_F, _KVK_G, _KVK_H,
    _KVK_I, _KVK_J, _KVK_K, _KVK_L, _KVK_M, _KVK_N, _KVK_O, _KVK_P,
    _KVK_Q, _KVK_R, _KVK_S, _KVK_T, _KVK_U, _KVK_V, _KVK_W, _KVK_X,
    _KVK_Y, _KVK_Z,
    _KVK_1, _KVK_2, _KVK_3, _KVK_4, _KVK_5, _KVK_6, _KVK_7, _KVK_8,
    _KVK_9, _KVK_0,
    _KVK_LSHIFT, _KVK_RSHIFT, _KVK_LCMD, _KVK_RCMD,
    _KVK_LALT, _KVK_RALT, _KVK_LCTRL, _KVK_RCTRL,
    _KVK_RETURN, _KVK_TAB, _KVK_SPACE, _KVK_DELETE, _KVK_FORWARD_DEL,
    _KVK_ESCAPE,
)

__all__ = [
    "VirtualHID", "get_virtual_hid", "_CgAPI", "KeyboardMixin", "MouseMixin",
    # Key constants re-exported for convenience
    "_KVK_A", "_KVK_B", "_KVK_C", "_KVK_D", "_KVK_E", "_KVK_F", "_KVK_G", "_KVK_H",
    "_KVK_I", "_KVK_J", "_KVK_K", "_KVK_L", "_KVK_M", "_KVK_N", "_KVK_O", "_KVK_P",
    "_KVK_Q", "_KVK_R", "_KVK_S", "_KVK_T", "_KVK_U", "_KVK_V", "_KVK_W", "_KVK_X",
    "_KVK_Y", "_KVK_Z",
    "_KVK_1", "_KVK_2", "_KVK_3", "_KVK_4", "_KVK_5", "_KVK_6", "_KVK_7", "_KVK_8",
    "_KVK_9", "_KVK_0",
    "_KVK_LSHIFT", "_KVK_RSHIFT", "_KVK_LCMD", "_KVK_RCMD",
    "_KVK_LALT", "_KVK_RALT", "_KVK_LCTRL", "_KVK_RCTRL",
    "_KVK_RETURN", "_KVK_TAB", "_KVK_SPACE", "_KVK_DELETE", "_KVK_FORWARD_DEL",
    "_KVK_ESCAPE",
    # New mouse event type and field constants exposed for user convenience.
    "kCGEventRightMouseDown", "kCGEventRightMouseUp",
    "kCGEventOtherMouseDown", "kCGEventOtherMouseUp",
    "kCGEventMouseMoved",
    "kCGMouseEventDeltaX", "kCGMouseEventDeltaY",
    "kCGScrollEventUnitLine", "kCGScrollEventUnitPixel",
    # Live display feed (graceful fallback if unavailable)
    "LiveDisplayFeed", "get_live_feed", "FeedStats", "LiveFeedError",
]
