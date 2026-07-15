#!/usr/bin/env python3
"""
CLI for the Virtual HID device — keyboard & mouse injection.

Usage:
    python3 virtual_hid_cli.py type "Hello World"
    python3 virtual_hid_cli.py click left 100 200
    python3 virtual_hid_cli.py scroll 3 up
    python3 virtual_hid_cli.py hotkey cmd c
    python3 virtual_hid_cli.py demo

No API keys. No root required. Runs entirely locally via CoreGraphics HID injection.
"""

import sys
import time


def _get_hid():
    """Import and return the VirtualHID singleton."""
    try:
        import virtual_hid
        return virtual_hid.get_virtual_hid()
    except ImportError as e:
        print(f"❌ Cannot load virtual_hid: {e}")
        sys.exit(1)


def cmd_type(text: str):
    hid = _get_hid()
    print(f"⌨️  Typing: {text}")
    hid.type_string(text)


def cmd_click(button: str, x: int, y: int):
    hid = _get_hid()
    print(f"⚠️  Mouse click not yet implemented (requires CGEventCreateMouseEvent)", flush=True)


def cmd_scroll(clicks: int, direction: str):
    hid = _get_hid()
    print(f"⚠️  Mouse scroll not yet implemented (requires CGEventCreateMouseEvent)", flush=True)


def cmd_hotkey(*keys):
    hid = _get_hid()
    print(f"⌨️  Hotkey: {' + '.join(keys)}")
    hid.hotkey(*keys)


def cmd_demo():
    hid = _get_hid()
    print("🎬 Demo mode — typing, clicking, scrolling...\n")
    hid.type_string("SCNN Virtual HID demo\n")
    time.sleep(0.5)
    hid.click(button="left", x=100, y=100)
    time.sleep(0.3)
    hid.scroll(clicks=2, direction="up")
    print("\n✅ Demo complete.")


def _usage():
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "type":
        cmd_type(" ".join(sys.argv[2:]))
    elif cmd == "click":
        button = sys.argv[2] if len(sys.argv) > 2 else "left"
        x = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        y = int(sys.argv[4]) if len(sys.argv) > 4 else 0
        cmd_click(button, x, y)
    elif cmd == "scroll":
        clicks = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        direction = sys.argv[3] if len(sys.argv) > 3 else "down"
        cmd_scroll(clicks, direction)
    elif cmd == "hotkey":
        cmd_hotkey(*sys.argv[2:])
    elif cmd == "demo":
        cmd_demo()
    else:
        print(f"❓ Unknown command: {cmd}")
        _usage()


if __name__ == "__main__":
    main()
