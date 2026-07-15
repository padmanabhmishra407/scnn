#!/usr/bin/env python3
"""Test CGEvent injection — writes log to file for verification."""
import ctypes, ctypes.util, sys

LOG = "/tmp/hid_test.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{msg}\n")
        f.flush()

try:
    lib = ctypes.CDLL(ctypes.util.find_library("CoreGraphics"))
    kbd_fn = "CGEventCreateKeyboardEvent"
    post_fn = "CGEventPost"
    src_fn = "CGEventSourceCreate"

    # CGEventSourceCreate(CGEventType sourceState, CFAllocatorRef alloc) -> CGEventSourceRef
    getattr(lib, src_fn).argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    getattr(lib, src_fn).restype = ctypes.c_void_p

    # CGEventCreateKeyboardEvent(CFAllocatorRef alloc, CGKeyCode key, Boolean keyDown) -> CGEventRef
    getattr(lib, kbd_fn).argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    getattr(lib, kbd_fn).restype = ctypes.c_void_p

    # CGEventPost(CGEventTapLocation tapLoc, CGEventRef event) -> void
    getattr(lib, post_fn).argtypes = [ctypes.c_int32, ctypes.c_void_p]

    log(f"CG loaded: {lib}")

    src = getattr(lib, src_fn)(0x80000002, None)
    log(f"Source created: {hex(src)}")

    if not src:
        log("FAILED to create source!")
        sys.exit(1)

    # Try Space key (vkey 0x31) down + up on both tap locations
    for tap in [1, 2]:
        tap_name = "Session" if tap == 1 else "HID"
        log(f"\n--- Tap: {tap_name} (kCG{tap}EventTap) ---")
        for down in [True, False]:
            evt = getattr(lib, kbd_fn)(src, 0x31, down)
            if not evt:
                log(f"  FAIL create event vk=0x31 down={down}")
                continue
            ret = getattr(lib, post_fn)(tap, evt)
            log(f"  post(tap={tap}, vk=0x31, down={down}) -> {ret}")

    # Also try key A (vkey 0x00) on HID tap
    log("\n--- HID tap, key=A ---")
    evt_a = getattr(lib, kbd_fn)(src, 0x00, True)
    if evt_a:
        ret = getattr(lib, post_fn)(2, evt_a)
        log(f"  A-down -> {ret}")

    log("\nDONE — check terminal for space/A characters")
except Exception as e:
    log(f"EXCEPTION: {e}")
    import traceback
    log(traceback.format_exc())
