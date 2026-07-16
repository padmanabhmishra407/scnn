#!/usr/bin/env python3
"""
Virtual HID MCP Server — exposes mouse/keyboard/window/accessibility tools via Model Context Protocol.

Claude Code spawns this as a subprocess and communicates via JSON-RPC over stdio.
Tools available:
  - list_windows: Enumerate all windows with CGWindowListCopyWindowInfo (no screenshots)
  - get_frontmost_window: Get the currently focused window metadata
  - read_elements: Read accessibility elements from frontmost app (digital UI reading)
  - click_element_by_title: Click a button/element by its title text
  - type_string: Type text into the currently focused element
  - move_mouse_relative: Move mouse by delta (dx, dy)
  - scroll: Scroll wheel in direction

This server avoids screenshots entirely — uses CGWindowListCopyWindowInfo for windows and
AXUIElement for UI elements. Screenshot-based computer-use is only as last resort fallback.
"""

import json
import sys
import os
from typing import Any, Dict, List, Optional


# Add project root to path so imports work when spawned by Claude Code
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.path.dirname(os.path.abspath(__file__)) + "/../..")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from virtual_hid.windows import list_windows as _list_windows, get_frontmost_window as _get_frontmost_window
from virtual_hid.ax_ui_element import (
    enumerate_frontmost_app_elements as _enumerate_ax,
    enumerate_elements_by_app as _enumerate_by_app,
    _get_frontmost_pid,
)


def _send_response(msg_id: Optional[str], result: Any):
    """Send a JSON-RPC response to stdout."""
    response = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": result if not isinstance(result, dict) else {"content": [{"type": "text", "text": json.dumps(result)}]},
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def _send_error(msg_id: Optional[str], code: int, message: str):
    """Send a JSON-RPC error response to stdout."""
    error = {"code": code, "message": message}
    response = {"jsonrpc": "2.0", "id": msg_id, "error": error}
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def _handle_list_windows(params: Dict[str, Any]):
    """List all windows using CGWindowListCopyWindowInfo (no screenshots)."""
    try:
        windows = _list_windows()
        return {"windows": windows}
    except Exception as exc:
        return {"error": str(exc), "note": "Requires Accessibility permissions"}


def _handle_get_frontmost_window(params: Dict[str, Any]):
    """Get the frontmost window metadata."""
    try:
        window = _get_frontmost_window()
        if not window:
            return {"window": None}
        return {"window": window}
    except Exception as exc:
        return {"error": str(exc)}


def _handle_read_elements(params: Dict[str, Any]):
    """Read accessibility elements from the frontmost application (digital UI reading)."""
    try:
        role_filter = params.get("role")  # Optional filter for specific roles like "button"

        elements = _enumerate_ax()

        if role_filter:
            elements = [e for e in elements if e["role"] == role_filter]

        return {"elements": elements, "count": len(elements)}
    except Exception as exc:
        return {"error": str(exc), "note": "Requires Accessibility permissions"}


def _handle_click_element_by_title(params: Dict[str, Any]):
    """Click an element by its title text substring. Returns True if successful."""
    try:
        from virtual_hid._core import _CgAPI
        from virtual_hid.mouse import MouseMixin

        title = params.get("title")
        if not title:
            return {"error": "Missing 'title' parameter"}

        # Find matching elements via AX enumeration.
        all_elements = _enumerate_ax()
        matches = [e for e in all_elements if (e.get("title", "") or "").lower().find(title.lower()) >= 0]

        if not matches:
            return {
                "success": False,
                "message": f"No element found with title matching '{title}'",
                "hint": "Use read_elements to see available labels first.",
            }

        target = matches[0]
        position = target.get("position")
        if not position:
            return {"success": False, "message": f"Element '{target['title']}' has no position."}

        x, y = position

        # Inject mouse click via virtual_hid MouseMixin.
        api = _CgAPI()
        mixin = MouseMixin.__new__(MouseMixin)
        mixin._api = api
        mixin.click(button="left", x=float(x), y=float(y))

        return {"success": True, "element": target}
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {"error": str(exc)}


def _handle_type_string(params: Dict[str, Any]):
    """Type text into the currently focused element via virtual_hid keyboard injection."""
    try:
        from virtual_hid._core import _CgAPI
        from virtual_hid.keyboard import KeyboardMixin

        text = params.get("text", "")
        if not text:
            return {"success": False, "message": "Missing 'text' parameter"}

        api = _CgAPI()
        mixin = KeyboardMixin.__new__(KeyboardMixin)
        mixin._api = api
        # Initialize letter vkey map (normally done in __init__).
        mixin._letter_vkeys = {}
        from virtual_hid._vkeys import get_vkey as _get_vkey_key
        for c in "abcdefghijklmnopqrstuvwxyz":
            upper = c.upper()
            try:
                mixin._letter_vkeys[c] = _get_vkey_key(upper)
            except KeyError:
                pass

        # Use type_string if available, else character-by-character injection.
        if hasattr(mixin, "type_string"):
            mixin.type_string(text)
        else:
            for ch in text:
                mixin.type_char(ch)

        return {"success": True, "typed_text": text}
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {"error": str(exc)}


