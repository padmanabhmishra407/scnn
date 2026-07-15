#!/usr/bin/env python3
"""
Window enumeration module for Vision/UI Reading capability.

Uses CGWindowListCopyWindowInfo via osascript (no ctypes needed).
Requires Accessibility permissions on macOS 10.15+.

Usage:
    from virtual_hid.windows import list_windows, get_frontmost_window
    windows = list_windows()
    frontmost = get_frontmost_window()
"""

import subprocess
from typing import Optional, List, Dict, Any


def _run_osascript(command: str) -> str:
    """Run an AppleScript command and return stdout."""
    result = subprocess.run(
        ["osascript", "-e", command],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def list_windows() -> List[Dict[str, Any]]:
    """List all on-screen windows with their metadata.

    Returns:
        List of dicts with keys: id, name, pid, bounds (tuple), is_visible.
    """
    script = """
    tell application "System Events"
        set windowList to every window of every process whose visible is true
        set output to ""
        repeat with w in windowList
            set output to output & id of w & "|" & name of w & "|" & unix id of (parent of w) & "|" & bounds of w & "|" & visible of w & linefeed
        end repeat
        return output
    end tell
    """

    try:
        result = _run_osascript(script)
        windows = []
        for line in result.strip().split("\n"):
            if not line or line.startswith("error"):
                continue
            parts = line.split("|")
            if len(parts) >= 5:
                try:
                    bounds = tuple(int(x) for x in parts[3].strip("()").split(","))
                    windows.append({
                        "id": int(parts[0]),
                        "name": parts[1],
                        "pid": int(parts[2]),
                        "bounds": bounds,  # (x, y, width, height)
                        "is_visible": bool(int(parts[4])),
                    })
                except (ValueError, IndexError):
                    continue
        return windows
    except subprocess.CalledProcessError as e:
        print(f"⚠️  list_windows failed: {e.stderr}")
        return []


def get_frontmost_window() -> Optional[Dict[str, Any]]:
    """Get the currently focused window.

    Returns:
        Dict with 'id', 'name', 'pid', 'bounds' of frontmost window, or None.
    """
    script = """
    tell application "System Events"
        set frontApp to first process whose frontmost is true
        return name of frontApp & "|" & id of (first window of frontApp) & "|" & bounds of (first window of frontApp)
    end tell
    """

    try:
        result = _run_osascript(script)
        parts = result.split("|")
        if len(parts) >= 3:
            return {
                "app_name": parts[0],
                "window_id": int(parts[1]),
                "bounds": tuple(int(x) for x in parts[2].strip("()").split(",")),
            }
    except subprocess.CalledProcessError as e:
        print(f"⚠️  get_frontmost_window failed: {e.stderr}")
    return None


def find_window(name: str, exact: bool = False) -> List[Dict[str, Any]]:
    """Find windows by name substring (case-insensitive).

    Args:
        name: Search string.
        exact: If True, match only exact window names.

    Returns:
        List of matching window dicts.
    """
    all_windows = list_windows()
    if exact:
        return [w for w in all_windows if w["name"] == name]
    return [w for w in all_windows if name.lower() in w["name"].lower()]


def get_app_process(app_name: str) -> Optional[int]:
    """Get the PID of a running application.

    Args:
        app_name: Application name (e.g., "Google Chrome", "Terminal").

    Returns:
        PID as integer, or None if not found.
    """
    script = f"""
    tell application "System Events"
        return unix id of process "{app_name}"
    end tell
    """

    try:
        result = _run_osascript(script)
        return int(result)
    except (subprocess.CalledProcessError, ValueError):
        return None


if __name__ == "__main__":
    print("Testing window enumeration...")

    # List all windows
    windows = list_windows()
    print(f"🪟 Found {len(windows)} visible windows:")
    for w in windows[:10]:  # Show first 10
        print(f"   - {w['name']} (PID: {w['pid']}, Bounds: {w['bounds']})")

    # Get frontmost window
    front = get_frontmost_window()
    if front:
        print(f"\n🎯 Frontmost app: {front['app_name']}")
        print(f"   Window ID: {front['window_id']}, Bounds: {front['bounds']}")

    # Find Chrome windows
    chrome_windows = find_window("Chrome")
    print(f"\n🔍 Found {len(chrome_windows)} Chrome window(s)")
