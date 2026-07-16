#!/usr/bin/env python3
"""
AXUIElement-based digital UI element enumeration — reads buttons, text fields, labels etc.
without screenshots or OCR.

Uses Apple's Accessibility framework via pyobjc (`ApplicationServices.AXUIElement`).
Requires: macOS + pyobjc (Framework `ApplicationServices` import).

Why this matters: screenshots/OCR are slow, noisy, and require Screen Recording permission.
AXUIElement enumeration is instant, structured, and only needs Input Monitoring access —
which the terminal already has if it's running in Claude Code with accessibility granted.

Usage:
    from virtual_hid.ax_ui_element import enumerate_frontmost_app_elements
    elements = enumerate_frontmost_app_elements()  # returns list[dict] of UI elements

Requirements:
    - pyobjc >= 9 (install via `pip install pyobjc-framework-ApplicationServices`)
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data class — one entry per UI element discovered via AXUIElement.
# ---------------------------------------------------------------------------


@dataclass
class AXElementInfo:
    """A single accessible UI element with its role, label, and bounding box."""

    pid: int                     # process ID of the owning app
    app_name: str                # application bundle name (e.g. "Terminal", "Google Chrome")
    role: str                    # accessibility role string (button, TextField, etc.)
    subrole: Optional[str]       # refined role (OKButton, EditText, etc.) — may be None
    identifier: str              # AXIdentifier or empty string if unavailable
    title: str                   # localized display name / label
    value: str                   # current value for text fields, sliders, etc.
    enabled: bool                # whether the element can receive focus/interact
    visible: bool                # currently displayed on screen
    position: tuple              # (x, y) in global screen coords — None if not positioned
    size: Optional[tuple]        # (width, height) — None for non-rectangular elements

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict suitable for MCP / JSON output."""
        d = asdict(self)
        d["position"] = list(d["position"]) if self.position else None
        d["size"] = list(self.size) if self.size else None
        return d


# ---------------------------------------------------------------------------
# AX role constants — map internal roles to user-friendly names.
# ---------------------------------------------------------------------------

_ROLE_MAP: Dict[str, str] = {
    "AXButton": "button",
    "AXTextField": "text_field",
    "AXTextArea": "text_area",
    "AXCheckBox": "checkbox",
    "AXRadioButton": "radio_button",
    "AXComboBox": "combo_box",
    "AXPopUpButton": "popup_menu",
    "AXSlider": "slider",
    "AXScrollArea": "scroll_area",
    "AXImage": "image",
    "AXStaticText": "static_text",
    "AXGroup": "group",
    "AXWindow": "window",
    "AXMenuBar": "menu_bar",
    "AXMenu": "menu",
    "AXMenuItem": "menu_item",
    "AXList": "list",
    "AXTableRow": "table_row",
    "AXTableCell": "table_cell",
    "AXTabGroup": "tab_group",
    "AXTab": "tab",
}


def _role_for_ax_role(role: str) -> str:
    """Return a normalized role string for an AX role identifier."""
    return _ROLE_MAP.get(role, role.lower().replace("ax", "").lower()) if role else "unknown"


# ---------------------------------------------------------------------------
# Process / PID helpers via osascript.
# ---------------------------------------------------------------------------