def _handle_move_mouse_relative(params: Dict[str, Any]):
    """Move mouse by delta (dx, dy). Positive dx=right, positive dy=down."""
    try:
        from virtual_hid.mouse import MouseMixin

        class Mover(MouseMixin):
            def __init__(self):
                self._api = None

        mover = Mover()
        dx = params.get("dx", 0)
        dy = params.get("dy", 0)
        mover.move_mouse(dx=dx, dy=dy)
        return {"success": True, "dx": dx, "dy": dy}
    except Exception as exc:
        return {"error": str(exc)}


def _handle_scroll(params: Dict[str, Any]):
    """Scroll wheel in direction (up/down/left/right)."""
    try:
        from virtual_hid.mouse import MouseMixin

        class Scroller(MouseMixin):
            def __init__(self):
                self._api = None

        scroller = Scroller()
        clicks = params.get("clicks", 1)
        direction = params.get("direction", "down")
        scroller.scroll(clicks=clicks, direction=direction)
        return {"success": True, "clicks": clicks, "direction": direction}
    except Exception as exc:
        return {"error": str(exc)}


# Tool definitions for MCP initialization
TOOL_DEFINITIONS = [
    {
        "name": "list_windows",
        "description": "List all on-screen windows using CGWindowListCopyWindowInfo (no screenshots). Returns window id, name, pid, bounds, app_name.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_frontmost_window",
        "description": "Get the currently focused window metadata including title, position, size, and application name.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_elements",
        "description": "Read all accessibility elements (buttons, text fields, labels) from the frontmost app using AXUIElement. No screenshots — digital UI reading.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_depth": {"type": "integer", "description": "Max recursion depth for element traversal (default 5)"},
                "role": {"type": "string", "description": "Filter by role, e.g. 'AXButton', 'AXTextField'"},
            },
        },
    },
    {
        "name": "click_element_by_title",
        "description": "Click an element by matching its title text. Useful for interacting with buttons, menu items.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title substring to match (case-insensitive)"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "type_string",
        "description": "Type text into the currently focused element or input field.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to type"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "move_mouse_relative",
        "description": "Move mouse by delta (dx, dy). Positive dx moves right, positive dy moves down.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dx": {"type": "integer", "description": "Horizontal delta in points"},
                "dy": {"type": "integer", "description": "Vertical delta in points"},
            },
        },
    },
    {
        "name": "scroll",
        "description": "Scroll mouse wheel. Direction: up, down, left, right.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "clicks": {"type": "integer", "default": 1, "description": "Number of scroll clicks"},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "default": "down"},
            },
        },
    },
]


def _handle_tool_call(tool_name: str, arguments: Dict[str, Any]):
    """Route tool call to the appropriate handler."""
    handlers = {
        "list_windows": _handle_list_windows,
        "get_frontmost_window": _handle_get_frontmost_window,
        "read_elements": _handle_read_elements,
        "click_element_by_title": _handle_click_element_by_title,
        "type_string": _handle_type_string,
        "move_mouse_relative": _handle_move_mouse_relative,
        "scroll": _handle_scroll,
    }

    handler = handlers.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}", "available_tools": list(handlers.keys())}

    try:
        result = handler(arguments)
        return result
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {"error": str(exc)}


def main():
    """Main MCP server loop — read JSON-RPC messages from stdin, respond on stdout."""
    print("[virtual_hid_mcp] Server started", file=sys.stderr)

    # Send initialization notification
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
            method = request.get("method", "")
            msg_id = request.get("id")
            params = request.get("params", {})

            # Handle tool calls
            if method == "tools/call":
                tool_name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = _handle_tool_call(tool_name, arguments)
                _send_response(msg_id, result)

            # Handle list tools (initialization)
            elif method == "tools/list":
                _send_response(msg_id, {"tools": TOOL_DEFINITIONS})

            # Handle initialize request
            elif method == "initialize":
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "serverInfo": {"name": "virtual_hid_mcp", "version": "1.0.0"},
                    },
                }
                # Also send tools/list notification
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.write(json.dumps({
                    "jsonrpc": "2.0",
                    "method": "notifications/tools/list_changed",
                }) + "\n")
                sys.stdout.flush()

            else:
                _send_error(msg_id, -32601, f"Method not found: {method}")

        except Exception as exc:
            print(f"[virtual_hid_mcp] Error handling request: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
