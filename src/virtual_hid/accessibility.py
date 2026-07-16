#!/usr/bin/env python3
"""
Digital UI Element Reader — reads accessibility attributes without screenshots.

Uses Apple's Accessibility framework via pyobjc (AXUIElement) to enumerate buttons, text fields,
labels, checkboxes, and other interactive elements from any frontmost application. This avoids the
heavy cost of continuous screen captures while providing structured element data for automation.

Requires:
  - macOS with Accessibility permission granted to Python terminal/app
  - pyobjc framework (pip install pyobjc-framework-Accessibility)

Usage:
    from virtual_hid.accessibility import read_frontmost_elements
    elements = read_frontmost_elements()
    # Returns list of dicts with role, label, position, size, enabled, etc.
"""

import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


def _require_accessibility_framework():
    """Import and return the AXUIElement reference for the frontmost app."""
    try:
        from AppKit import NSWorkspace
        from Accessibility import (
            AXUIElementCreateApplication,
            AXUIElementCopyAttributeValue,
            kAXFocusedWindowAttribute,
            kAXWindowsAttribute,
            kAXRoleAttribute,
            kAXTitleAttribute,
            kAXValueAttribute,
            kAXEnabledAttribute,
            kAXPositionAttribute,
            kAXSizeAttribute,
            kAXMainWindowAttribute,
        )

        workspace = NSWorkspace.sharedWorkspace()
        frontmost_app = workspace.frontmostApplication()
        if not frontmost_app:
            return None

        app_pid = frontmost_app.processIdentifier()
        ax_app = AXUIElementCreateApplication(app_pid)
        return ax_app, {
            "kAXFocusedWindowAttribute": kAXFocusedWindowAttribute,
            "kAXWindowsAttribute": kAXWindowsAttribute,
            "kAXRoleAttribute": kAXRoleAttribute,
            "kAXTitleAttribute": kAXTitleAttribute,
            "kAXValueAttribute": kAXValueAttribute,
            "kAXEnabledAttribute": kAXEnabledAttribute,
            "kAXPositionAttribute": kAXPositionAttribute,
            "kAXSizeAttribute": kAXSizeAttribute,
            "kAXMainWindowAttribute": kAXMainWindowAttribute,
        }
    except ImportError as exc:
        logger.debug("Accessibility framework not available: %s", exc)
        return None


def read_frontmost_elements() -> List[Dict[str, Any]]:
    """Read all accessibility elements from the frontmost application.

    Returns a list of dicts with keys: role, title, value, enabled, position (x,y), size (w,h).
    Elements are traversed recursively to capture nested UI components.
    """
    ax_data = _require_accessibility_framework()
    if not ax_data:
        return []

    ax_app, attrs = ax_data

    # Get the main window of the frontmost app
    main_window_ref = AXUIElementCopyAttributeValue(ax_app, attrs["kAXMainWindowAttribute"])
    if not main_window_ref:
        logger.debug("No main window found for frontmost app")
        return []

    elements = _traverse_ax_element(main_window_ref, attrs)
    return elements


def read_elements_from_pid(pid: int) -> List[Dict[str, Any]]:
    """Read all accessibility elements from a specific application by PID."""
    try:
        from Accessibility import AXUIElementCreateApplication

        ax_app = AXUIElementCreateApplication(pid)
        if not ax_app:
            return []

        workspace_module = __import__("AppKit")
        NSWorkspace = workspace_module.NSWorkspace

        attrs = {
            "kAXMainWindowAttribute": getattr(NSWorkspace, "kAXMainWindowAttribute", None),
            "kAXRoleAttribute": getattr(NSWorkspace, "kAXRoleAttribute", None),
            "kAXTitleAttribute": getattr(NSWorkspace, "kAXTitleAttribute", None),
        }

        if not all(attrs.values()):
            logger.debug("Accessibility attributes unavailable")
            return []

        main_window_ref = AXUIElementCopyAttributeValue(ax_app, attrs["kAXMainWindowAttribute"])
        if not main_window_ref:
            return []

        elements = _traverse_ax_element(main_window_ref, attrs)
        return elements

    except Exception as exc:
        logger.debug("Failed to read elements from PID %d: %s", pid, exc)
        return []


