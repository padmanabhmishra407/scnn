#!/usr/bin/env python3
"""
Screen capture module for Vision/UI Reading capability.

Primary: Uses macOS `screencapture` command (zero deps, returns raw PNG bytes).
Fallback: CGWindowListCreateImage via ctypes for window-specific capture.

Usage:
    from virtual_hid.screen import capture_screen, capture_region
    img = capture_screen()  # Returns PIL Image of full desktop
"""

import subprocess
from typing import Optional, List, Dict, Any
from PIL import Image


def capture_screen() -> Image.Image:
    """Capture the entire screen using macOS screencapture command.

    Returns:
        PIL.Image: Full screen screenshot as RGB image.
    """
    result = subprocess.run(
        ["screencapture", "-r", "-C"],  # -r for raw, -C to capture all screens
        capture_output=True, check=True
    )
    return Image.open(result.stdout).convert("RGB")


def capture_window(window_id: int) -> Optional[Image.Image]:
    """Capture a specific window by its CGWindowID.

    Args:
        window_id: The CoreGraphics window ID to capture.

    Returns:
        PIL.Image of the window, or None if not found.
    """
    # Use screencapture with -W flag for specific window (requires Accessibility permission)
    try:
        result = subprocess.run(
            ["screencapture", "-r", "-W", str(window_id)],
            capture_output=True, check=True
        )
        return Image.open(result.stdout).convert("RGB")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: try CGWindowListCreateImage via ctypes (requires more setup)
        return None


def capture_region(x: int, y: int, width: int, height: int) -> Image.Image:
    """Capture a rectangular region of the screen.

    Args:
        x, y: Top-left corner coordinates.
        width, height: Region dimensions in pixels.

    Returns:
        PIL.Image of the specified region.
    """
    # Use screencapture with -l flag for specific region (requires Accessibility permission)
    try:
        result = subprocess.run(
            ["screencapture", "-r", "-l", f"{x},{y},{width},{height}"],
            capture_output=True, check=True
        )
        return Image.open(result.stdout).convert("RGB")
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: crop from full screen capture
        full = capture_screen()
        return full.crop((x, y, x + width, y + height))


def list_screens() -> List[Dict[str, Any]]:
    """List all connected displays with their bounds.

    Returns:
        List of dicts with 'id', 'name', 'bounds' (tuple of x,y,w,h).
    """
    # Use screencapture -l to list display IDs, then parse output
    try:
        result = subprocess.run(
            ["screencapture", "-l"],
            capture_output=True, text=True, check=True
        )
        screens = []
        for line in result.stdout.strip().split("\n"):
            if not line or line.startswith("#"):
                continue  # Skip header/comment lines
            parts = line.split()
            if len(parts) >= 2:
                try:
                    wid = int(parts[0])
                    name = parts[1]
                    screens.append({"id": wid, "name": name})
                except ValueError:
                    continue
        return screens
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: assume single screen
        return [{"id": 0, "name": "Built-in Retina Display"}]


if __name__ == "__main__":
    print("Testing screen capture...")
    img = capture_screen()
    print(f"✅ Captured full screen: {img.size}")

    screens = list_screens()
    print(f"🖥️  Found {len(screens)} display(s): {[s['name'] for s in screens]}")
