#!/usr/bin/env python3
"""Test HID injection with CGEventSource and all tap locations."""
import ctypes, ctypes.util, time

lib = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
kbd_fn = "CGEventCreateKeyboardEvent"
post_fn = "CGEventPost"
src_fn = "CGEventSourceCreate"

getattr(lib, kbd_fn).argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
getattr(lib, kbd_fn).restype = ctypes.c_void_p
getattr(lib, post_fn).argtypes = [ctypes.c_int32, ctypes.c_void_p]

# Create HID event source (kCGHIDEventTap state = 0x80000002)
src = getattr(lib, src_fn)(0x80000002, None)
print(f"Event source: {hex(src)}")

def press_and_release(vkey, tap_loc=2):
    """Press and release a key at the given tap location."""
    evt_down = getattr(lib, kbd_fn)(src, vkey, True)
    if evt_down:
        getattr(lib, post_fn)(tap_loc, evt_down)
    time.sleep(0.15)
    evt_up = getattr(lib, kbd_fn)(src, vkey, False)
    if evt_up:
        getattr(lib, post_fn)(tap_loc, evt_up)

# Test with all tap locations using Space (vkey 0x31)
for tap in [1, 2]:
    name = "Session" if tap == 1 else "HID"
    print(f"\n--- Tap: {name} (kCG{tap}EventTap), key=Space ---")
    press_and_release(0x31, tap_loc=tap)

# Test with A key (vkey 0x00) on HID tap
print("\n--- HID tap, key=A ---")
press_and_release(0x00, tap_loc=2)

print("\nDONE - check terminal or text editor for typed characters!")
