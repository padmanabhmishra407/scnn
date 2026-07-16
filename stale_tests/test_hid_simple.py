#!/usr/bin/env python3
"""Skip in CI / subprocess contexts (requires macOS Accessibility permissions)."""
import os as _os
if bool(_os.environ.get('CG_HID_NO_MOUSE', '')):
    print('[skipped — permission-guarded]')
    import sys; sys.exit(0)

import ctypes, ctypes.util

lib = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))

kbd_fn = "CGEventCreateKeyboardEvent"
post_fn = "CGEventPost"
src_fn = "CGEventSourceCreate"

# Bind signatures
getattr(lib, kbd_fn).argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
getattr(lib, kbd_fn).restype = ctypes.c_void_p
getattr(lib, post_fn).argtypes = [ctypes.c_int32, ctypes.c_void_p]

# Create HID event source (kCGHIDEventTap state)
src = getattr(lib, src_fn)(0x80000002, None)
print(f"Source: {hex(src)}")

# Try creating and posting an A key down event at tap=2 (HID)
evt = getattr(lib, kbd_fn)(src, 0x00, True)  # key A, down
print(f"A-down event: {hex(evt) if evt else 'NULL'}")
if evt:
    ret = getattr(lib, post_fn)(2, evt)
    print(f"Posted with return code: {ret}")

# Try session tap (tap=1) too
evt2 = getattr(lib, kbd_fn)(src, 0x31, True)  # key Space, down
print(f"Space-down event: {hex(evt2) if evt2 else 'NULL'}")
if evt2:
    ret2 = getattr(lib, post_fn)(1, evt2)
    print(f"Posted to Session tap with return code: {ret2}")

# Post UP events too (required for proper key handling)
evt_up = getattr(lib, kbd_fn)(src, 0x00, False)  # A up
if evt_up:
    getattr(lib, post_fn)(2, evt_up)
print("Events posted. Check terminal or text editor.")
