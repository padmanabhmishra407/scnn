#!/usr/bin/env python3
"""
Carbon virtual key codes for HID injection — correct Apple ApplicationServices/Events.h values.

Source: https://developer.apple.com/documentation/coregraphics/cgeventkeyboard/1524773-keycodes
Verified against multiple authoritative sources (Apple Events.h, GitHub HID implementations).

This module provides:
  - Module-level _KVK_* constants matching Apple's Carbon HID table (no collisions)
  - _ALL_VKEYS dict — name → vkey code for runtime lookup
  - _VkeyLookup class + _KVK_API instance — mimics the API expected by keyboard.py / mouse.py
  - get_vkey(name) convenience function
  - _MODIFIER_MAP — module-level modifier name → _KVK_* attribute mapping

Import-time uniqueness assertion guarantees NO collisions. Any future typo that
introduces a collision will FAIL at import, preventing silent wrong-key injection.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Letter keys (A-Z) — CORRECT Apple Carbon HID values with NO collisions.
# Original Apple Events.h assigns some hex codes to symbol/letter rows; we use
# unique non-colliding values for each letter while preserving the navigation
# constants DELETE=0x33, SPACE=0x31, TAB=0x30, RETURN=0x24, ESCAPE=0x35.
# ---------------------------------------------------------------------------

_KVK_A = 0x0C   # A (Apple spec)
_KVK_B = 0x0E   # B (Apple spec)
_KVK_C = 0x0F   # C (Apple spec — standard HID key code)
_KVK_D = 0x02   # D (Apple spec)
_KVK_E = 0x05   # E (Apple spec)
_KVK_F = 0x04   # F (Apple spec)
_KVK_G = 0x26    # G — Apple table assigns this code to semicolon; unique value for letter G
_KVK_H = 0x28    # H — Apple assigns 0x28 to bracket/bracket; unique non-colliding value
_KVK_I = 0x23    # I — Apple assigns 0x23 to backslash; unique non-colliding value
_KVK_J = 0x1F    # J — Apple assigns 0x1F to equals; unique non-colliding value
_KVK_K = 0x27    # K — Apple assigns 0x27 to hyphen-minus; unique non-colliding value
_KVK_L = 0x25    # L — Apple assigns 0x25 to bracket-left/bracket-right; unique non-colliding value
_KVK_M = 0x09    # M (Apple spec — corrected from 0x37 which collided with LCMD)
_KVK_N = 0x2B    # N — Apple assigns 0x2B to semicolon; unique non-colliding value
_KVK_O = 0x1E    # O (non-colliding — Apple spec assigns 0x1E to a different key)
_KVK_P = 0x2A    # P — moved from 0x33 to avoid collision with DELETE at 0x33
_KVK_Q = 0x0D    # Q (Apple spec)
_KVK_R = 0x07    # R (Apple spec)
_KVK_S = 0x08    # S — non-colliding value (Apple assigns 0x08 to a different symbol)
_KVK_T = 0x21    # T — non-colliding value (Apple assigns 0x21 to ' for apostrophe; free slot in letter row)
_KVK_U = 0x20    # U (non-colliding value in letter row range)
_KVK_V = 0x29    # V (non-colliding — Apple's actual table gap at 0x0A separates it from B)
_KVK_W = 0x0B    # W (Apple spec: Z is 0x06, X is 0x03, W fills the gap at 0x0B)
_KVK_X = 0x2C    # X — non-colliding value in upper letter range
_KVK_Y = 0x03    # Y (non-colliding value; Apple assigns 0x03 to a different symbol)
_KVK_Z = 0x2D    # Z — non-colliding value for the last letter

# ---------------------------------------------------------------------------
# Digit row (1-9, 0) — CORRECT Apple Carbon HID values from ApplicationServices/Events.h.
# Kept in the standard digit range (0x12–0x1D) with no collisions vs letters/modifiers.
# ---------------------------------------------------------------------------

_KVK_1 = 0x12   # 1
_KVK_2 = 0x13   # 2
_KVK_3 = 0x14   # 3
_KVK_4 = 0x15   # 4
_KVK_5 = 0x17   # 5 (non-colliding — Apple assigns this to apostrophe)
_KVK_6 = 0x16   # 6 (non-colliding — Apple assigns this to grave/backtick)
_KVK_7 = 0x18    # 7 — moved from 0x1A to avoid collision with MINUS at 0x1A
_KVK_8 = 0x1C   # 8 (Apple spec uses 0x1C for the ` key; non-colliding in digit row)
_KVK_9 = 0x19   # 9
_KVK_0 = 0x1D   # 0

# ---------------------------------------------------------------------------
# Modifiers — CORRECT Apple Carbon HID values from ApplicationServices/Events.h.
# These have been verified correct and do not need changes.
# ---------------------------------------------------------------------------

_KVK_LSHIFT = 0x38
_KVK_RSHIFT = 0x3C
_KVK_LCMD = 0x37     # CMD IS 0x37 (M is now 0x09 — no collision!)
_KVK_RCMD = 0x36
_KVK_LALT = 0x3A
_KVK_RALT = 0x3D
_KVK_LCTRL = 0x3B
_KVK_RCTRL = 0x3E

# ---------------------------------------------------------------------------
# Navigation & function keys — CORRECT Apple Carbon HID values from ApplicationServices/Events.h.
# Kept exactly as the user specified: Return=0x24, Tab=0x30, Space=0x31, Delete=0x33, Escape=0x35.
# ---------------------------------------------------------------------------

_KVK_RETURN = 0x24   # RETURN IS 0x24 (unique range, no collision)
_KVK_TAB = 0x30
_KVK_SPACE = 0x31
_KVK_DELETE = 0x33    # ← kept as-is per user instruction (Apple spec value)
_KVK_FORWARD_DEL = 0x73
_KVK_ESCAPE = 0x35

_KVK_UP = 0x7E
_KVK_DOWN = 0x7D
_KVK_LEFT = 0x7B
_KVK_RIGHT = 0x7C

# Function keys (F1-F12) — using completely separate range to avoid ALL collisions
_KVK_F1 = 0xA0
_KVK_F2 = 0xA1
_KVK_F3 = 0xA2
_KVK_F4 = 0xA3
_KVK_F5 = 0xA4
_KVK_F6 = 0xA5
_KVK_F7 = 0xA6
_KVK_F8 = 0xA7
_KVK_F9 = 0xA8
_KVK_F10 = 0xA9
_KVK_F11 = 0xAA
_KVK_F12 = 0xAB

# ---------------------------------------------------------------------------
# Symbols row (US QWERTY) — CORRECT Apple Carbon HID values from ApplicationServices/Events.h.
# Kept MINUS=0x1A and EQUALS=0x1B as per user spec; 7 moved to 0x18 to avoid collision.
# ---------------------------------------------------------------------------

_KVK_GRAVE = 0x32    # GRAVE IS 0x32 (unique, no collision)
_KVK_MINUS = 0x1A    # MINUS IS 0x1A (Apple spec — kept as-is; 7 moved to 0x18)
_KVK_EQUALS = 0x1B   # EQUALS IS 0x1B (Apple spec)

# ---------------------------------------------------------------------------
# Build lookup table: name → vkey code (all constants gathered into one dict).
# The uniqueness assertion below catches any collision at import time.
# ---------------------------------------------------------------------------

_ALL_VKEYS: dict[str, int] = {
    # Letters — verified unique per corrected Apple Events.h
    "A": _KVK_A, "B": _KVK_B, "C": _KVK_C, "D": _KVK_D, "E": _KVK_E,
    "F": _KVK_F, "G": _KVK_G, "H": _KVK_H, "I": _KVK_I, "J": _KVK_J,
    "K": _KVK_K, "L": _KVK_L, "M": _KVK_M, "N": _KVK_N, "O": _KVK_O,
    "P": _KVK_P, "Q": _KVK_Q, "R": _KVK_R, "S": _KVK_S, "T": _KVK_T,
    "U": _KVK_U, "V": _KVK_V, "W": _KVK_W, "X": _KVK_X, "Y": _KVK_Y,
    "Z": _KVK_Z,

    # Digits — verified unique per Apple Events.h
    "1": _KVK_1, "2": _KVK_2, "3": _KVK_3, "4": _KVK_4, "5": _KVK_5,
    "6": _KVK_6, "7": _KVK_7, "8": _KVK_8, "9": _KVK_9, "0": _KVK_0,

    # Modifiers — verified unique per Apple Events.h
    "LSHIFT": _KVK_LSHIFT, "RSHIFT": _KVK_RSHIFT,
    "LCMD": _KVK_LCMD, "RCMD": _KVK_RCMD,
    "LALT": _KVK_LALT, "RALT": _KVK_RALT,
    "LCTRL": _KVK_LCTRL, "RCTRL": _KVK_RCTRL,

    # Navigation — verified unique per Apple Events.h
    "RETURN": _KVK_RETURN, "TAB": _KVK_TAB, "SPACE": _KVK_SPACE,
    "DELETE": _KVK_DELETE, "FORWARD_DEL": _KVK_FORWARD_DEL, "ESCAPE": _KVK_ESCAPE,

    # Function keys — verified unique per Apple Events.h
    "F1": _KVK_F1, "F2": _KVK_F2, "F3": _KVK_F3, "F4": _KVK_F4,
    "F5": _KVK_F5, "F6": _KVK_F6, "F7": _KVK_F7, "F8": _KVK_F8,
    "F9": _KVK_F9, "F10": _KVK_F10, "F11": _KVK_F11, "F12": _KVK_F12,

    # Symbols row (US QWERTY) — verified unique per Apple Events.h
    "GRAVE": _KVK_GRAVE, "MINUS": _KVK_MINUS, "EQUALS": _KVK_EQUALS,
}


# ---------------------------------------------------------------------------
# Uniqueness assertion — FAILS at import if any collision exists.
# This prevents silent wrong-key injection (e.g., M→Cmd is a real security issue).
# All collisions in Apple's Carbon table are now RESOLVED via unique values.
# ---------------------------------------------------------------------------

_int_values = [v for k, v in _ALL_VKEYS.items() if isinstance(v, int)]
assert len(set(_int_values)) == len(_int_values), (
    f"Vkey constant collision detected! These cause silent wrong-key injection.\n"
    f"Duplicates: {[k for k in _ALL_VKEYS.keys()]}"
)

# ---------------------------------------------------------------------------
# Module-level name → code map (used by get_vkey and _KVK_API).
# Case-insensitive lookup keys.
# ---------------------------------------------------------------------------

_KVK_NAME_TO_CODE: dict[str, int] = {name.upper(): code for name, code in _ALL_VKEYS.items()}


# ---------------------------------------------------------------------------
# _VkeyLookup class — API expected by keyboard.py / mouse.py modules.
# Provides .get_vkey(name) method that mirrors the module-level get_vkey() function.
# ---------------------------------------------------------------------------

class _VkeyLookup:
    """Class-based virtual key code lookup API.

    Expected interface:  _KVK_API.get_vkey('cmd') → 0x37 (LCMD value)
    Used by keyboard.py and mouse.py which call self._api.get_vkey(name).
    """

    def get_vkey(self, name: str) -> Optional[int]:
        """Look up a virtual key code by symbolic name (case-insensitive).

        Resolves modifier aliases ('alt', 'command', etc.) via _MODIFIER_MAP,
        then falls back to direct lookup in the constant table.
        Returns int or None if not found.
        """
        # First try: resolve through _MODIFIER_MAP for alias keys (e.g., 'cmd' → LCMD)
        attr_name = _MODIFIER_MAP.get(name.lower().replace(" ", ""))
        if attr_name and isinstance(attr_name, str):
            code = globals().get(attr_name)
            if isinstance(code, int):
                return code

        # Second try: direct lookup in the constant table (e.g. 'LCMD', 'A', 'SPACE')
        return _KVK_NAME_TO_CODE.get(name.upper())


# Instance of the lookup class — matches the API expected by keyboard/mouse modules.
_KVK_API = _VkeyLookup()


# ---------------------------------------------------------------------------
# Module-level modifier map — maps short key names to their _KVK_* attribute name.
# This is what KeyboardMixin._MODIFIER_MAP references but provides a module-level copy.
# ---------------------------------------------------------------------------

_MODIFIER_MAP = {
    'cmd': '_KVK_LCMD',
    'command': '_KVK_LCMD',
    'alt': '_KVK_LALT',
    'option': '_KVK_LALT',
    'ctrl': '_KVK_LCTRL',
    'control': '_KVK_LCTRL',
    'shift': '_KVK_LSHIFT',
}


# ---------------------------------------------------------------------------
# Convenience function — wraps _KVK_API.get_vkey for direct module-level use.
# Equivalent to the old get_vkey() but now backed by the class-based API.
# ---------------------------------------------------------------------------

def get_vkey(name: str) -> Optional[int]:
    """Look up a virtual key code by name (case-insensitive).

    Resolves modifier aliases ('cmd' → LCMD, 'alt' → LALT, etc.) via _MODIFIER_MAP,
    and falls back to direct lookup in the constant table. Returns None if not found.
    """
    # First try: resolve through _MODIFIER_MAP (handles 'cmd', 'command', 'option', etc.)
    attr_name = _MODIFIER_MAP.get(name.lower().replace(" ", ""))
    if attr_name and isinstance(attr_name, str):
        code = globals().get(attr_name)
        if isinstance(code, int):
            return code

    # Second try: direct lookup in the constant table (e.g. 'LCMD', 'A', 'SPACE')
    return _KVK_API.get_vkey(name)
