#!/usr/bin/env python3
"""
MouseMixin -- injects mouse events via CGEventCreateMouseEvent.

Requires: CGEventSource + CFRelease on every returned event ref (memory management critical).
Mouse injection does NOT require Accessibility permissions for posting, but reading screen state does.

Usage:
    class VirtualHID(KeyboardMixin, MouseMixin):
        ...

The mixin accesses self._api (_CgAPI instance) and uses cg_event_ref context manager for cleanup.
"""

import logging
import time

from ._core import (
    kCGEventLeftMouseDown, kCGEventLeftMouseUp,
    kCGEventRightMouseDown, kCGEventRightMouseUp,
    kCGEventOtherMouseDown, kCGEventOtherMouseUp,
    kCGEventScrollWheel, kCGEventMouseMoved,
    kCGMouseButtonLeft, kCGMouseButtonRight, kCGMouseButtonCenter,
    kCGMouseEventDeltaX, kCGMouseEventDeltaY,
    kCGScrollEventUnitLine, kCGScrollEventUnitPixel,
    cg_event_ref,
)

logger = logging.getLogger(__name__)


class MouseMixin:
    """Mixin providing mouse click/scroll/move injection via CGEventCreateMouseEvent."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def _mouse_available(self) -> bool:
        """Check if a valid CGEventSourceRef exists for mouse injection.

        Only non-zero positive values are considered valid -- CoreGraphics uses
        unsigned pointers, so negative values (e.g. -1 from corrupted refs) must
        be rejected to prevent silent event corruption on invalid sources.
        """
        return bool(self._api.event_source and self._api.event_source > 0)

    def _post_click(self, event_type: int, x: float, y: float, button_code: int):
        """Helper to create, post, and release a mouse event.

        Uses NULL (0) as the event source when no valid CGEventSourceRef is available —
        CoreGraphics allows HID tap injection with a NULL source via kCGHIDEventTap posting.
        This avoids requiring Accessibility permissions for mouse event creation while still
        allowing injection through the raw HID tap layer.
        """
        # Use 0 (NULL) as fallback when no valid event source is available
        src = self._api.event_source if self._mouse_available else 0

        with cg_event_ref(
            self._api,
            self._api.create_mouse_event(src, event_type, (x, y), button_code)
        ) as evt:
            if evt:
                self._api.post_event(evt)

    def click(self, button: str = "left", x: float = 0.0, y: float = 0.0):
        """Click a mouse button at coordinates (x, y).

        Args:
            button: 'left', 'right', or 'center' -- defaults to 'left'.
            x, y: Screen coordinates in points (origin is top-left of screen).
                  Use (0, 0) for relative events; absolute positioning requires frontmost window.
        """
        btn_map = {
            "left": kCGMouseButtonLeft,
            "right": kCGMouseButtonRight,
            "center": kCGMouseButtonCenter,
        }
        button_code = btn_map.get(button.lower(), kCGMouseButtonLeft)

        # Select the correct event type based on which physical mouse button is requested.
        # Uses Apple's official CGEventType values (36/37 for right, 25/26 for other/middle).
        if button.lower() == "left":
            down_type = kCGEventLeftMouseDown   # CGEventType 1 (Apple official)
            up_type = kCGEventLeftMouseUp       # CGEventType 2
        elif button.lower() == "right":
            down_type = kCGEventRightMouseDown  # CGEventType 36 (Apple official, NOT 14)
            up_type = kCGEventRightMouseUp      # CGEventType 37 (NOT 15)
        else:  # 'center' or any other button
            down_type = kCGEventOtherMouseDown  # CGEventType 25 (Apple official, NOT 16)
            up_type = kCGEventOtherMouseUp      # CGEventType 26 (NOT 17)

        self._post_click(down_type, x, y, button_code)
        time.sleep(0.02)

        self._post_click(up_type, x, y, button_code)
        time.sleep(0.02)

    def scroll(self, clicks: int = 1, direction: str = "down", x: float = 0.0, y: float = 0.0):
        """Scroll the mouse wheel by `clicks` units. Direction: 'up', 'down', 'left', or 'right'.

        Args:
            clicks: Number of scroll units (1 click in line-based units equals ~120 pixels; this maps
                    directly to typical mouse wheel 'clicks').
            direction: 'up', 'down', 'left', or 'right'. Defaults to 'down'.
            x, y: Screen coordinates for the event origin. (Scroll events are direction-based so x/y
                  affect only which window receives the scroll; pass 0/0 if not needed.)
        """
        # Scroll wheel delta sign convention in CoreGraphics: positive = up/right, negative = down/left.
        vertical_delta = 0
        horizontal_delta = 0

        direction_lower = direction.lower()
        if direction_lower in ("down", "downward"):
            vertical_delta = -abs(clicks) * 1     # negative for down; units already in line count
        elif direction_lower in ("up", "upward"):
            vertical_delta = abs(clicks) * 1       # positive for up
        elif direction_lower in ("left", "leftward"):
            horizontal_delta = -abs(clicks) * 1    # negative for left scroll
        elif direction_lower in ("right", "rightward"):
            horizontal_delta = abs(clicks) * 1     # positive for right scroll
        else:
            raise ValueError(
                f"Unknown scroll direction '{direction}' -- expected 'up', 'down', 'left', or 'right'."
            )

        # Use NULL (0) as fallback when no valid event source is available —
        # CGEventCreateScrollWheelEvent accepts NULL allocator for default behavior.
        src = self._api.event_source if self._mouse_available else 0

        evt = self._api.create_scroll_wheel_event(
            source=src,
            units=kCGScrollEventUnitLine,
            wheel1_delta=vertical_delta,
            wheel2_delta=horizontal_delta,
        )
        if not evt:
            logger.warning("scroll failed: could not create scroll wheel event.")
            return

        with cg_event_ref(self._api, evt):
            self._api.post_event(evt)

    def move_mouse(self, dx: int = 0, dy: int = 0):
        """Move the mouse by a relative delta (positive dx=right, positive dy=down).

        Uses NULL event source when no valid CGEventSourceRef exists — CoreGraphics allows HID tap
        injection with NULL source via kCGHIDEventTap posting. This avoids requiring Accessibility
        permissions while still allowing injection through the raw HID tap layer.
        """
        # Use 0 (NULL) as fallback when no valid event source is available
        src = self._api.event_source if self._mouse_available else 0

        # Step 1: Read current cursor position so the MouseMoved event has a valid base location.
        loc = self._api.get_current_mouse_location()

        # Step 2: Create a MouseMoved event at the current location (button arg ignored for this type).
        evt_ref = self._api.create_mouse_event(
            source=src,
            event_type=kCGEventMouseMoved,     # CGEventType value 5 -- indicates delta-mode movement
            point=(loc.x, loc.y),
            button=kCGMouseButtonLeft,          # ignored by CoreGraphics for MouseMoved type; kept for API compat
        )
        if not evt_ref:
            logger.warning("move_mouse failed: could not create mouse event ref.")
            return

        # Step 3: Set the delta X and Y integer fields to encode relative movement amounts.
        self._api.set_integer_value_field(evt_ref, kCGMouseEventDeltaX, dx)
        self._api.set_integer_value_field(evt_ref, kCGMouseEventDeltaY, dy)

        # Step 4: Post through HID tap so the event is indistinguishable from real USB mouse input.
        with cg_event_ref(self._api, evt_ref):
            self._api.post_event(evt_ref)
