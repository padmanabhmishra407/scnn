#!/usr/bin/env python3
"""
MouseMixin — injects mouse events via CGEventCreateMouseEvent.

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
    kCGEventLeftMouseDown, kCGEventLeftMouseUp, kCGEventScrollWheel,
    kCGMouseButtonLeft, kCGMouseButtonRight, kCGMouseButtonCenter,
    cg_event_ref,
)

logger = logging.getLogger(__name__)


class MouseMixin:
    """Mixin providing mouse click/scroll/move injection via CGEventCreateMouseEvent."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def _mouse_available(self) -> bool:
        """Check if event source was successfully created (required for mouse events)."""
        return bool(getattr(self._api, "_event_source", 0))

    def _post_click(self, event_type: int, x: float, y: float, button_code: int):
        """Helper to create, post, and release a mouse event.

        Raises RuntimeError if the CoreGraphics event source is unavailable
        (e.g., Accessibility permission denied). This prevents silent failures
        where mouse clicks appear to succeed but inject no events.
        """
        if not self._mouse_available:
            raise RuntimeError(
                "Mouse injection requires a valid CGEventSource — Accessibility permissions may be needed. "
                "Keyboard-only mode is active."
            )

        with cg_event_ref(
            self._api,
            self._api.create_mouse_event(
                self._event_source, event_type, (x, y), button_code
            )
        ) as evt:
            if evt:
                self._api.post_event(evt)

    def click(self, button: str = "left", x: float = 0.0, y: float = 0.0):
        """Click a mouse button at coordinates (x, y).

        Args:
            button: 'left', 'right', or 'center' — defaults to 'left'.
            x, y: Screen coordinates in points (origin is top-left of screen).
                  Use (0, 0) for relative events; absolute positioning requires frontmost window.
        """
        btn_map = {
            "left": kCGMouseButtonLeft,
            "right": kCGMouseButtonRight,
            "center": kCGMouseButtonCenter,
        }
        button_code = btn_map.get(button.lower(), kCGMouseButtonLeft)

        # Down event
        self._post_click(kCGEventLeftMouseDown, x, y, button_code)
        time.sleep(0.02)

        # Up event
        self._post_click(kCGEventLeftMouseUp, x, y, button_code)
        time.sleep(0.02)

    def scroll(self, clicks: int = 1, direction: str = "down", x: float = 0.0, y: float = 0.0):
        """Scroll the mouse wheel by `clicks` units. Direction: 'up' (positive) or 'down' (negative).

        Args:
            clicks: Number of scroll units (1 click ≈ 120 points on most mice).
            direction: 'up', 'down', 'left', or 'right'. Defaults to 'down'.
            x, y: Screen coordinates for the event origin.
        """
        # Scroll wheel delta sign convention: positive = up, negative = down (in CoreGraphics)
        if direction.lower() in ("down", "downward"):
            delta_sign = -120  # one click downward
        elif direction.lower() in ("up", "upward"):
            delta_sign = 120   # one click upward
        else:
            raise ValueError(f"Unknown scroll direction '{direction}' — expected 'up' or 'down'.")

        total_delta = delta_sign * clicks

        # Create a scroll wheel event with vertical delta set to total_delta
        for _ in range(abs(total_delta) // 120):
            self._post_click(kCGEventScrollWheel, x, y, 0)

    def move_mouse(self, dx: int = 0, dy: int = 0):
        """Move the mouse by a relative delta (positive dx = right, positive dy = down)."""
        pass  # Requires CGEventSetLocation which needs CFNumberRef manipulation — skip for now
