#!/usr/bin/env python3
"""
Argparse-based CLI for the Virtual HID package.

Usage:
    python3 -m virtual_hid type "Hello World"
    python3 -m virtual_hid hotkey cmd c
    python3 -m virtual_hid click left 100 200
    python3 -m virtual_hid scroll 3 up
    python3 -m virtual_hid demo

No API keys. No root required. Runs entirely locally via CoreGraphics HID injection.
"""

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="virtual-hid",
        description="Virtual HID device for macOS — injects keyboard/mouse events at the system level.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python3 -m virtual_hid type "Hello World"\n'
            "  python3 -m virtual_hid hotkey cmd c\n"
            "  python3 -m virtual_hid click left 100 200\n"
            "  python3 -m virtual_hid scroll 3 up\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command to run")

    # type: inject text via keyboard injection
    p_type = subparsers.add_parser("type", help="Type a string character by character")
    p_type.add_argument("text", nargs="+", help="Text to type (words separated by spaces)")

    # hotkey: press/release modifier key combination
    p_hotkey = subparsers.add_parser("hotkey", help="Press and release a modifier key combo")
    p_hotkey.add_argument("keys", nargs="+", help="Modifier keys: cmd, ctrl, alt, shift, option, command")

    # click: mouse button at coordinates
    p_click = subparsers.add_parser("click", help="Click a mouse button at (x, y)")
    p_click.add_argument("button", choices=["left", "right", "center"], default="left", help="Mouse button (default: left)")
    p_click.add_argument("x", type=float, help="X coordinate")
    p_click.add_argument("y", type=float, help="Y coordinate")

    # scroll: mouse wheel scrolling
    p_scroll = subparsers.add_parser("scroll", help="Scroll the mouse wheel")
    p_scroll.add_argument("clicks", type=int, default=1, help="Number of scroll clicks (default: 1)")
    p_scroll.add_argument("direction", choices=["up", "down"], default="down", help="Direction (default: down)")

    # demo: run a quick demonstration
    subparsers.add_parser("demo", help="Run a quick demo: type, click, scroll")

    return parser


def main():
    """CLI entry point — dispatches to the appropriate virtual_hid method."""
    parser = _build_parser()
    args = parser.parse_args()

    # Load the VirtualHID singleton (throws if CoreGraphics unavailable)
    try:
        from .. import get_virtual_hid
        hid = get_virtual_hid()
    except ImportError as e:
        print(f"❌ Cannot load virtual_hid: {e}", file=sys.stderr)
        sys.exit(1)

    # Dispatch based on subcommand
    if args.command == "type":
        text = " ".join(args.text)
        print(f"⌨️  Typing: {text}")
        hid.type_string(text)
    elif args.command == "hotkey":
        keys = [k.lower().replace(" ", "") for k in args.keys]
        print(f"⌨️  Hotkey: {' + '.join(keys)}")
        hid.hotkey(*keys)
    elif args.command == "click":
        x, y = float(args.x), float(args.y)
        button = str(args.button).lower() if args.button else "left"
        print(f"🖱️  Clicking at ({x}, {y}) — button: {button}")
        hid.click(button=button, x=x, y=y)
    elif args.command == "scroll":
        clicks = int(args.clicks) if args.clicks else 1
        direction = str(args.direction).lower() if args.direction else "down"
        print(f"🔄 Scrolling {clicks} click(s) {direction}")
        hid.scroll(clicks=clicks, direction=direction)
    elif args.command == "demo":
        print("🎬 Demo mode — typing, clicking, scrolling...\n")
        hid.type_string("SCNN Virtual HID demo\n")
        import time as _time
        _time.sleep(0.5)
        hid.click(button="left", x=100, y=100)
        _time.sleep(0.3)
        hid.scroll(clicks=2, direction="up")
        print("\n✅ Demo complete.")


if __name__ == "__main__":
    main()
