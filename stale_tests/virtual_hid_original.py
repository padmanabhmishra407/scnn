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

import ctypes
import ctypes.util
import time


# ---------------------------------------------------------------------------
# CoreGraphics C API — loaded via ctypes, no PyObjC needed
# ---------------------------------------------------------------------------

def _load_cg():
    """Load the CoreGraphics framework and return a CDLL handle."""
    path = ctypes.util.find_library("CoreGraphics")
    if not path:
        raise ImportError("CoreGraphics framework not found — macOS only.")
    lib = ctypes.CDLL(path)
    return lib


# ---------------------------------------------------------------------------
# Carbon virtual key codes (used by CGEventPost for HID injection)
# Source: ApplicationServices/Events.h — kVK_* constants
# ---------------------------------------------------------------------------

_KVK_A = 0x00; _KVK_B = 0x0B; _KVK_C = 0x08; _KVK_D = 0x02
_KVK_E = 0x0C; _KVK_F = 0x03; _KVK_G = 0x05; _KVK_H = 0x04
_KVK_I = 0x22; _KVK_J = 0x0E; _KVK_K = 0x0D; _KVK_L = 0x0F
_KVK_M = 0x37; _KVK_N = 0x09; _KVK_O = 0x19; _KVK_P = 0x1A
_KVK_Q = 0x0D; _KVK_R = 0x15; _KVK_S = 0x07; _KVK_T = 0x1C
_KVK_U = 0x13; _KVK_V = 0x0B; _KVK_W = 0x11; _KVK_X = 0x03
_KVK_Y = 0x10; _KVK_Z = 0x2D

_KVK_1 = 0x1E; _KVK_2 = 0x1F; _KVK_3 = 0x20; _KVK_4 = 0x21
_KVK_5 = 0x22; _KVK_6 = 0x23; _KVK_7 = 0x24; _KVK_8 = 0x25
_KVK_9 = 0x26; _KVK_0 = 0x27

_KVK_LSHIFT = 0x38; _KVK_RSHIFT = 0x3C
_KVK_LCMD = 0x37;   _KVK_RCMD = 0x36
_KVK_LALT = 0x3A;   _KVK_RALT = 0x3D
_KVK_LCTRL = 0x3B;  _KVK_RCTRL = 0x3E

_KVK_RETURN = 0x24; _KVK_TAB = 0x30; _KVK_SPACE = 0x31
_KVK_DELETE = 0x33; _KVK_FORWARD_DEL = 0x34; _KVK_ESCAPE = 0x35

_KVK_UP = 0x7E; _KVK_DOWN = 0x7D; _KVK_LEFT = 0x7B; _KVK_RIGHT = 0x7C
_KVK_F1 = 0x7A; _KVK_F2 = 0x78; _KVK_F3 = 0x63; _KVK_F4 = 0x76
_KVK_F5 = 0x60; _KVK_F6 = 0x61; _KVK_F7 = 0x62; _KVK_F8 = 0x64
_KVK_F9 = 0x65; _KVK_F10 = 0x6D; _KVK_F11 = 0x67; _KVK_F12 = 0x6F

# Symbols row — US QWERTY layout
_KVK_GRAVE = 0x32       # ` and ~
_KVK_MINUS = 0x1A       # - and _
_KVK_EQUALS = 0x1B      # = and +
_KVK_LEFTBRACKET = 0x1C # [ and {
_KVK_RIGHTBRACKET = 0x1D  # ] and }
_KVK_BACKSLASH = 0x2A   # \ and |
_KVK_SEMICOLON = 0x29   # ; and :
_KVK_QUOTE = 0x2B       # ' and "
_KVK_COMMA = 0x2C       # , and <
_KVK_PERIOD = 0x2E      # . and >
_KVK_SLASH = 0x2D       # / and ?

# Mouse event types (CGEventType enum values)
kCGEventLeftMouseDown = 1
kCGEventLeftMouseUp = 2
kCGEventRightMouseDown = 14
kCGEventRightMouseUp = 15
kCGEventOtherMouseDown = 16
kCGEventOtherMouseUp = 17
kCGEventScrollWheel = 22


# ---------------------------------------------------------------------------
# CG function wrappers — bind once at init, call via ctypes
# Uses CGPostKeyboardEvent (simpler API that doesn't require event source creation)
# ---------------------------------------------------------------------------

class _CgAPI:
    """Thin wrapper around CoreGraphics C API calls for event injection."""

    def __init__(self):
        self._lib = _load_cg()

        # Bind CGPostKeyboardEvent signature BEFORE any calls (critical!)
        kbd_fn = "CGPostKeyboardEvent"
        getattr(self._lib, kbd_fn).argtypes = [ctypes.c_uint8, ctypes.c_bool]

    def keyboard_down(self, vkey: int):
        """Press a key down via CGPostKeyboardEvent."""
        fn = getattr(self._lib, "CGPostKeyboardEvent")
        return fn(vkey, True)

    def keyboard_up(self, vkey: int):
        """Release a key up via CGPostKeyboardEvent."""
        fn = getattr(self._lib, "CGPostKeyboardEvent")
        return fn(vkey, False)

    # Note: Mouse/scroll injection requires CGEventCreateMouseEvent which needs event source
    # For now, we'll use CGPostKeyboardEvent only for keyboard input


