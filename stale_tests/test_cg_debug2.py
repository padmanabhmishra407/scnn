#!/usr/bin/env python3
"""Debug CGEvent injection — bind signatures FIRST, then call."""
import ctypes, ctypes.util, sys

LOG = "/tmp/hid_debug2.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{msg}\n")
        f.flush()

try:
    # Load CoreGraphics
    cg_path = ctypes.util.find_library("CoreGraphics")
    if not cg_path:
        raise RuntimeError("CoreGraphics framework NOT found!")
    lib = ctypes.CDLL(cg_path)
    log(f"OK: loaded {cg_path}")

    # Bind ALL function signatures BEFORE any calls (critical for ctypes!)
    # CGEventSourceRef CGEventSourceCreate(CGEventType sourceState, CFAllocatorRef alloc)
    lib.CGEventSourceCreate.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    lib.CGEventSourceCreate.restype = ctypes.c_void_p

    # CGEventRef CGEventCreateKeyboardEvent(CFAllocatorRef alloc, CGKeyCode key, Boolean keyDown)
    kbd_fn = "CGEventCreateKeyboardEvent"  # no underscore!
    getattr(lib, kbd_fn).argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    getattr(lib, kbd_fn).restype = ctypes.c_void_p

    # void CGEventPost(CGEventTapLocation tapLoc, CGEventRef event) -> void
    post_fn = "CGEventPost"
    kCGHIDEventTap = 2
    getattr(lib, post_fn).argtypes = [ctypes.c_int32, ctypes.c_void_p]

    log("OK: all signatures bound")

    log("OK: all signatures bound")

    # Create HID event source (kCGHIDEventTapState = 0x80000002)
    try:
        src = lib.CGEventSourceCreate(0x80000002, None)
        log(f"OK: CGEventSourceCreate returned {hex(src)}")

        if not src:
            # Try with CFAllocatorDefault (kCFAllocatorDefault = 1)
            kCFAllocatorDefault = 1
            src2 = lib.CGEventSourceCreate(0x80000002, ctypes.c_void_p.from_address(kCFAllocatorDefault))
            log(f"OK: tried alloc=1 -> {hex(src2)}")

        # Create Space key down event (vkey 0x31)
        space_vkey = 0x31
        kbd_fn = "CGEventCreateKeyboardEvent"
        evt_down = getattr(lib, kbd_fn)(src if src else ctypes.c_void_p(0), space_vkey, True)
        log(f"OK: created Space-down at {hex(evt_down)}")

        # Post to HID tap location (2)
        post_fn = "CGEventPost"
        ret = getattr(lib, post_fn)(kCGHIDEventTap, evt_down)
        log(f"OK: CGEventPost returned {ret}")

        # Create Space key up event
        evt_up = getattr(lib, kbd_fn)(src if src else ctypes.c_void_p(0), space_vkey, False)
        ret_up = getattr(lib, post_fn)(kCGHIDEventTap, evt_up)
        log(f"OK: posted Space-up, return={ret_up}")

        # Also try key 'A' (vkey 0x00) on HID tap
        a_vkey = 0x00
        evt_a = getattr(lib, kbd_fn)(src if src else ctypes.c_void_p(0), a_vkey, True)
        ret_a = getattr(lib, post_fn)(kCGHIDEventTap, evt_a)
        log(f"OK: posted A-down, return={ret_a}")

    except Exception as e:
        import traceback
        log(f"\nFATAL EXCEPTION in CGEvent injection:\n{e}\n{traceback.format_exc()}")
    log(f"OK: CGEventSourceCreate returned {hex(src)}")

    if not src:
        # Try with CFAllocatorDefault (kCFAllocatorDefault = 1)
        src2 = lib.CGEventSourceCreate(0x80000002, ctypes.c_void_p.from_address(1))
        log(f"OK: tried alloc=1 -> {hex(src2)}")

    # Create Space key down event (vkey 0x31)
    space_vkey = 0x31
    kbd_fn = "CGEventCreateKeyboardEvent"
    evt_down = getattr(lib, kbd_fn)(src if src else ctypes.c_void_p(0), space_vkey, True)
    log(f"OK: created Space-down at {hex(evt_down)}")

    # Post to HID tap location (2)
    post_fn = "CGEventPost"
    ret = getattr(lib, post_fn)(kCGHIDEventTap, evt_down)
    log(f"OK: CGEventPost returned {ret}")

    # Create Space key up event
    evt_up = getattr(lib, kbd_fn)(src if src else ctypes.c_void_p(0), space_vkey, False)
    ret_up = getattr(lib, post_fn)(kCGHIDEventTap, evt_up)
    log(f"OK: posted Space-up, return={ret_up}")

    # Also try key 'A' (vkey 0x00) on HID tap
    a_vkey = 0x00
    evt_a = getattr(lib, kbd_fn)(src if src else ctypes.c_void_p(0), a_vkey, True)
    ret_a = getattr(lib, post_fn)(kCGHIDEventTap, evt_a)
    log(f"OK: posted A-down, return={ret_a}")

    log("\nDONE — check terminal for space/A characters!")

except Exception as e:
    import traceback
    log(f"\nFATAL EXCEPTION:\n{e}\n{traceback.format_exc()}")
    sys.exit(1)
