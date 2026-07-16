# Graph Report - scnn  (2026-07-17)

## Corpus Check
- 44 files · ~33,206 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 634 nodes · 965 edges · 46 communities (43 shown, 3 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 46 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `797b6a05`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- VirtualHID
- KeyboardMixin
- screen.py
- tracker.py
- SCNN Virtual HID — Phase 1 & Phase 2 Implementation Complete Report
- windows.py
- __init__.py
- accessibility.py
- ax_ui_element.py
- mcp_server.py
- live_feed.py
- ui_interactor.py
- _CgAPI
- test_ui_interactor.py
- MouseMixin
- test_live_feed.py
- LiveDisplayFeed
- identify_clickable_elements
- test_cli.py
- SCNN - Self-Improving Cybernetic Neural Network Research Project
- Protocol Rules (Non-Negotiable)
- Computer Use Agent — Setup Guide
- ocr_image
- BoundingBox
- handle_modal_dialog
- pure_airllm.py
- ClickableElement
- virtual_hid_cli.py
- SCNN - Self-Improving Cybernetic Neural Network
- TestMouseMixin
- test_vkeys.py
- ._bind_sigs
- /handoff Command
- /handoff Skill
- CGPoint
- capture_screen
- main
- _inject_mouse_click
- press_and_release
- install_agentworld.sh
- git_helper.sh

## God Nodes (most connected - your core abstractions)
1. `_CgAPI` - 20 edges
2. `LiveDisplayFeed` - 20 edges
3. `KeyboardMixin` - 17 edges
4. `ClickableElement` - 16 edges
5. `capture_screen()` - 15 edges
6. `VirtualHID` - 15 edges
7. `VirtualHID` - 13 edges
8. `MouseMixin` - 13 edges
9. `BoundingBox` - 13 edges
10. `click_element()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `TestMouseMixin` --uses--> `CGPoint`  [INFERRED]
  tests/test_mouse.py → src/virtual_hid/_core.py
- `test_vision_agent_uses_live_feed()` --calls--> `VisionAgent`  [INFERRED]
  tests/test_live_feed.py → src/virtual_hid/agent.py
- `test_feed_provides_continuous_frames()` --calls--> `LiveDisplayFeed`  [INFERRED]
  tests/test_live_feed.py → src/virtual_hid/live_feed.py
- `test_feed_region_capture()` --calls--> `LiveDisplayFeed`  [INFERRED]
  tests/test_live_feed.py → src/virtual_hid/live_feed.py
- `test_feed_stop_cleanly()` --calls--> `LiveDisplayFeed`  [INFERRED]
  tests/test_live_feed.py → src/virtual_hid/live_feed.py

## Import Cycles
- None detected.

## Communities (46 total, 3 thin omitted)

### Community 0 - "VirtualHID"
Cohesion: 0.08
Nodes (23): _CgAPI, get_virtual_hid(), _load_cg(), Press a key down via CGPostKeyboardEvent., Release a key up via CGPostKeyboardEvent., Injects keyboard and mouse events at the system HID level via CoreGraphics., Press (down) a virtual key code., Release (up) a virtual key code. (+15 more)

### Community 1 - "KeyboardMixin"
Cohesion: 0.08
Nodes (20): KeyboardMixin, Type a string character by character. Handles uppercase and common symbols., Press and hold a modifier key combination (e.g. press_hotkey('cmd', 'c'))., Release a previously pressed hotkey combination., Press and release a key combination (convenience wrapper)., Press a key then release it (single keystroke). Accepts name or int., Mixin providing keyboard injection via CGPostKeyboardEvent., Resolve a modifier key name to its vkey constant. (+12 more)

### Community 2 - "screen.py"
Cohesion: 0.10
Nodes (28): _bytes_to_image(), capture_screen_raw(), capture_window(), _capture_window_ctypes(), _display_name_for_id(), DisplayInfo, _enumerate_displays_cg(), _enumerate_displays_system_profiler() (+20 more)

### Community 3 - "tracker.py"
Cohesion: 0.11
Nodes (28): _handle_message(), main(), Process an incoming JSON-RPC request and return a response dict., Write a JSON-RPC response as a single line to stdout (MCP stdio protocol)., Send a notification (no id, no response expected)., Main loop: read JSON-RPC messages from stdin, respond on stdout., Return the list of tool definitions for MCP initialization., _send_notification() (+20 more)

### Community 4 - "SCNN Virtual HID — Phase 1 & Phase 2 Implementation Complete Report"
Cohesion: 0.07
Nodes (28): BPE Tokenization Test:, Critical Bug Fixes Applied:, Documentation:, Edge-Case UI Interaction Handler (`ui_interactor.py`), 🎯 Executive Summary, 🤖 Fan-Out Subagent Orchestration, Files Created/Modified:, 📊 Final Deliverables (+20 more)

### Community 5 - "windows.py"
Cohesion: 0.12
Nodes (25): _check_accessibility_permission(), find_window_by_app(), find_window_by_name(), get_app_pid(), _get_frontmost_app_name(), get_frontmost_window(), _is_permission_granted(), list_windows() (+17 more)

### Community 6 - "__init__.py"
Cohesion: 0.14
Nodes (18): Action, Observation, Execute an action via virtual_hid injection.          Args:             action:, High-level interaction loop: observe → act based on prompt.          This is a s, Structured representation of what the agent sees on screen., Structured representation of an action the agent wants to execute., Closed-loop agent that sees, thinks, and acts on the UI.      This is the core o, Capture and parse the current screen state using the live feed when available. (+10 more)

### Community 7 - "accessibility.py"
Cohesion: 0.14
Nodes (23): click_element_at(), find_element_by_role(), find_element_by_title(), get_all_elements(), list_buttons(), list_text_fields(), Any, Recursively traverse an AXUIElement and its children to collect all UI elements. (+15 more)

### Community 8 - "ax_ui_element.py"
Cohesion: 0.13
Nodes (22): AXElementInfo, _enumerate_elements(), enumerate_elements_by_app(), enumerate_frontmost_app_elements(), _find_pids_by_app_name(), _get_app_name_for_pid(), get_ax_element_info(), _get_frontmost_pid() (+14 more)

### Community 9 - "mcp_server.py"
Cohesion: 0.15
Nodes (23): _handle_click_element_by_title(), _handle_get_frontmost_window(), _handle_list_windows(), _handle_move_mouse_relative(), _handle_read_elements(), _handle_scroll(), _handle_tool_call(), _handle_type_string() (+15 more)

### Community 10 - "live_feed.py"
Cohesion: 0.13
Nodes (18): _capture_one_cg(), _capture_one_cg_with_timeout(), _capture_one_screencapture(), invalidate_cache(), LiveFeedError, Image, RuntimeError, Capture a single frame using the ``screencapture`` CLI (from ``screen.py``). (+10 more)

### Community 11 - "ui_interactor.py"
Cohesion: 0.12
Nodes (21): classify_element(), _inject_mouse_scroll(), _is_button_text(), _is_disabled(), _press_enter_key(), _press_tab_key(), UI Interactor Module — Edge-Case UI Interaction Handling  Provides screen-captur, Return True if the text looks like a button label. (+13 more)

### Community 12 - "_CgAPI"
Cohesion: 0.12
Nodes (11): c_void_p, _CgAPI, Thin ctypes wrapper around CoreGraphics C API for HID event injection.      Meth, Cached CGEventSourceRef for mouse injection (0 if unavailable)., Post key-down via CGPostKeyboardEvent (simpler, no alloc needed)., Post key-up via CGPostKeyboardEvent., Create a keyboard event ref (caller must release via CFRelease)., Create a scroll wheel event using the fixed-arity CGEventCreateScrollWheelEvent2 (+3 more)

### Community 13 - "test_ui_interactor.py"
Cohesion: 0.16
Nodes (17): click_element(), Click at the centre of a detected UI element via virtual_hid MouseMixin injectio, Type *text* into a field at the element's coordinate location.      If ``click_f, type_into_element(), Unit tests for ui_interactor module - edge case handling., Test that mouse injection falls back to osascript when MouseMixin unavailable., Test that disabled buttons raise ValueError., Test that missing x/y coordinates raise ValueError. (+9 more)

### Community 14 - "MouseMixin"
Cohesion: 0.15
Nodes (9): cg_event_ref(), Yield a CoreGraphics event ref and auto-release it on exit.      Usage:, MouseMixin, Scroll the mouse wheel by `clicks` units. Direction: 'up', 'down', 'left', or 'r, Move the mouse by a relative delta (positive dx=right, positive dy=down)., Mixin providing mouse click/scroll/move injection via CGEventCreateMouseEvent., Check if a valid CGEventSourceRef exists for mouse injection.          Only non-, Helper to create, post, and release a mouse event.          Uses NULL (0) as the (+1 more)

### Community 15 - "test_live_feed.py"
Cohesion: 0.16
Nodes (16): Verify concurrent reads from multiple threads don't cause errors., Skip in pytest mode; exit cleanly when run as standalone script., Verify stop() terminates the capture thread without hanging., Verify get_live_feed returns cached feeds for same parameters., Verify VisionAgent.observe() uses the live feed instead of one-shot capture., Verify LiveDisplayFeed initializes and starts its background thread., Verify that get_frame returns updated frames over time (proves continuous stream, Verify region-based capture returns correctly sized images. (+8 more)

### Community 16 - "LiveDisplayFeed"
Cohesion: 0.16
Nodes (10): FeedStats, LiveDisplayFeed, Continuous background screen-capture feed.      Runs a daemon thread that captur, Stop the background capture thread and wait for it to exit.          This sets t, Best-effort cleanup — stop the feed if it is still running., Return ``True`` if the capture thread is currently alive., Return a snapshot of current feed statistics.          The returned :class:`Feed, Statistics about the current live feed state.      Attributes:         frames_ca (+2 more)

### Community 17 - "identify_clickable_elements"
Cohesion: 0.18
Nodes (13): _capture_screen_prefer_feed(), _element_to_dict(), identify_clickable_elements(), _load_image(), _ocr_text(), Any, Identify clickable/tappable UI elements in a captured image using OCR.      Args, Load an image from a PIL Image, file path, or bytes. (+5 more)

### Community 18 - "test_cli.py"
Cohesion: 0.15
Nodes (12): The 'demo' subcommand should parse with no extra args., The 'type' subcommand should parse text arguments correctly., The 'hotkey' subcommand should parse modifier key names correctly., The 'click' subcommand should parse button and coordinates correctly., The 'scroll' subcommand should parse direction correctly., The --help flag should list all available subcommands: type, hotkey, click, scro, test_click_subcommand_parses_coords(), test_demo_subcommand_parses() (+4 more)

### Community 19 - "SCNN - Self-Improving Cybernetic Neural Network Research Project"
Cohesion: 0.17
Nodes (11): Development Philosophy, Environment Setup, Identity, Project Structure (Minimal), Research Focus Areas (Add as project evolves), SCNN - Self-Improving Cybernetic Neural Network Research Project, Self-Improvement Patterns, Tool Usage Policy (+3 more)

### Community 20 - "Protocol Rules (Non-Negotiable)"
Cohesion: 0.17
Nodes (11): Auto-Handoff Protocol — Hard Enforced, Enforcement Notes, Protocol Rules (Non-Negotiable), Rule 1: Every Fix Attempt MUST Have a `bug_id`, Rule 2: Pre-Register Before Fixing (Claim Phase), Rule 3: Always Pass `bug_id` to `record_fix_attempt`, Rule 4: Call `stuck_report` Before Each Fix Attempt, Rule 5: Never Change the `bug_id` Mid-Fix Cycle (+3 more)

### Community 21 - "Computer Use Agent — Setup Guide"
Cohesion: 0.17
Nodes (11): 1. Anthropic API Key, 2. macOS Accessibility Permission, 3. Verify Installation, Computer Use Agent — Setup Guide, Daemon Mode (Optional), Example Output, Prerequisites, Run the Agent (+3 more)

### Community 22 - "ocr_image"
Cohesion: 0.21
Nodes (11): bpe_tokenize(), ocr_image(), ocr_text_from_region(), Any, Extract text regions from an image using Apple Vision framework.      Tries thre, Extract text from a specific region of an image.      Args:         image: Full, Tokenize text using Byte Pair Encoding (BPE).      Splits text into subword unit, Run Vision framework OCR directly via pyobjc (no subprocess).      Uses ``NSData (+3 more)

### Community 23 - "BoundingBox"
Cohesion: 0.17
Nodes (8): BoundingBox, Axis-aligned bounding box in screen coordinates., Test that element types are correctly classified., Test BoundingBox coordinate calculations., Test ClickableElement coordinate extraction., test_bounding_box_properties(), test_clickable_element_properties(), test_element_classification()

### Community 24 - "handle_modal_dialog"
Cohesion: 0.17
Nodes (12): handle_modal_dialog(), _identify_dialog_action(), _is_action_button(), Handle a modal dialog by finding and clicking its action buttons.      The funct, Determine whether an 'Accept' or 'Cancel' action is implied by dialog text., Return True if the element looks like an action button (OK/Cancel/etc.)., Select the best button from *candidates* based on the *preferred_action*.      E, _select_best_action_button() (+4 more)

### Community 25 - "pure_airllm.py"
Cohesion: 0.27
Nodes (4): anthropic_messages_endpoint(), DummyModel, DummyTokenizer, Request

### Community 26 - "ClickableElement"
Cohesion: 0.22
Nodes (6): _as_clickable_element(), ClickableElement, Right-click at the centre of an element (opens context menus).      Useful for c, Coerce a dict or :class:`ClickableElement` into the dataclass., A detected UI element that can be interacted with., right_click_element()

### Community 27 - "virtual_hid_cli.py"
Cohesion: 0.44
Nodes (9): cmd_click(), cmd_demo(), cmd_hotkey(), cmd_scroll(), cmd_type(), _get_hid(), main(), Import and return the VirtualHID singleton. (+1 more)

### Community 28 - "SCNN - Self-Improving Cybernetic Neural Network"
Cohesion: 0.22
Nodes (8): Directory Structure, Environment Setup, Getting Started, Prerequisites, Project Overview, Research Focus Areas, SCNN - Self-Improving Cybernetic Neural Network, Self-Improvement Loop

### Community 29 - "TestMouseMixin"
Cohesion: 0.22
Nodes (5): Test MouseMixin API surface with mocked _CgAPI., click should create mouse events via cg_event_ref context manager., scroll should call create_scroll_wheel_event (NOT create_mouse_event) with real, move_mouse should create a MouseMoved event and set deltaX/deltaY integer fields, TestMouseMixin

### Community 30 - "test_vkeys.py"
Cohesion: 0.22
Nodes (8): Verify a sample of known Carbon vkey values against Apple's Events.h reference., Unknown key names should return None (not crash)., Ensure all A-Z letters and 1-0 digits are mapped., Import-time assertion guarantees all vkey constants are unique.      This is the, test_all_constants_unique(), test_all_expected_keys_present(), test_get_vkey_returns_none_for_unknown(), test_known_values_correct()

### Community 31 - "._bind_sigs"
Cohesion: 0.29
Nodes (5): CDLL, Create a CGEventSourceRef with fork-based timeout to handle macOS permission pro, Load the CoreGraphics framework. Raises ImportError on non-macOS., Bind argument and return types for all CoreGraphics/CoreFoundation functions we, _safe_create_event_source()

### Community 32 - "/handoff Command"
Cohesion: 0.25
Nodes (7): Behavior, /handoff Command, Inline Focus Message (shown when command is triggered), Output Modes, Purpose, Template, When to Use

### Community 33 - "/handoff Skill"
Cohesion: 0.25
Nodes (7): Behavior, /handoff Skill, Inline Focus Message (shown when skill is triggered), Output Modes, Purpose, Template, When to Use

### Community 34 - "CGPoint"
Cohesion: 0.33
Nodes (4): CGPoint, Mac OS X CGPoint -- two double-precision floating-point coordinates., Create a mouse event ref (caller must release via CFRelease).          Args:, Return the current cursor position as a CGPoint by creating an uninitialized eve

### Community 35 - "capture_screen"
Cohesion: 0.40
Nodes (6): capture_region(), capture_screen(), CaptureResult, Capture the full desktop (all monitors composited) or a specific region.      Ar, Capture a rectangular region of the screen.      Args:         x, y: Top-left co, Structured result from any capture operation.

### Community 36 - "main"
Cohesion: 0.50
Nodes (4): ArgumentParser, _build_parser(), main(), CLI entry point — dispatches to the appropriate virtual_hid method.

### Community 37 - "_inject_mouse_click"
Cohesion: 0.50
Nodes (4): _click_via_applescript(), _inject_mouse_click(), Inject a single mouse click at (x, y) using osascript fallback., Click at (x, y) using osascript (the fallback when MouseMixin can't be instantia

## Knowledge Gaps
- **67 isolated node(s):** `install_agentworld.sh script`, `git_helper.sh script`, `Inline Focus Message (shown when command is triggered)`, `Purpose`, `When to Use` (+62 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `KeyboardMixin` connect `KeyboardMixin` to `mcp_server.py`, `__init__.py`, `accessibility.py`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `capture_screen()` connect `capture_screen` to `screen.py`, `__init__.py`, `live_feed.py`, `ui_interactor.py`, `identify_clickable_elements`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `MouseMixin` connect `MouseMixin` to `mcp_server.py`, `TestMouseMixin`, `__init__.py`, `accessibility.py`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `_CgAPI` (e.g. with `_handle_click_element_by_title()` and `_handle_type_string()`) actually correct?**
  _`_CgAPI` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `LiveDisplayFeed` (e.g. with `VirtualHID` and `ScreenCaptureError`) actually correct?**
  _`LiveDisplayFeed` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `KeyboardMixin` (e.g. with `VirtualHID` and `_handle_type_string()`) actually correct?**
  _`KeyboardMixin` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `install_agentworld.sh script`, `git_helper.sh script`, `Inline Focus Message (shown when command is triggered)` to the rest of the system?**
  _67 weakly-connected nodes found - possible documentation gaps or missing edges._