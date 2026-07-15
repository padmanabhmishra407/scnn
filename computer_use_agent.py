#!/usr/bin/env python3
"""
Computer Use Agent for macOS — drives your desktop via synthetic HID events.

Connects to the Anthropic Messages API with the `computer` tool definition,
captures screenshots, and issues mouse/keyboard actions through pyautogui.

Usage:
  export ANTHROPIC_API_KEY="sk-ant-..."
  python3 computer_use_agent.py "Open Safari and navigate to example.com"

Requires:
  - macOS with Terminal.app granted Accessibility permissions (System Settings → Privacy & Security)
  - pip install pyautogui pillow anthropic
"""

import os
import sys
import io
import base64
import time
import json
import subprocess
from datetime import datetime
from typing import Optional

# Try importing dependencies; fail fast if missing
try:
    import anthropic
except ImportError:
    print("❌ Missing 'anthropic' SDK. Run: pip3 install anthropic")
    sys.exit(1)

try:
    import pyautogui
except ImportError:
    print("❌ Missing 'pyautogui'. Run: pip3 install pyautogui")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("❌ Missing 'pillow'. Run: pip3 install pillow")
    sys.exit(1)


class ComputerUseAgent:
    """Drives a desktop agentic loop via the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)

        # Screen resolution (detected once at startup)
        width, height = pyautogui.size()
        print(f"🖥️  Detected screen: {width}x{height}")

        # Computer tool definition for the API
        self.computer_tool = anthropic.types.ToolParam(
            name="computer",
            type="computer_20250124",
            display_width_px=width,
            display_height_px=height,
            keyboard_delay=0.05,  # delay between keystrokes in seconds
        )

    def take_screenshot(self) -> Image.Image:
        """Capture the entire screen and return a PIL Image."""
        img = pyautogui.screenshot()
        return img

    def execute_action(self, action_type: str, **kwargs):
        """Execute a single computer-use action via pyautogui or system commands."""
        if action_type == "click":
            x = kwargs.get("x", 0)
            y = kwargs.get("y", 0)
            button = kwargs.get("button", "left")
            print(f"🖱️ Clicking ({x}, {y}) with '{button}' button")
            pyautogui.click(x, y, button=button)

        elif action_type == "type":
            text = kwargs.get("text", "")
            hotkey = kwargs.get("hotkey", None)  # e.g. ["cmd", "c"] for ⌘C
            if hotkey:
                print(f"⌨️ Pressing hotkey: {' + '.join(hotkey)}")
                pyautogui.hotkey(*hotkey)
            else:
                print(f"⌨️ Typing: {text[:50]}{'...' if len(text) > 50 else ''}")
                # Use type directly for normal text, pressEnter for explicit returns
                pyautogui.write(text, interval=0.02)

        elif action_type == "mouse_move":
            x = kwargs.get("x", 0)
            y = kwargs.get("y", 0)
            print(f"🖱️ Moving mouse to ({x}, {y})")
            pyautogui.moveTo(x, y)

        elif action_type == "scroll":
            x = kwargs.get("x", 0)
            y = kwargs.get("y", 0)
            clicks = kwargs.get("clicks", 1)
            direction = kwargs.get("direction", "up")
            print(f"🔄 Scrolling {clicks} clicks at ({x}, {y}) — {direction}")
            pyautogui.scroll(clicks, x=x, y=y)

        elif action_type == "wait":
            seconds = kwargs.get("seconds", 1)
            print(f"⏳ Waiting {seconds}s...")
            time.sleep(seconds)

        else:
            print(f"❓ Unknown action type: {action_type}")

    def run(self, user_message: str):
        """Run the agentic loop for a single user request."""
        print(f"\n{'='*60}")
        print(f"🧠 Computer Use Agent — Task: {user_message[:80]}")
        print(f"{'='*60}\n")

        # Initial screenshot as context
        screenshot = self.take_screenshot()
        screenshot_base64 = _image_to_base64(screenshot)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            f"Task: {user_message}\n\n"
                            f"This is a screenshot of the current screen. Use the 'computer' tool to complete the task.\n"
                            f"If you need to type something, use the 'type' action. If you need to click, use 'click'.\n"
                            f"After each set of actions, take another screenshot so I can see the result."
                        ),
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_base64,
                        },
                        "name": "initial_screenshot",
                    },
                ],
            }
        ]

        # Loop: send to API → parse actions → execute → screenshot → repeat
        max_iterations = 20  # safety limit to prevent runaway loops
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            print(f"\n🔄 Iteration {iteration}/{max_iterations}")

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    tools=[self.computer_tool],
                    messages=messages,
                )
            except Exception as e:
                print(f"❌ API error: {e}")
                break

            # Check if the response has any tool use blocks
            content_blocks = [c for c in response.content if hasattr(c, "type")]
            tool_calls = [b for b in content_blocks if b.type == "tool_use"]

            if not tool_calls:
                print(f"\n✅ Agent finished. Final text:")
                text_blocks = [b for b in content_blocks if b.type == "text"]
                for tb in text_blocks:
                    print(tb.text)
                break

            # Execute all tool calls from this iteration
            screenshot = self.take_screenshot()
            screenshot_base64 = _image_to_base64(screenshot)

            for block in tool_calls:
                action = block.name  # e.g. "click", "type"
                params = block.input or {}
                print(f"\n📋 Tool call: {action}({json.dumps(params, indent=2)})")

                try:
                    self.execute_action(action, **params)
                except Exception as e:
                    print(f"⚠️ Action failed: {e}")

                time.sleep(0.5)  # small delay between actions

            # Append the executed tool result + new screenshot to messages
            messages.append({
                "role": "assistant",
                "content": [
                    anthropic.types.ContentBlock(
                        type="tool_use",
                        id=block.id,
                        name=block.name,
                        input=block.input,
                    )
                ],
            })

            # Build tool result content block(s) — one per screenshot capture
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": screenshot_base64,
                                },
                            }
                        ],
                    }
                ],
            })

        if iteration >= max_iterations:
            print(f"\n⚠️ Hit max iterations ({max_iterations}). Agent stopped.")


def _image_to_base64(image: Image.Image) -> str:
    """Convert a PIL Image to base64-encoded PNG."""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Set ANTHROPIC_API_KEY environment variable first.")
        print("   export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python3 computer_use_agent.py \"Your task description\"")
        print("\nExample:")
        print('  python3 computer_use_agent.py "Open Calculator and compute 42 * 7"')
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    agent = ComputerUseAgent(api_key=api_key)
    agent.run(user_message=task)
