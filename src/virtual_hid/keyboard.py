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

from ._vkeys import _MODIFIER_MAP, get_vkey


class KeyboardMixin:
    """Mixin providing keyboard injection via CGPostKeyboardEvent."""

    # Re-export module-level modifier map so existing callers can use self._MODIFIER_MAP.
    _MODIFIER_MAP = _MODIFIER_MAP

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Build letter→vkey lookup table once at init (A=KVK_A, B=KVK_B, ...)
        from ._vkeys import _ALL_VKEYS as vkeys

        self._letter_vkeys: dict[str, int] = {}
        for i in range(26):
            letter = chr(ord("a") + i)  # lowercase a-z — these are the type_char() input keys
            upper = letter.upper()       # uppercase A-Z — matches _ALL_VKEYS keys
            if upper in vkeys:
                self._letter_vkeys[letter] = vkeys[upper]

    def _resolve_modifier(self, name: str):
        """Resolve a modifier key name to its vkey constant."""
        return get_vkey(name)

    # -- Single-character typing ---------------------------------------------

    def press_key(self, vkey_name):
        """Press (down) a virtual key by name (e.g. 'A', 'cmd', 'return') or int vkey code."""
        if isinstance(vkey_name, str):
            vkey = get_vkey(vkey_name)
            if vkey is None:
                raise ValueError(f"Unknown virtual key name: {vkey_name!r}")
        else:
            vkey = int(vkey_name)

        self._api.keyboard_down(int(vkey))

    def release_key(self, vkey_name):
        """Release (up) a virtual key by name (e.g. 'A', 'cmd', 'return') or int vkey code."""
        if isinstance(vkey_name, str):
            vkey = get_vkey(vkey_name)
            if vkey is None:
                raise ValueError(f"Unknown virtual key name: {vkey_name!r}")
        else:
            vkey = int(vkey_name)

        self._api.keyboard_up(int(vkey))

    def type_char(self, char):
        """Type a single character. Handles uppercase by auto-pressing shift before the letter.

        Supports: A-Z/a-z (via _letter_vkeys), digits 0-9, space, tab, return, and common
        punctuation (/ . , ; ' [ ] \\ = - + @ # $ % ^ & * ( ) ! ? ~ _) via local fallback map.
        """
        # Map single-char whitespace/control symbols to their _vkeys names for reliable lookup
        _WS_TO_VKEY_NAME = {
            ' ': 'SPACE', '\t': 'TAB', '\n': 'RETURN', '\r': 'RETURN',
        }

        vkey = None
        is_upper_letter = len(char) == 1 and char.isupper() and char.lower() in self._letter_vkeys

        if is_upper_letter:
            # Shift + letter: use the lowercase key code from _letter_vkeys
            vkey = self._letter_vkeys[char.lower()]
        elif not is_upper_letter and char in self._letter_vkeys:
            # Lowercase letter — direct lookup from init-time table
            vkey = self._letter_vkeys[char]
        else:
            # Try whitespace/control mapping first (space, tab, newline, etc.)
            name = _WS_TO_VKEY_NAME.get(char)
            if name is not None:
                vkey = get_vkey(name)

            if vkey is None and len(char) == 1:
                # Local fallback for common punctuation/symbols — maps char → Carbon HID vkey code.
                # These are known Apple ApplicationServices key codes for a US QWERTY layout.
                _PUNCT_TO_VKEY = {
                    '.': 0x2E, ',': 0x2F, ';': 0x33, "'": 0x34,    # period comma semicolon apostrophe
                    '[': 0x21, ']': 0x19, '\\': 0x22,              # brackets backslash (non-colliding)
                    '/': 0x27, '=': 0x1B, '-': 0x1A, '+': 0x2D,    # slash equals minus plus
                    '@': 0x29, '#': 0x39, '$': 0x3F, '%': 0x40,    # at hash dollar percent
                    '^': 0x41, '&': 0x42, '*': 0x43, '(': 0x44,    # caret ampersand star paren-open
                    ')': 0x45, '!': 0x46, '?': 0x47, '~': 0x48,    # paren-close exclaim question tilde
                    '_': 0x49, '`': 0x32,                          # underscore grave (GRAVE is 0x32)
                }
                vkey = _PUNCT_TO_VKEY.get(char)

            if vkey is None:
                # Last resort: general vkey lookup for symbols defined in _ALL_VKEYS (e.g. GRAVE, MINUS)
                vkey = get_vkey(char)

        shift_needed = False
        if is_upper_letter:
            shift_needed = True
            shift_vkey = get_vkey("shift") or 0x38  # LSHIFT fallback

        if shift_needed:
            self.press_key(shift_vkey)
            time.sleep(0.02)

        if vkey is not None:
            self.press_key(vkey)
            time.sleep(0.03)
            self.release_key(vkey)
        else:
            # Unresolvable character — skip silently to avoid crashing the string
            pass

        if shift_needed:
            time.sleep(0.02)
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
            vkey = get_vkey(name)
            if vkey is None:
                raise ValueError(f"Unknown hotkey component: {name!r}")
            self.press_key(vkey)
            time.sleep(0.02)

    def release_hotkey(self, *keys):
        """Release a previously pressed hotkey combination."""
        for k in reversed(keys):
            name = k.lower().replace(" ", "")
            vkey = get_vkey(name)
            if vkey is None:
                raise ValueError(f"Unknown hotkey component: {name!r}")
            self.release_key(vkey)
            time.sleep(0.02)

    def hotkey(self, *keys):
        """Press and release a key combination (convenience wrapper)."""
        self.press_hotkey(*keys)
        time.sleep(0.1)
        self.release_hotkey(*keys)

    def press_and_release(self, vkey_name: str):
        """Press a key then release it (single keystroke). Accepts name or int."""
        if isinstance(vkey_name, str):
            vkey = get_vkey(vkey_name)
            if vkey is None:
                raise ValueError(f"Unknown virtual key name: {vkey_name!r}")
        else:
            vkey = int(vkey_name)

        self.press_key(vkey)
        time.sleep(0.03)
        self.release_key(vkey)