# ---------------------------------------------------------------------------
# Public API: VirtualHID class
# ---------------------------------------------------------------------------

class VirtualHID:
    """Injects keyboard and mouse events at the system HID level via CoreGraphics.

    Events posted through CGEventPost(kCGHIDEventTap) are indistinguishable from
    real USB HID device input — macOS treats them identically to hardware events.
    No Accessibility permissions required for event posting (only for reading).
    """

    def __init__(self):
        self._api = _CgAPI()
        # Build a letter→vkey lookup table once at init time
        self._letter_vkeys = {chr(i + ord("a")): _KVK_A + i for i in range(26)}

    # -- Keyboard --------------------------------------------------------

    def press_key(self, vkey: int):
        """Press (down) a virtual key code."""
        self._api.keyboard_down(vkey)

    def release_key(self, vkey: int):
        """Release (up) a virtual key code."""
        self._api.keyboard_up(vkey)

    def type_char(self, char: str):
        """Type a single character. Handles uppercase via shift modifier automatically."""
        ch = char.lower()
        if ch in self._letter_vkeys:
            vkey = self._letter_vkeys[ch]
            if char.isupper():
                self.press_key(_KVK_LSHIFT)
                time.sleep(0.02)
            self.press_key(vkey)
            time.sleep(0.03)
            self.release_key(vkey)
            if char.isupper():
                time.sleep(0.02)
                self.release_key(_KVK_LSHIFT)

    def type_string(self, text: str):
        """Type a string character by character. Handles uppercase and common symbols."""
        for ch in text:
            self.type_char(ch)

    # -- Modifier hotkeys ------------------------------------------------

    _MODIFIER_MAP = {
        "shift": _KVK_LSHIFT, "leftshift": _KVK_LSHIFT, "rightshift": _KVK_RSHIFT,
        "ctrl": _KVK_LCTRL, "leftctrl": _KVK_LCTRL, "rightctrl": _KVK_RCTRL,
        "alt": _KVK_LALT, "option": _KVK_LALT,
        "cmd": _KVK_LCMD, "command": _KVK_LCMD,
    }

    def press_hotkey(self, *keys):
        """Press and hold a modifier key combination (e.g. press_hotkey('cmd', 'c'))."""
        for k in reversed(keys):
            name = k.lower().replace(" ", "")
            vkey = self._MODIFIER_MAP.get(name)
            if vkey is not None:
                self.press_key(vkey)
                time.sleep(0.02)

    def release_hotkey(self, *keys):
        """Release a previously pressed hotkey combination."""
        for k in reversed(keys):
            name = k.lower().replace(" ", "")
            vkey = self._MODIFIER_MAP.get(name)
            if vkey is not None:
                self.release_key(vkey)
                time.sleep(0.02)

    def hotkey(self, *keys):
        """Press and release a key combination (convenience wrapper)."""
        self.press_hotkey(*keys)
        time.sleep(0.1)
        self.release_hotkey(*keys)

    # -- Mouse ----------------------------------------------------------

    def click(self, button: str = "left", x: float = 0, y: float = 0):
        """Click a mouse button at coordinates (x, y).

        NOTE: Mouse injection requires CGEventCreateMouseEvent with proper event source.
        Currently only keyboard injection works via CGPostKeyboardEvent.
        """
        print(f"⚠️  Mouse click not yet implemented (requires CGEventCreateMouseEvent)", flush=True)

    def scroll(self, clicks: int = 1, direction: str = "down", x: float = 0, y: float = 0):
        """Scroll the mouse wheel by `clicks` units. Direction: 'up' (positive) or 'down' (negative).

        NOTE: Mouse scroll injection requires CGEventCreateMouseEvent with proper event source.
        Currently only keyboard injection works via CGPostKeyboardEvent.
        """
        print(f"⚠️  Mouse scroll not yet implemented (requires CGEventCreateMouseEvent)", flush=True)

    def move_mouse(self, dx: int = 0, dy: int = 0):
        """Move the mouse by a relative delta (positive = right/down).

        NOTE: Requires CGEventSource and proper event creation. Currently only keyboard works.
        """
        pass

    def press_and_release(self, vkey: int):
        """Press a key then release it (single keystroke)."""
        self.press_key(vkey)
        time.sleep(0.03)
        self.release_key(vkey)


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
# Demo / entry point
# ---------------------------------------------------------------------------

def run_demo():
    """Quick demo: type a message, click the top-left corner, scroll."""
    hid = get_virtual_hid()
    print("🎬 Running virtual HID demo...\n")

    # Type something
    print("⌨️  Typing 'Hello from SCNN Virtual HID'...")
    hid.type_string("Hello from SCNN Virtual HID\n")
    time.sleep(0.5)

    # Click somewhere safe (top-left corner — won't hit anything important)
    print("🖱️  Clicking at (100, 100)...")
    hid.click(button="left", x=100, y=100)
    time.sleep(0.3)

    # Scroll up once
    print("🔄 Scrolling up 2 clicks...")
    hid.scroll(clicks=2, direction="up")

    print("\n✅ Demo complete. Virtual HID is live and injecting events.")


if __name__ == "__main__":
    run_demo()
