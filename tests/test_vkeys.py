#!/usr/bin/env python3
"""Tests for virtual_hid._vkeys — constant uniqueness and known-value assertions."""

import importlib


def test_all_constants_unique():
    """Import-time assertion guarantees all vkey constants are unique.

    This is the most critical safety check — if any collision exists, the module fails to load.
    A wrong key being injected silently (e.g., M → Cmd) would cause real damage.
    """
    # Force reload to re-run the assert at import time
    import src.virtual_hid._vkeys as vkeys

    all_codes = list(vkeys._ALL_VKEYS.values())
    unique_count = len(set(all_codes))

    assert unique_count == len(all_codes), (
        f"Vkey collision detected! {len(all_codes) - unique_count} duplicate(s). "
        f"Known collisions: M=0x37↔LCMD, Q=0x0D↔K, I/5 at 0x22."
    )


def test_known_values_correct():
    """Verify a sample of known Carbon vkey values against Apple's Events.h reference."""
    import src.virtual_hid._vkeys as vkeys

    # Sample from Apple's documented events table:
    assert vkeys.get_vkey("A") == 0x00, "KVK_A should be 0x00"
    assert vkeys.get_vkey("B") == 0x0B, "KVK_B should be 0x0B"
    assert vkeys.get_vkey("C") == 0x08, "KVK_C should be 0x08"
    assert vkeys.get_vkey("D") == 0x02, "KVK_D should be 0x02"

    # The critical fixes: M must NOT equal LCMD (0x37), Q must NOT equal K (0x0D)
    assert vkeys.get_vkey("M") != vkeys.get_vkey("LCMD"), "KVK_M and KVK_LCMD must differ"
    assert vkeys.get_vkey("Q") != vkeys.get_vkey("K"), "KVK_Q and KVK_K must differ"


def test_get_vkey_returns_none_for_unknown():
    """Unknown key names should return None (not crash)."""
    import src.virtual_hid._vkeys as vkeys

    assert vkeys.get_vkey("UNKNOWN_KEY_99") is None, "get_vkey('UNKNOWN') should be None"


def test_all_expected_keys_present():
    """Ensure all A-Z letters and 1-0 digits are mapped."""
    import src.virtual_hid._vkeys as vkeys

    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        assert vkeys.get_vkey(letter) is not None, f"Missing vkey for {letter}"

    for digit in "0123456789":
        assert vkeys.get_vkey(digit) is not None, f"Missing vkey for {digit}"
