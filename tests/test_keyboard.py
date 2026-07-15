#!/usr/bin/env python3
"""Tests for virtual_hid.keyboard — verify API surface works correctly."""

import sys
import unittest
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, "/Users/padmanabhmishra/Documents/scnn/src")


class TestKeyboardMixin(unittest.TestCase):
    """Test KeyboardMixin API surface with mocked _CgAPI."""

    def test_type_string_calls_api(self):
        """type_string should call keyboard_down/up for each character via type_char."""
        from virtual_hid.keyboard import KeyboardMixin

        # Create a class that inherits from KeyboardMixin and provides type_char
        class TestHID(KeyboardMixin):
            def __init__(self):
                self._api = Mock()
                self._letter_vkeys = {chr(ord("a") + i): i for i in range(26)}
                self._KVK_LSHIFT = 0x38

            # Provide the type_char method that VirtualHID would normally have
            def type_char(self, ch):
                vkey = self._letter_vkeys.get(ch.lower(), 0)
                if ch.isupper():
                    self._api.keyboard_down(self._KVK_LSHIFT)
                self._api.keyboard_down(vkey)
                self._api.keyboard_up(vkey)
                if ch.isupper():
                    self._api.keyboard_up(self._KVK_LSHIFT)

        hid = TestHID()

        with patch.object(hid._api, "keyboard_down", return_value=None), \
             patch.object(hid._api, "keyboard_up", return_value=None):
            hid.type_string("abc")

            # Verify keyboard_down was called at least once (for 'a', 'b', 'c')
            assert hid._api.keyboard_down.call_count >= 3, \
                f"Expected ≥3 keyboard_down calls for 'abc', got {hid._api.keyboard_down.call_count}"

    def test_hotkey_calls_modifier_api(self):
        """hotkey should press modifier keys via keyboard_down/up."""
        from virtual_hid.keyboard import KeyboardMixin

        class TestHID(KeyboardMixin):
            def __init__(self):
                self._api = Mock()
                self._MODIFIER_MAP = {"cmd": "_KVK_LCMD"}
                self._KVK_LCMD = 0x37

        hid = TestHID()

        with patch.object(hid._api, "keyboard_down", return_value=None), \
             patch.object(hid._api, "keyboard_up", return_value=None):
            hid.hotkey("cmd")

            # Verify keyboard_down was called for cmd modifier
            assert hid._api.keyboard_down.call_count >= 1, \
                f"Expected ≥1 keyboard_down call for hotkey(cmd), got {hid._api.keyboard_down.call_count}"


if __name__ == "__main__":
    unittest.main()