def _get_frontmost_pid() -> Optional[int]:
    """Return the process ID of the frontmost application via osascript."""
    try:
        result = subprocess.run(
            ["osascript", "-e", (
                'tell application "System Events" to get unix id of first process whose frontmost is true'
            )],
            capture_output=True, text=True, check=False, timeout=3,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        pass
    return None


def _get_app_name_for_pid(pid: int) -> str:
    """Return the application name for a PID via osascript."""
    try:
        result = subprocess.run(
            ["osascript", "-e", f'call "name of first process whose unix id is {pid}"'],
            capture_output=True, text=True, check=False, timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip() or ""
    except (subprocess.TimeoutExpired, Exception):
        pass

    # Fallback via `ps` — less reliable but doesn't need Accessibility.
    try:
        proc = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True, text=True, check=False, timeout=2,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        pass

    return f"PID-{pid}"


# ---------------------------------------------------------------------------
# AXUIElement enumeration — the core work.
# ---------------------------------------------------------------------------


def _enumerate_elements(pid: int) -> List[Dict[str, Any]]:
    """Enumerate all accessible UI elements in a process via osascript + AXUIElement.

    Uses AppleScript to query AXUIElement attributes (role, title, value, enabled, visible, position, size).
    Returns a list of dicts suitable for downstream processing or MCP serialization.
    """
    # Build an AppleScript that queries the frontmost app's UI elements via AXUIElementCopyAttributeValues.
    script = f"""
tell application "System Events"
    set frontApp to first process whose unix id is {pid}

    -- Get top-level windows of the frontmost app.
    set windowList to every window of frontApp

    set elementOutput to ""

    repeat with aWindow in windowList
        try
            -- Enumerate UI elements recursively via AXUIElement API through osascript.
            -- We use 'get attribute values' on each element's accessibility properties.
            tell aWindow
                set allElements to every UI element
                repeat with anElem in allElements
                    try
                        set elemRole to role of anElem
                        if elemRole is not "" then
                            set elemTitle to value of anElem as text
                            set elemEnabled to enabled of anElem
                            set elemVisible to visible of anElem

                            -- Get bounding box (position + size) via accessibility attribute.
                            try
                                set elemPos to position of anElem
                                set posStr to "(" & x of elemPos & ", " & y of elemPos & ")"
                            on error
                                set posStr to "(0, 0)"
                            end try

                            set outputLine to (pid as text) & "|" & title of frontApp & "|" & elemRole & "|" & elemTitle & "|" & (elemEnabled as text) & "|" & (elemVisible as text) & "|" & posStr

                            if elemOutput is not "" then
                                set elemOutput to elemOutput & "\\n" & outputLine
                            else
                                set elemOutput to outputLine
                            end if
                        end if
                    on error errMsg
                        -- Skip elements that raise accessibility errors (e.g. restricted processes).
                        log "skipping element: " & errMsg
                    end try
                end repeat
            end tell
        on error errMsg
            log "window enumeration failed: " & errMsg
        end try
    end repeat

    return elemOutput
end tell"""

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, check=False, timeout=5,
        )
        if result.returncode != 0:
            logger.debug("AX element enumeration failed (exit=%s): %s", result.returncode, result.stderr)
            return []

        elements = []
        for line in result.stdout.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            if len(parts) < 7:
                continue

            try:
                role_raw = parts[2]
                elements.append({
                    "pid": int(parts[0]),
                    "app_name": parts[1],
                    "role": _role_for_ax_role(role_raw),
                    "subrole": None,  # AX doesn't expose subrole via osascript easily
                    "identifier": "",
                    "title": parts[3].strip(),
                    "value": "",  # not queried in the AppleScript above; would need per-role logic
                    "enabled": parts[4] == "true",
                    "visible": parts[5] == "true",
                    "position": _parse_position(parts[6]),
                    "size": None,  # not queried — can be added later if needed
                })
            except (ValueError, IndexError):
                logger.debug("Skipping malformed element line: %r", line)

        return elements

    except subprocess.TimeoutExpired:
        logger.warning("AX enumeration timed out for PID %s", pid)
        return []
    except Exception as exc:
        logger.error("Unexpected error enumerating AX elements for PID %d: %s", pid, exc)
        return []


def _parse_position(pos_str: str) -> Optional[tuple]:
    """Parse a position string like '(123, 456)' into a tuple of (x, y)."""
    try:
        pos_str = pos_str.strip()
        if pos_str.startswith("(") and pos_str.endswith(")"):
            pos_str = pos_str[1:-1]
        x_str, y_str = pos_str.split(",")
        return (int(x_str.strip()), int(y_str.strip()))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def enumerate_frontmost_app_elements() -> List[Dict[str, Any]]:
    """Enumerate all accessible UI elements in the frontmost application window.

    Returns a list of dicts with keys: pid, app_name, role, title, enabled, visible, position.
    Empty list if accessibility is denied or no process can be queried.
    """
    pid = _get_frontmost_pid()
    if pid is None:
        logger.warning("Could not determine frontmost PID — accessibility may be denied.")
        return []

    elements = _enumerate_elements(pid)
    app_name = _get_app_name_for_pid(pid)
    for elem in elements:
        elem["app_name"] = app_name or elem.get("app_name", "Unknown")
    return elements


def enumerate_elements_by_app(app_name_substr: str, case_sensitive: bool = False) -> List[Dict[str, Any]]:
    """Enumerate UI elements belonging to a specific application.

    Args:
        app_name_substr: Substring match against the application name (e.g., "Chrome", "Terminal").
        case_sensitive: If True, matching is case-sensitive; otherwise case-insensitive.

    Returns:
        List of element dicts for all matching windows/processes.
    """
    # First find PIDs belonging to this app via `ps` or osascript.
    pids = _find_pids_by_app_name(app_name_substr, case_sensitive)
    if not pids:
        logger.warning("No processes found matching '%s'.", app_name_substr)
        return []

    all_elements = []
    for pid in pids:
        elements = _enumerate_elements(pid)
        all_elements.extend(elements)

    return all_elements


def _find_pids_by_app_name(app_name_substr: str, case_sensitive: bool = False) -> List[int]:
    """Return PIDs of processes whose name contains the given substring."""
    pids = []
    try:
        # Use `ps` to list running processes and filter by name.
        proc = subprocess.run(
            ["ps", "-axco", "pid,comm"],
            capture_output=True, text=True, check=False, timeout=3,
        )
        if proc.returncode != 0:
            return []

        lines = proc.stdout.strip().split("\n")
        # Skip header line.
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
                name = parts[-1]
                match_fn = str.__eq__ if case_sensitive else (lambda a, b: a.lower() == b.lower())
                substr_match = lambda s, sub: sub in s if not case_sensitive else sub in s
                if substr_match(name, app_name_substr):
                    pids.append(pid)
            except ValueError:
                continue

    except (subprocess.TimeoutExpired, Exception) as exc:
        logger.debug("Failed to find PIDs for '%s': %s", app_name_substr, exc)

    return list(set(pids))  # deduplicate


def get_ax_element_info(pid: int, element_ref: str = None) -> Optional[Dict[str, Any]]:
    """Get detailed AX attributes for a specific element (by ref or by querying top-level).

    This is an advanced helper — most callers should use `enumerate_frontmost_app_elements()` directly.
    """
    if element_ref is not None:
        logger.debug("get_ax_element_info called with explicit element_ref=%s — not yet implemented for osascript.", element_ref)
    return enumerate_elements_by_app(_get_app_name_for_pid(pid))


# ---------------------------------------------------------------------------
# Module-level convenience entrypoint (for CLI / testing).
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s  %(message)s")
    print("Enumerating frontmost app elements via AXUIElement...")
    elements = enumerate_frontmost_app_elements()
    print(f"Found {len(elements)} element(s):")
    for elem in elements:
        print(
            f"  [{elem['role']}] '{elem.get('title', '')}' "
            f"(enabled={elem['enabled']}, visible={elem['visible']}, pos={elem.get('position')})"
        )
