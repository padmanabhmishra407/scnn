#!/usr/bin/env python3
"""Tests for virtual_hid.mouse — verify API surface works correctly."""

import sys
import unittest
from unittest.mock import Mock, patch

from virtual_hid._core import CGPoint  # used in test_move_mouse_posts_delta_event

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
                # _mouse_available reads self._api.event_source; provide a real int value.
                self._api.event_source = 12345
                self._kCGEventLeftMouseDown = 1
                self._kCGEventLeftMouseUp = 2

        hid = TestHID()

        # Patch create_mouse_event to return a mock event ref; also patch post_event.
        with patch.object(hid._api, "create_mouse_event", return_value=999),              patch.object(hid._api, "post_event"):
            hid.click(button="left", x=100, y=200)

            # Verify create_mouse_event was called (for down and up events)
            assert hid._api.create_mouse_event.call_count >= 2, \
                f"Expected ≥2 create_mouse_event calls for click, got {hid._api.create_mouse_event.call_count}"

    def test_scroll_creates_events(self):
        """scroll should call create_scroll_wheel_event (NOT create_mouse_event) with real deltas."""
        from virtual_hid.mouse import MouseMixin

        class TestHID(MouseMixin):
            def __init__(self):
                self._api = Mock()
                # _mouse_available reads self._api.event_source; provide a real int value.
                self._api.event_source = 12345

        hid = TestHID()

        with patch.object(hid._api, "post_event"):
            hid.scroll(clicks=3, direction="up")

            # Verify create_scroll_wheel_event was called exactly once (single event per scroll call).
            assert hid._api.create_scroll_wheel_event.call_count == 1, \
                f"Expected 1 create_scroll_wheel_event call for scroll(3, up), got " \
                f"{hid._api.create_scroll_wheel_event.call_count}"

            # Verify the vertical delta was set to +3 (positive = up direction).
            call_args = hid._api.create_scroll_wheel_event.call_args
            assert call_args[1]["wheel1_delta"] == 3, \
                f"Expected wheel1_delta=+3 for scroll(3, up), got {call_args[1]['wheel1_delta']}"

            # Verify horizontal delta is zero (no horizontal scrolling).
            assert call_args[1]["wheel2_delta"] == 0, \
                f"Expected wheel2_delta=0 for vertical-only scroll, got {call_args[1]['wheel2_delta']}"

    def test_move_mouse_posts_delta_event(self):
        """move_mouse should create a MouseMoved event and set deltaX/deltaY integer fields."""
        from virtual_hid.mouse import MouseMixin

        class TestHID(MouseMixin):
            def __init__(self):
                self._api = Mock()
                # _mouse_available reads self._api.event_source; provide a real int value.
                self._api.event_source = 12345
                self._api.get_current_mouse_location.return_value = CGPoint(x=500, y=300)

        hid = TestHID()

        # Use side_effect to capture calls AND return a valid ref for the context manager.
        create_calls = []
        def track_create(*args, **kwargs):
            create_calls.append((args, kwargs))
            return 999  # Simulate a non-zero event ref for cg_event_ref

        hid._api.create_mouse_event.side_effect = track_create

        with patch.object(hid._api, "post_event"):
            hid.move_mouse(dx=10, dy=20)

        # Verify create_mouse_event was called exactly once.
        assert len(create_calls) == 1, \
            "Expected 1 create_mouse_event call for move_mouse, got " + str(len(create_calls))

        _, kwargs = create_calls[0]
        # Event type is passed as keyword arg 'event_type' and should equal kCGEventMouseMoved (5).
        assert kwargs["event_type"] == 5, \
            "Expected event_type=5 (kCGEventMouseMoved), got " + str(kwargs.get("event_type"))

        # Verify set_integer_value_field was called twice: once for deltaX=10 and once for deltaY=20.
        set_calls = []
        def track_set(*a, **kw):
            set_calls.append((a, kw))

        hid._api.set_integer_value_field.side_effect = track_set
        # Re-run move_mouse to capture set_integer_value_field calls (create calls already tracked).
        create_calls.clear()
        with patch.object(hid._api, "post_event"):
            hid.move_mouse(dx=10, dy=20)

        assert len(set_calls) == 2, \
            "Expected 2 set_integer_value_field calls (deltaX + deltaY), got " + str(len(set_calls))


