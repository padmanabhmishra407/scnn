---
name: auto-handoff
description: "Enforce fix-attempt tracking with persistent bug_id. Detects stuck patterns at 6+ attempts and generates session handoffs."
trigger: /auto-handoff
always_apply: true
protocol_level: hard_enforced
---

# Auto-Handoff Protocol — Hard Enforced

## Protocol Rules (Non-Negotiable)

### Rule 1: Every Fix Attempt MUST Have a `bug_id`
A `bug_id` is the persistent handle for a tracked issue. It enables correct retrieval across sessions, handoffs, and the stuck-detection loop.

```
Bug ID Format: bug-<short-hex-slug>
Examples: bug-mouse-injection-fix, bug-tracker-state-corrupt
```

### Rule 2: Pre-Register Before Fixing (Claim Phase)
Before attempting any fix on a new issue, **call `claim_bug_id`** to register the bug and receive its ID. This creates the persistent handle that all subsequent attempts reference.

```
tool_call: claim_bug_id(
    description="What is broken — one sentence",
    files_affected=["src/virtual_hid/_core.py"],
    severity="high|medium|low"
)
# → Returns {"bug_id": "bug-<slug>", "attempt_number": 1, ...}
```

### Rule 3: Always Pass `bug_id` to `record_fix_attempt`
Every call to `record_fix_attempt` MUST include the `bug_id` from Rule 2. Never omit it — omission creates orphaned entries that drift across sessions and break retrieval.

```
tool_call: record_fix_attempt(
    bug_id="bug-mouse-injection-fix",   # ← REQUIRED, not optional
    description="Tried approach X on _core.py line 65",
    files_modified=["src/virtual_hid/_core.py"],
    result="failed|partial|resolved",
    error_output="Traceback... or null if resolved"
)
```

### Rule 4: Call `stuck_report` Before Each Fix Attempt
Before every fix attempt, call `stuck_report`. The response dictates action:
- `"continue_current"` → proceed with fix, then call `record_fix_attempt` with the SAME `bug_id`
- `"try_different_approach"` → review last 3 attempts for this bug, pick a fundamentally different hypothesis (different file, different root cause theory), record with same `bug_id`
- `"run_handoff"` → call `generate_handoff(bug_id=...)`, then call `/clear` to reset context. New session reads HANDOFF.md and continues from where it left off

### Rule 5: Never Change the `bug_id` Mid-Fix Cycle
Once a bug has an ID, that ID is immutable for the lifetime of the issue. Do NOT generate new IDs by varying descriptions or file lists. The hash must be stable. If you need to split one tracked bug into two separate issues, call `split_bug` instead of creating a new entry.

### Rule 6: Clear Tracker Only After Resolution
Call `clear_tracker(bug_id=...)` ONLY after the bug is truly resolved and verified (tests pass, no regression). Never clear a tracker entry mid-cycle — this loses attempt history and breaks the stuck-detection loop.

## Workflow Summary (One Page)

```
Session Start → stuck_report() → check for stuck bugs in active handoff
    │
    ├─ NEW BUG: claim_bug_id(description=..., files_affected=[...])
    │   → use returned bug_id for ALL subsequent calls
    │
    ├─ EXISTING BUG: record_fix_attempt(bug_id="bug-...", ...) [after each attempt]
    │   → if response says "stuck", generate_handoff then /clear
    │   → if response says "warning", try different approach first
    │
    └─ RESOLVED BUG: clear_tracker(bug_id="bug-...")
```

## When NOT to Use This Skill
- One-off questions or simple edits that don't involve debugging/fixing
- When explicitly told to skip tracking (e.g., "just show me the code, no need to track")
- Documentation-only changes with no behavioral impact

## Enforcement Notes
- **bug_id is required** — calls without it will be rejected or auto-claimed by `claim_bug_id` first
- **Stable hashing** — bug IDs are derived from description + files (not timestamps), so they persist across sessions
- **Cross-session retrieval** — a fresh session can call `stuck_report()` and immediately see all active bugs with their IDs, no prior context needed
