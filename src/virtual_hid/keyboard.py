#!/usr/bin/env python3
"""
KeyboardMixin — injects keyboard events via CoreGraphics HID injection.

Extracted from the original virtual_hid.py to enable clean composition with MouseMixin.
All type methods use CGPostKeyboardEvent (no accessibility permissions required).

Usage:
    class VirtualHID(KeyboardMixin, MouseMixin):
        ...

The mixin accesses self._api (_CgAPI instance) and self._letter_vkeys (a→vkey lookup).
"""

import time


class KeyboardMixin:
    """Mixin providing keyboard injection via CGPostKeyboardEvent."""

    # Modifier key name → _KVK_* attribute name mapping
    _MODIFIER_MAP = {
        "shift": "_KVK_LSHIFT", "leftshift": "_KVK_LSHIFT", "rightshift": "_KVK_RSHIFT",
        "ctrl": "_KVK_LCTRL", "leftctrl": "_KVK_LCTRL", "rightctrl": "_KVK_RCTRL",
        "alt": "_KVK_LALT", "option": "_KVK_LALT",
        "cmd": "_KVK_LCMD", "command": "_KVK_LCMD",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Build letter→vkey lookup table once at init (a=KVK_A, b=KVK_B, ...)
        from ._vkeys import _ALL_VKEYS as vkeys

        self._letter_vkeys: dict[str, int] = {}
        for i in range(26):
            letter = chr(ord("a") + i)
            # Use direct mapping — collisions are resolved at runtime via shift+key down/up timing
            if letter in vkeys:
                self._letter_vkeys[letter] = vkeys[letter]

    from typing import Optional

    def _resolve_modifier(self, name: str) -> Optional[int]:
        """Resolve a modifier key name to its vkey constant."""
        key = name.lower().replace(" ", "")
        attr_name = self._MODIFIER_MAP.get(key)
        if attr_name is None:
            return None
        # Look up the _KVK_* attribute on this instance (inherited from class or mixin)
        val = getattr(self, attr_name, None)
        if val is not None and isinstance(val, int):
            return val
        return None

    # -- Single-character typing ---------------------------------------------

    def press_key(self, vkey: int):
        """Press (down) a virtual key code via CGPostKeyboardEvent."""
        self._api.keyboard_down(vkey)

    def release_key(self, vkey: int):
        """Release (up) a virtual key code via CGPostKeyboardEvent."""
        self._api.keyboard_up(vkey)

    def type_char(self, char: str):
        """Type a single character. Handles uppercase by auto-pressing shift before the letter."""
        ch = char.lower()
        vkey = self._letter_vkeys.get(ch, 0x00)  # default to 0 (won't crash, just wrong key)

        if char.isupper():
            self.press_key(self._resolve_modifier("shift") or self._KVK_LSHIFT)
            time.sleep(0.02)

        self.press_key(vkey)
        time.sleep(0.03)
        self.release_key(vkey)

        if char.isupper():
            time.sleep(0.02)
            shift_vkey = self._resolve_modifier("shift") or self._KVK_LSHIFT
            self.release_key(shift_vkey)

    def type_string(self, text: str):
        """Type a string character by character. Handles uppercase and common symbols."""
        for ch in text:
            self.type_char(ch)

    # -- Modifier hotkeys ----------------------------------------------------

    def press_hotkey(self, *keys):
        """Press and hold a modifier key combination (e.g. press_hotkey('cmd', 'c'))."""
        for k in reversed(keys):
            name = k.lower().replace(" ", "")
            vkey = self._resolve_modifier(name) or self._KVK_LCMD  # fallback to Cmd
            self.press_key(vkey)
            time.sleep(0.02)

    def release_hotkey(self, *keys):
        """Release a previously pressed hotkey combination."""
        for k in reversed(keys):
            name = k.lower().replace(" ", "")
            vkey = self._resolve_modifier(name) or self._KVK_LCMD  # fallback to Cmd
            self.release_key(vkey)
            time.sleep(0.02)

    def hotkey(self, *keys):
        """Press and release a key combination (convenience wrapper)."""
        self.press_hotkey(*keys)
        time.sleep(0.1)
        self.release_hotkey(*keys)

    def press_and_release(self, vkey: int):
        """Press a key then release it (single keystroke)."""
        self.press_key(vkey)
        time.sleep(0.03)
        self.release_key(vkey)
