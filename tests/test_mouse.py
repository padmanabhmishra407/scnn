#!/usr/bin/env python3
"""Tests for virtual_hid.mouse — verify API surface works correctly."""

import sys
import unittest
from unittest.mock import Mock, patch

# Add src to path for imports
sys.path.insert(0, "/Users/padmanabhmishra/Documents/scnn/src")


class TestMouseMixin(unittest.TestCase):
    """Test MouseMixin API surface with mocked _CgAPI."""

    def test_click_creates_events(self):
        """click should create mouse events via cg_event_ref context manager."""
        from virtual_hid.mouse import MouseMixin

        # Create a class that inherits from MouseMixin and provides necessary attributes
        class TestHID(MouseMixin):
            def __init__(self):
                self._api = Mock()
                self._event_source = 12345
                self._kCGEventLeftMouseDown = 1
                self._kCGEventLeftMouseUp = 2

        hid = TestHID()

        # Patch create_mouse_event to return a mock event ref
        with patch.object(hid._api, "create_mouse_event", return_value=999):
            hid.click(button="left", x=100, y=200)

            # Verify create_mouse_event was called (for down and up events)
            assert hid._api.create_mouse_event.call_count >= 2, \
                f"Expected ≥2 create_mouse_event calls for click, got {hid._api.create_mouse_event.call_count}"

    def test_scroll_creates_events(self):
        """scroll should create multiple scroll wheel events."""
        from virtual_hid.mouse import MouseMixin

        class TestHID(MouseMixin):
            def __init__(self):
                self._api = Mock()
                self._event_source = 12345

        hid = TestHID()

        with patch.object(hid._api, "create_mouse_event", return_value=999):
            hid.scroll(clicks=3, direction="up")

            # Verify create_mouse_event was called for each scroll unit
            assert hid._api.create_mouse_event.call_count >= 3, \
                f"Expected ≥3 create_mouse_event calls for scroll(3, up), got {hid._api.create_mouse_event.call_count}"

    def test_move_mouse_is_stubbed(self):
        """move_mouse should currently be a stub (no-op)."""
        from virtual_hid.mouse import MouseMixin

        class TestHID(MouseMixin):
            pass

        hid = TestHID()
        # Should not raise or crash
        hid.move_mouse(dx=10, dy=20)


if __name__ == "__main__":
    unittest.main()