def _traverse_ax_element(ax_element, attrs: Dict[str, Any], depth: int = 0, max_depth: int = 10):
    """Recursively traverse an AXUIElement and its children to collect all UI elements."""
    if depth > max_depth:
        return []

    elements = []

    # Get the role of this element (button, text field, window, etc.)
    role_value = AXUIElementCopyAttributeValue(ax_element, attrs["kAXRoleAttribute"])
    if not role_value or isinstance(role_value, tuple):  # tuple means error/failure
        return elements

    role = str(role_value) if role_value else "Unknown"

    # Get title/label (most UI elements have a descriptive name)
    title_value = AXUIElementCopyAttributeValue(ax_element, attrs["kAXTitleAttribute"])
    title = str(title_value) if title_value and not isinstance(title_value, tuple) else ""

    # Get value (for text fields, sliders, etc.)
    value_value = AXUIElementCopyAttributeValue(ax_element, attrs["kAXValueAttribute"])
    value = str(value_value) if value_value and not isinstance(value_value, tuple) else None

    # Get enabled state
    enabled_value = AXUIElementCopyAttributeValue(ax_element, attrs["kAXEnabledAttribute"])
    enabled = bool(enabled_value) if enabled_value is not None and not isinstance(enabled_value, tuple) else True

    # Get position (x, y)
    position_ref = AXUIElementCopyAttributeValue(ax_element, attrs["kAXPositionAttribute"])
    position = None
    if position_ref and not isinstance(position_ref, tuple):
        try:
            from AppKit import NSMakePoint
            if hasattr(position_ref, "location"):
                location = position_ref.location()
                position = (float(location.x), float(location.y))
            elif hasattr(position_ref, "x") and hasattr(position_ref, "y"):
                position = (float(position_ref.x), float(position_ref.y))
        except Exception:
            pass

    # Get size (width, height)
    size_ref = AXUIElementCopyAttributeValue(ax_element, attrs["kAXSizeAttribute"])
    size = None
    if size_ref and not isinstance(size_ref, tuple):
        try:
            from AppKit import NSMakeSize
            if hasattr(size_ref, "size"):
                sz = size_ref.size()
                size = (float(sz.width), float(sz.height))
            elif hasattr(size_ref, "width") and hasattr(size_ref, "height"):
                size = (float(size_ref.width), float(size_ref.height))
        except Exception:
            pass

    # Build element dict
    element_dict = {
        "role": role,
        "title": title,
        "value": value,
        "enabled": enabled,
        "position": position,
        "size": size,
        "depth": depth,
    }
    elements.append(element_dict)

    # Recursively traverse children (if this element has any)
    children_value = AXUIElementCopyAttributeValue(ax_element, "AXChildren")
    if children_value and not isinstance(children_value, tuple):
        try:
            for child in children_value:
                child_elements = _traverse_ax_element(child, attrs, depth + 1, max_depth)
                elements.extend(child_elements)
        except Exception as exc:
            logger.debug("Failed to traverse children of %s: %s", role, exc)

    return elements


def find_element_by_title(title_substr: str, case_sensitive: bool = False) -> Optional[Dict[str, Any]]:
    """Find the first element whose title contains the given substring."""
    elements = read_frontmost_elements()
    for elem in elements:
        if title_substr.lower() in elem["title"].lower() if not case_sensitive else title_substr in elem["title"]:
            return elem
    return None


def find_element_by_role(role: str) -> List[Dict[str, Any]]:
    """Find all elements with the given role (e.g., 'AXButton', 'AXTextField')."""
    elements = read_frontmost_elements()
    return [elem for elem in elements if elem["role"] == role]


def click_element_at(position: tuple) -> bool:
    """Click at screen coordinates using virtual_hid mouse injection."""
    try:
        from .mouse import MouseMixin

        class Clicker(MouseMixin):
            def __init__(self):
                self._api = None  # Not needed for static method calls

        Clicker.click(Clicker(), x=position[0], y=position[1])
        return True
    except Exception as exc:
        logger.debug("Failed to click at %s: %s", position, exc)
        return False


def type_into_element(element: Dict[str, Any], text: str) -> bool:
    """Click on an element and type text into it."""
    if not element.get("position"):
        logger.warning("Element has no position; cannot focus for typing")
        return False

    x, y = element["position"]
    success = click_element_at((x, y))
    if not success:
        return False

    try:
        import time
        time.sleep(0.1)  # Brief delay to ensure focus

        from .keyboard import KeyboardMixin

        class Typer(KeyboardMixin):
            def __init__(self):
                self._api = None

        typer = Typer()
        for char in text:
            typer.type_char(char)
            time.sleep(0.02)  # Small delay between chars for reliability

        return True
    except Exception as exc:
        logger.debug("Failed to type into element: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Convenience module-level functions for MCP server integration
# ---------------------------------------------------------------------------


def get_all_elements() -> List[Dict[str, Any]]:
    """Public API: read all elements from the frontmost application."""
    return read_frontmost_elements()


def list_buttons() -> List[Dict[str, Any]]:
    """Public API: find all button elements."""
    return find_element_by_role("AXButton")


def list_text_fields() -> List[Dict[str, Any]]:
    """Public API: find all text field elements."""
    return find_element_by_role("AXTextField")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Reading frontmost app accessibility elements...")

    elements = read_frontmost_elements()
    print(f"Found {len(elements)} elements:")
    for elem in elements[:20]:  # Show first 20
        pos_str = f"@({elem['position'][0]:.0f},{elem['position'][1]:.0f})" if elem["position"] else "no position"
        print(f"  - {elem['role']:15s} | {elem['title'][:40]:40s} | enabled={elem['enabled']} | {pos_str}")
