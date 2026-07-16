#!/usr/bin/env python3
"""
VisionAgent — closed-loop see→think→act agent for UI interaction.

Composes screen capture, window enumeration, OCR, and HID injection into a unified API.
Enables the agent to SEE what's on screen, READ text/UI elements, and ACT via virtual_hid.

Usage:
    from virtual_hid.agent import VisionAgent
    agent = VisionAgent()
    observation = agent.observe()  # Capture + parse current screen state
    agent.act("type", "Hello World")  # Execute an action
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Observation:
    """Structured representation of what the agent sees on screen."""
    screenshot: Any = None  # PIL Image
    windows: List[Dict[str, Any]] = field(default_factory=list)
    frontmost_window: Optional[Dict[str, Any]] = None
    text_regions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """Structured representation of an action the agent wants to execute."""
    type: str  # "type", "click", "scroll", "hotkey", "move"
    text: Optional[str] = None
    button: str = "left"
    x: float = 0.0
    y: float = 0.0
    clicks: int = 1
    direction: str = "down"
    keys: List[str] = field(default_factory=list)
    dx: int = 0
    dy: int = 0


class VisionAgent:
    """Closed-loop agent that sees, thinks, and acts on the UI.

    This is the core of Phase 2 — enabling the agent to interact with macOS like a human would.
    The agent can:
      - Capture screenshots (full screen or specific windows/regions)
      - Enumerate open windows and find frontmost app
      - Extract text from UI elements using OCR
      - Execute actions via virtual_hid injection (type, click, scroll, hotkey)

    Example usage:
        agent = VisionAgent()
        obs = agent.observe()  # See what's on screen
        print(f"Frontmost app: {obs.frontmost_window['app_name']}")
        agent.act(Action(type="type", text="Hello World"))  # Type something
    """

    def __init__(self):
        from . import get_virtual_hid, capture_screen, list_windows, ocr_image

        self.hid = get_virtual_hid()
        self.capture = capture_screen  # fallback one-shot screen capture

        # Lazy-import live feed so circular deps stay contained. If the module
        # isn't available (e.g. in test environments), we fall back to capture_screen.
        try:
            from .live_feed import get_live_feed

            self.feed = get_live_feed(fps=15)  # type: ignore[assignment]
        except Exception:
            self.feed = None  # type: ignore[assignment]

        self.list_windows = list_windows
        self.ocr = ocr_image

    def observe(self) -> Observation:
        """Capture and parse the current screen state using the live feed when available.

        Returns:
            Observation with screenshot, windows, frontmost window, and OCR results.
        """
        # Prefer a frame from the live display feed; fall back to one-shot capture
        if self.feed is not None:
            screenshot = self.feed.get_frame()
        else:
            screenshot = self.capture()

        # List all visible windows
        windows = self.list_windows()

        # Get frontmost window
        frontmost = None
        if windows:
            frontmost = next((w for w in windows if w.get("is_visible")), None)

        # Extract text via OCR
        text_regions = self.ocr(screenshot)

        meta: Dict[str, Any] = {"timestamp": __import__("time").time()}
        if self.feed is not None:
            try:
                meta["feed_fps"] = getattr(self.feed, "_fps", None)
                stats = self.feed.get_stats()
                meta["frames_captured"] = (
                    stats.frames_captured if hasattr(stats, "frames_captured") else None  # type: ignore[attr-defined]
                )
            except Exception:
                pass

        return Observation(
            screenshot=screenshot,
            windows=windows,
            frontmost_window=frontmost,
            text_regions=text_regions,
            metadata=meta,
        )

    def act(self, action: Action):
        """Execute an action via virtual_hid injection.

        Args:
            action: The Action to execute (type, click, scroll, hotkey, move).
        """
        if action.type == "type":
            self.hid.type_string(action.text or "")
        elif action.type == "click":
            self.hid.click(button=action.button, x=action.x, y=action.y)
        elif action.type == "scroll":
            self.hid.scroll(clicks=action.clicks, direction=action.direction)
        elif action.type == "hotkey":
            self.hid.hotkey(*action.keys)
        elif action.type == "move":
            self.hid.move_mouse(dx=action.dx, dy=action.dy)

    def interact(self, prompt: str) -> Observation:
        """High-level interaction loop: observe → act based on prompt.

        This is a simplified version of the full agent loop — in practice you'd want more
        sophisticated reasoning here. For now, it supports basic text input and navigation.

        Args:
            prompt: Natural language instruction (e.g., "Type 'Hello' into Terminal").

        Returns:
            Updated Observation after executing the action.
        """
        # Parse simple prompts
        if prompt.startswith("type"):
            text = prompt[4:].strip().strip('"').strip("'")
            self.act(Action(type="type", text=text))
        elif prompt.startswith("click"):
            parts = prompt.split()
            x, y = float(parts[1]), float(parts[2]) if len(parts) > 2 else 0.0
            self.act(Action(type="click", x=x, y=y))
        elif prompt.startswith("hotkey"):
            keys = prompt[6:].strip().split("+")
            self.act(Action(type="hotkey", keys=keys))

        return self.observe()


if __name__ == "__main__":
    print("Testing VisionAgent...")
    agent = VisionAgent()

    # Observe current state
    obs = agent.observe()
    print(f"📸 Captured screenshot: {obs.screenshot.size if obs.screenshot else 'None'}")
    print(f"🪟 Found {len(obs.windows)} windows")
    if obs.frontmost_window:
        print(f"🎯 Frontmost: {obs.frontmost_window.get('name', 'Unknown')} (PID: {obs.frontmost_window.get('pid')})")
    print(f"📝 Extracted {len(obs.text_regions)} text regions via OCR")

    # Test action execution
    agent.act(Action(type="type", text="VisionAgent test\n"))
    print("✅ Action executed successfully")
