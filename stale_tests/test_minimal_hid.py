#!/usr/bin/env python3
"""Minimal CGEvent injection test — no classes, raw ctypes only."""
import ctypes, ctypes.util

# Load CoreGraphics
lib = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))

# Bind function signatures BEFORE any calls (critical!)
src_fn = "CGEventSourceCreate"
kbd_fn = "CGEventCreateKeyboardEvent"
post_fn = "CGEventPost"

getattr(lib, src_fn).argtypes = [ctypes.c_uint32, ctypes.c_void_p]
getattr(lib, src_fn).restype = ctypes.c_void_p

getattr(lib, kbd_fn).argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
getattr(lib, kbd_fn).restype = ctypes.c_void_p

kCGHIDEventTap = 2
getattr(lib, post_fn).argtypes = [ctypes.c_int32, ctypes.c_void_p]

print(f"CoreGraphics loaded: {lib}")
print(f"kCGHIDEventTap constant: {kCGHIDEventTap}")

# Create HID event source (0x80000002 = kCGHIDEventTapState)
src = getattr(lib, src_fn)(0x80000002, None)
print(f"Event source created: {hex(src)}")

if not src:
    print("ERROR: Failed to create event source!")
    exit(1)

# Create Space key down event (vkey 0x31 = Space in Carbon)
space_vkey = 0x31
evt_down = getattr(lib, kbd_fn)(src, space_vkey, True)
print(f"Space-down event created: {hex(evt_down)}")

if not evt_down:
    print("ERROR: Failed to create keyboard event!")
    exit(1)

# Post the event to HID tap location
ret = getattr(lib, post_fn)(kCGHIDEventTap, evt_down)
print(f"Posted Space-down to HID tap, return code: {ret}")

# Create Space key up event
evt_up = getattr(lib, kbd_fn)(src, space_vkey, False)
print(f"Space-up event created: {hex(evt_up)}")

if not evt_up:
    print("ERROR: Failed to create keyboard up event!")
    exit(1)

# Post the UP event too (required for proper key handling)
ret_up = getattr(lib, post_fn)(kCGHIDEventTap, evt_up)
print(f"Posted Space-up to HID tap, return code: {ret_up}")

print("\nDONE — check terminal or text editor for space character!")
