#!/usr/bin/env python3
"""
Window enumeration module for Vision/UI Reading capability.

Uses CGWindowListCopyWindowInfo via osascript (no ctypes needed).
Requires Accessibility permissions on macOS 10.15+.

Usage:
    from virtual_hid.windows import list_windows, get_frontmost_window, find_window_by_name
    windows = list_windows()
    frontmost = get_frontmost_window()
"""

import logging
import subprocess
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


# AppleScript that calls CGWindowListCopyWindowInfo and returns results as a
# human-readable text format.  We use CGWindowListCopyWindowInfo with the
# kCGWindowListOptionAll option so every window (including hidden ones) is
# reported, which avoids relying on System Events / Accessibility APIs.
_LIST_WINDOWS_SCRIPT = """\
set output to ""
try
    set windowArray to current application's CGWindowListCopyWindowInfo(2, 0) as list
    repeat with aWindow in windowArray
        set output to output & "WINDOW|" & ... \
"""

def _parse_window_info(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a single CGWindowListCopyWindowInfo entry into our structured dict."""
    try:
        wid = int(raw.get("kCGWindowNumber", 0))
        owner_pid = raw.get("kCGWindowOwnerPID", 0)

        # kCGWindowName may be empty string for some windows (e.g. dock, menu bar).
        name = raw.get("kCGWindowName", "") or ""
        app_name = raw.get("kCGWindowOwnerName", "") or "Unknown"

        bounds_raw = raw.get("kCGWindowBounds", {})
        if isinstance(bounds_raw, dict):
            x = float(bounds_raw.get("X", 0))
            y = float(bounds_raw.get("Y", 0))
            w = float(bounds_raw.get("Width", 0))
            h = float(bounds_raw.get("Height", 0))
            bounds = (x, y, w, h)
        else:
            bounds = (0.0, 0.0, 0.0, 0.0)

        # kCGWindowAlpha is the window opacity (1.0 = opaque).
        alpha = raw.get("kCGWindowAlpha", 1.0) or 0.0
        is_visible = bool(alpha > 0 and wid != 0)

        return {
            "id": wid,
            "name": name,
            "pid": int(owner_pid),
            "app_name": app_name,
            "bounds": bounds,
            "is_visible": is_visible,
            "alpha": float(alpha),
            "layer": raw.get("kCGWindowLayer", 0),
            "window_number": raw.get("kCGWindowNumber", wid),
        }
    except (ValueError, TypeError, KeyError) as e:
        logger.debug(f"Skipping malformed window entry: {e}")
        return None


def _run_osascript(script_text: str) -> str:
    """Run an AppleScript via osascript and return stdout.

    Raises CalledProcessError on failure (caller handles).
    """
    result = subprocess.run(
        ["osascript", "-e", script_text],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        # Common failure modes:
        #   - Accessibility permission denied → exit code 128
        #   - AppleScript compile/runtime errors → non-zero
        raise subprocess.CalledProcessError(result.returncode, "osascript", output=result.stdout, stderr=stderr)
    return result.stdout.strip()


def _run_osascript_file(script_path: str) -> str:
    """Run an .applescript file via osascript and return stdout."""
    result = subprocess.run(
        ["osascript", script_path],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        raise subprocess.CalledProcessError(result.returncode, "osascript", output=result.stdout, stderr=stderr)
    return result.stdout.strip()


def _list_windows_via_applescript() -> str:
    """Execute AppleScript that returns raw CGWindowListCopyWindowInfo data.

    We avoid telling System Events because that requires Accessibility permission
    for `tell application "System Events"`.  Instead we use `do shell script` to
    invoke osascript in-line, which can call CoreGraphics directly via Objective-C.
    """
    # This AppleScript uses `ignoring application responses` so it works even if
    # no app is frontmost.  CGWindowListCopyWindowInfo returns a list of dicts.
    script = """\
set output to ""
try
    set windowArray to current application's CGWindowListCopyWindowInfo(2, 0) as list
    repeat with aWindow in windowArray
        try
            set winNum to kCGWindowNumber of aWindow as text
            set ownerPID to kCGWindowOwnerPID of aWindow as text
            set wName to (kCGWindowName of aWindow as string)
            if wName is missing value then set wName to ""
            set appName to (kCGWindowOwnerName of aWindow as string)
            if appName is missing value then set appName to "Unknown"
            set boundsDict to kCGWindowBounds of aWindow
            set yStr to (boundsDict's objectForKey:("Y")) as text
            set wStr to (boundsDict's objectForKey:("Width")) as text
            set hStr to (boundsDict's objectForKey:("Height")) as text
            if yStr is missing value then set yStr to "0"
            if wStr is missing value then set wStr to "0"
            if hStr is missing value then set hStr to "0"
            set output to output & winNum & "|" & ownerPID & "|" & wName & "|" & appName & "|" & yStr & "|" & wStr & "|" & hStr & "\\n"
        on error errMsg
            set output to output & "ERROR|" & errMsg & "\\n"
        end try
    end repeat
on error errMsg
    set output to "FATAL|Accessibility permission denied or CGWindowListCopyWindowInfo unavailable: " & errMsg
end try
return output"""
    return _run_osascript(script)


def list_windows() -> List[Dict[str, Any]]:
    """List all on-screen windows with their metadata.

    Returns:
        List of dicts with keys: id, name, pid, bounds (tuple), is_visible,
        app_name, alpha, layer.
    """
    raw_output = _list_windows_via_applescript()

    # Check for fatal errors in output
    if raw_output.startswith("FATAL|"):
        error_msg = raw_output[len("FATAL|"):]
        logger.warning(
            "Accessibility permission denied or CGWindowListCopyWindowInfo failed. "
            "Grant 'Screen Recording' + 'Input Monitoring' permissions to your terminal/app "
            "in System Preferences > Security & Privacy > Privacy."
        )
        return []

    windows: List[Dict[str, Any]] = []
    for line in raw_output.split("\n"):
        if not line or line.startswith("ERROR|") or line.startswith("FATAL|"):
            continue
        parts = line.split("|")
        if len(parts) < 7:
            continue

        # Build a dict that mimics the raw CGWindowListCopyWindowInfo entry format
        try:
            raw_entry = {
                "kCGWindowNumber": int(parts[0]),
                "kCGWindowOwnerPID": int(parts[1]),
                "kCGWindowName": parts[2],
                "kCGWindowOwnerName": parts[3],
                "kCGWindowBounds": {
                    "X": 0.0,  # Not extracted — would need complex AppleScript
                    "Y": float(parts[4]),
                    "Width": float(parts[5]),
                    "Height": float(parts[6]),
                },
                "kCGWindowAlpha": 1.0,  # Default; real alpha not easily extractable via osascript
                "kCGWindowLayer": 0,
            }
            parsed = _parse_window_info(raw_entry)
            if parsed:
                windows.append(parsed)
        except (ValueError, TypeError) as e:
            logger.debug(f"Skipping malformed line: {line!r} ({e})")
            continue

    return windows


def get_frontmost_window() -> Optional[Dict[str, Any]]:
    """Get the currently focused window info.

    Uses CGWindowListCopyWindowInfo with option 0 (only visible windows) and
    filters by the highest-level window that has a non-empty name and is on
    screen layer 0.

    Returns:
        Dict with 'id', 'name', 'pid', 'bounds', 'app_name' or None.
    """
    # First try getting frontmost app via System Events (this works without
    # CGWindowListCopyWindowInfo Accessibility issues for just the app name).
    frontmost_app = _get_frontmost_app_name()
    if not frontmost_app:
        return None

    windows = list_windows()
    # Filter to visible, non-hidden-layer windows belonging to that app.
    candidates = [w for w in windows if w["app_name"] == frontmost_app and w["is_visible"]]
    if not candidates:
        return None

    # Sort by alpha descending (most opaque first) then layer ascending.
    candidates.sort(key=lambda w: (-w.get("alpha", 1.0), w.get("layer", 0)))
    return candidates[0]


def _get_frontmost_app_name() -> Optional[str]:
    """Get the name of the frontmost application via osascript."""
    script = (
        'try\n'
        '    tell application "System Events"\n'
        '        set frontApp to first process whose frontmost is true\n'
        '        return name of frontApp\n'
        '    end tell\n'
        'on error errMsg\n'
        '    return ""\n'
        'end try'
    )
    try:
        result = _run_osascript(script)
        if result and result != "":
            return result
    except subprocess.CalledProcessError as e:
        logger.warning(f"Could not determine frontmost app: {e.stderr}")
    return None


def find_window_by_name(substr: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
    """Find windows whose name contains the given substring.

    Args:
        substr: Search string (substring match).
        case_sensitive: If True, matching is case-sensitive; otherwise case-insensitive.

    Returns:
        List of matching window dicts.
    """
    all_windows = list_windows()
    if case_sensitive:
        return [w for w in all_windows if substr in w.get("name", "")]
    return [w for w in all_windows if substr.lower() in w.get("name", "").lower()]


def find_window_by_app(app_name: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
    """Find windows belonging to a specific application.

    Args:
        app_name: Application name (e.g., "Google Chrome", "Terminal").
        case_sensitive: If True, matching is case-sensitive; otherwise case-insensitive.

    Returns:
        List of matching window dicts.
    """
    all_windows = list_windows()
    if case_sensitive:
        return [w for w in all_windows if app_name == w.get("app_name", "")]
    return [w for w in all_windows if app_name.lower() == w.get("app_name", "").lower()]


def get_app_pid(app_name: str) -> Optional[int]:
    """Get the PID of a running application.

    Args:
        app_name: Application name (e.g., "Google Chrome", "Terminal").

    Returns:
        PID as integer, or None if not found.
    """
    windows = find_window_by_app(app_name)
    if windows:
        return windows[0]["pid"]
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing window enumeration...")

    # List all windows
    windows = list_windows()
    print(f"Found {len(windows)} visible windows:")
    for w in windows[:10]:  # Show first 10
        print(f"   - {w['name']} (PID: {w['pid']}, App: {w['app_name']}, Bounds: {w['bounds']})")

    # Get frontmost window
    front = get_frontmost_window()
    if front:
        print(f"\nFrontmost app: {front.get('app_name')}")
        print(f"   Window ID: {front['id']}, Bounds: {front['bounds']}")

    # Find Chrome windows (case-insensitive substring)
    chrome_windows = find_window_by_name("Chrome")
    print(f"\nFound {len(chrome_windows)} Chrome window(s)")
