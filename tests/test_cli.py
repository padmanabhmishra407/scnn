#!/usr/bin/env python3
"""Tests for virtual_hid.cli — verify argparse subcommand parsing without running HID injection."""

import subprocess
import sys


def test_help_shows_subcommands():
    """The --help flag should list all available subcommands: type, hotkey, click, scroll, demo."""
    result = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '/Users/padmanabhmishra/Documents/scnn/src'); from virtual_hid.cli.__main__ import _build_parser; print(_build_parser().format_help())"],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"Help command failed with code {result.returncode}"
    help_text = result.stdout.lower()

    # Check that all subcommands appear in the help output
    for cmd in ("type", "hotkey", "click", "scroll", "demo"):
        assert cmd in help_text, f"'{cmd}' not found in --help output"


def test_type_subcommand_parses():
    """The 'type' subcommand should parse text arguments correctly."""
    result = subprocess.run(
        [sys.executable, "-c", """
import sys; sys.path.insert(0, '/Users/padmanabhmishra/Documents/scnn/src')
from virtual_hid.cli.__main__ import _build_parser
parser = _build_parser()
args = parser.parse_args(['type', 'Hello', 'World'])
assert args.command == 'type'
assert args.text == ['Hello', 'World']
print("OK: type subcommand parsed correctly")
"""],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"Type parsing failed: {result.stderr}"
    assert "OK:" in result.stdout


def test_hotkey_subcommand_parses():
    """The 'hotkey' subcommand should parse modifier key names correctly."""
    result = subprocess.run(
        [sys.executable, "-c", """
import sys; sys.path.insert(0, '/Users/padmanabhmishra/Documents/scnn/src')
from virtual_hid.cli.__main__ import _build_parser
parser = _build_parser()
args = parser.parse_args(['hotkey', 'cmd', 'c'])
assert args.command == 'hotkey'
assert args.keys == ['cmd', 'c']
print("OK: hotkey subcommand parsed correctly")
"""],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"Hotkey parsing failed: {result.stderr}"
    assert "OK:" in result.stdout


def test_click_subcommand_parses_coords():
    """The 'click' subcommand should parse button and coordinates correctly."""
    result = subprocess.run(
        [sys.executable, "-c", """
import sys; sys.path.insert(0, '/Users/padmanabhmishra/Documents/scnn/src')
from virtual_hid.cli.__main__ import _build_parser
parser = _build_parser()
args = parser.parse_args(['click', 'left', '100.5', '200.7'])
assert args.command == 'click'
assert args.button == 'left'
assert abs(args.x - 100.5) < 0.001
assert abs(args.y - 200.7) < 0.001
print("OK: click subcommand parsed correctly")
"""],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"Click parsing failed: {result.stderr}"
    assert "OK:" in result.stdout


def test_scroll_subcommand_parses_direction():
    """The 'scroll' subcommand should parse direction correctly."""
    result = subprocess.run(
        [sys.executable, "-c", """
import sys; sys.path.insert(0, '/Users/padmanabhmishra/Documents/scnn/src')
from virtual_hid.cli.__main__ import _build_parser
parser = _build_parser()
args = parser.parse_args(['scroll', '5', 'up'])
assert args.command == 'scroll'
assert args.clicks == 5
assert args.direction == 'up'
print("OK: scroll subcommand parsed correctly")
"""],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"Scroll parsing failed: {result.stderr}"
    assert "OK:" in result.stdout


def test_demo_subcommand_parses():
    """The 'demo' subcommand should parse with no extra args."""
    result = subprocess.run(
        [sys.executable, "-c", """
import sys; sys.path.insert(0, '/Users/padmanabhmishra/Documents/scnn/src')
from virtual_hid.cli.__main__ import _build_parser
parser = _build_parser()
args = parser.parse_args(['demo'])
assert args.command == 'demo'
print("OK: demo subcommand parsed correctly")
"""],
        capture_output=True, text=True
    )

    assert result.returncode == 0, f"Demo parsing failed: {result.stderr}"
    assert "OK:" in result.stdout


if __name__ == "__main__":
    # Run all tests manually if executed directly
    test_help_shows_subcommands()
    test_type_subcommand_parses()
    test_hotkey_subcommand_parses()
    test_click_subcommand_parses()
    test_scroll_subcommand_parses()
    test_demo_subcommand_parses()
    print("✅ All CLI tests passed!")
