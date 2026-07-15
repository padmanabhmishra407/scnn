#!/usr/bin/env python3
"""Debug CGEvent injection step by step with explicit error reporting."""
import ctypes, ctypes.util, sys

LOG = "/tmp/hid_debug.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{msg}\n")
        f.flush()

try:
    # Step 1: Load CoreGraphics
    cg_path = ctypes.util.find_library("CoreGraphics")
    if not cg_path:
        log("ERROR: CoreGraphics framework NOT found!")
        sys.exit(2)
    lib = ctypes.CDLL(cg_path)
    log(f"Step 1 OK: loaded {cg_path}")

    # Step 2: Verify function pointers exist (raw, no argtypes yet)
    kbd_fn = "CGEventCreateKeyboardEvent"
    post_fn = "CGEventPost"
    src_fn = "CGEventSourceCreate"

    for fn_name in [kbd_fn, post_fn, src_fn]:
        try:
            getattr(lib, fn_name)  # just verify it exists
            log(f"Step 2 OK: {fn_name} found")
        except AttributeError as e:
            log(f"Step 2 FAIL: {fn_name} not found — {e}")

    # Step 3: Create HID event source (kCGHIDEventTapState = 0x80000002)
    try:
        src = lib.CGEventSourceCreate(0x80000002, None)
        log(f"Step 3 OK: CGEventSourceCreate returned {hex(src)}")

        if not src:
            # Try with CFAllocatorDefault (1) instead of None
            kCFAllocatorDefault = 1
            src2 = lib.CGEventSourceCreate(0x80000002, ctypes.c_void_p(kCFAllocatorDefault))
            log(f"Step 3b: tried with alloc=0x1 -> {hex(src2)}")
    except Exception as e:
        log(f"Step 3 FAIL: CGEventSourceCreate raised {e}")

    # Step 4: Set up function signatures properly
    # CGEventRef CGEventCreateKeyboardEvent(CFAllocatorRef alloc, CGKeyCode key, Boolean keyDown)
    lib.CGEventCreateKeyboard_event.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    lib.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p

    # void CGEventPost(CGEventTapLocation tapLoc, CGEventRef event)
    kCGHIDEventTap = 2
    lib.CGEventPost.argtypes = [ctypes.c_int32, ctypes.c_void_p]

    log(f"Step 4 OK: function signatures bound")

    # Step 5: Create a keyboard event (Space key, vkey=0x31)
    space_vkey = 0x31
    evt_down = lib.CGEventCreateKeyboardEvent(src if src else ctypes.c_void_p(0), space_vkey, True)
    log(f"Step 5 OK: created Space-down event at {hex(evt_down)}")

    # Step 6: Post the event
    ret = lib.CGEventPost(kCGHIDEventTap, evt_down)
    log(f"Step 6 OK: CGEventPost returned {ret}")

    # Step 7: Create UP event and post it
    evt_up = lib.CGEventCreateKeyboard_event(src if src else ctypes.c_void_p(0), space_vkey, False)
    ret_up = lib.CGEventPost(kCGHIDEventTap, evt_up)
    log(f"Step 7 OK: Space-up posted, return={ret_up}")

    # Step 8: Also try key 'A' (vkey=0x00) on HID tap
    a_vkey = 0x00
    evt_a_down = lib.CGEventCreateKeyboard_event(src if src else ctypes.c_void_p(0), a_vkey, True)
    ret_a = lib.CGEventPost(kCGHIDEventTap, evt_a_down)
    log(f"Step 8 OK: A-down posted, return={ret_a}")

    log("\nDONE — check terminal for space/A characters!")

except Exception as e:
    import traceback
    log(f"\nFATAL EXCEPTION:\n{e}\n{traceback.format_exc()}")
