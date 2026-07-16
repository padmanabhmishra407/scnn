#!/usr/bin/env python3
"""
State tracking for auto-handoff MCP server.

Manages fix_tracker.json with file locking for atomic read/write.
Each "bug" tracks attempts against a specific issue, with timestamps
and error output preserved across sessions.
"""

import json
import os
import fcntl
import hashlib
from datetime import datetime, timezone
from typing import Optional

TRACKER_PATH = os.path.join(os.environ.get("PROJECT_ROOT", "."), ".claude", "fix_tracker.json")

# Stable bug ID generation: description + files only (no timestamp).
# This guarantees the same issue gets the same bug_id across sessions,
# enabling correct cross-session retrieval and stuck-detection continuity.
def _generate_bug_id(description: str, files_modified: list) -> str:
    """Generate a stable, deterministic bug ID from description + affected files.

    The hash is computed from description+files only — no timestamps or session data —
    so the same issue always produces the same bug_id across sessions.
    """
    seed = f"{description}|{','.join(sorted(files_modified))}"
    h = hashlib.sha256(seed.encode()).hexdigest()[:8]
    return f"bug-{h}"


def _load_tracker() -> dict:
    """Load tracker state from disk. Creates fresh state if missing."""
    if os.path.exists(TRACKER_PATH):
        with open(TRACKER_PATH, "r") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return {
        "version": 1,
        "bugs": {},
        "current_focus": None,
        "last_session_read_at": None,
    }


def _save_tracker(state: dict):
    """Atomically write tracker state to disk with exclusive lock."""
    os.makedirs(os.path.dirname(TRACKER_PATH), exist_ok=True)
    tmp_path = TRACKER_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    os.replace(tmp_path, TRACKER_PATH)


def claim_bug_id(description: str, files_affected: list, severity: str = "medium") -> dict:
    """Pre-register a bug with a stable ID before any fix attempt.

    This MUST be called before the first record_fix_attempt for a new issue.
    The returned bug_id is immutable — it persists across sessions and handoffs.

    Args:
        description: One-sentence summary of what's broken (used in hash → same desc = same id)
        files_affected: List of files that need fixing (affects the ID hash)
        severity: "high", "medium", or "low" — used for prioritization in reports

    Returns:
        dict with bug_id, attempt_number=1, status="active", suggested_next_step
    """
    state = _load_tracker()

    # Check if this description+files combo already has a registered bug
    existing_id = None
    for bid, b in state["bugs"].items():
        seed_match = f"{b['description']}|{','.join(sorted(b.get('files_affected', [])))}"
        candidate_seed = f"{description}|{','.join(sorted(files_affected))}"
        if hashlib.sha256(seed_match.encode()).hexdigest()[:8] == \
           hashlib.sha256(candidate_seed.encode()).hexdigest()[:8]:
            existing_id = bid
            break

    if existing_id:
        bug = state["bugs"][existing_id]
        return {
            "bug_id": existing_id,
            "attempt_number": len(bug["attempts"]) + 1,
            "status": bug["status"],
            "message": f"Bug '{description}' already tracked as `{existing_id}`. Continuing.",
            "suggested_next_step": _suggest_next_step(bug),
        }

    new_id = _generate_bug_id(description, files_affected)
    now_iso = datetime.now(timezone.utc).isoformat()
    bug = {
        "description": description,
        "created_at": now_iso,
        "updated_at": now_iso,
        "status": "active",
        "severity": severity,
        "files_affected": sorted(set(files_affected)),
        "attempts": [],
        "stuck_threshold": 6,
        "auto_handoff_triggered": False,
    }
    state["bugs"][new_id] = bug

    if not state.get("current_focus"):
        state["current_focus"] = new_id

    _save_tracker(state)

    return {
        "bug_id": new_id,
        "attempt_number": 1,
        "status": "active",
        "message": f"Bug claimed: `{new_id}` — '{description}'",
        "suggested_next_step": _suggest_next_step(new_id, bug),
    }


def _suggest_next_step(bug_id: str, bug: dict) -> str:
    """Suggest next step based on bug state and attempt history."""
    count = len(bug["attempts"])
    threshold = bug.get("stuck_threshold", 6)

    if count == 0:
        return f"Call record_fix_attempt with this bug_id ({bug_id!r}) after each fix try."
    elif count >= threshold:
        return f"STUCK at {count} attempts. Call generate_handoff(bug_id={bug_id!r}) then /clear to reset context."
    elif count >= 4:
        last_errors = [a.get("error_output", "") for a in bug["attempts"][-3:]]
        return f"Approaching limit ({count}/{threshold}). Review these error patterns:\n" + "\n".join(f"  - {e[:100]}" for e in last_errors if e) or "  (none recorded)"
    else:
        last_result = bug["attempts"][-1]["result"]
        return f"Continue fixing ({count}/{threshold}). If result is 'failed', try a different approach before next attempt."


def record_fix_attempt(description: str, files_modified: list, result: str,
                       error_output: Optional[str] = None, bug_id: Optional[str] = None) -> dict:
    """Record a fix attempt and return current stuck status.

    Args:
        description: What you tried (1-2 sentences)
        files_modified: Files that were changed during this attempt
        result: "resolved" | "partial" | "failed"
        error_output: Error/traceback/console output. Omit for resolved/partial.
        bug_id: REQUIRED — the stable ID from claim_bug_id(). Never omit this.

    Returns:
        dict with stuck_status, message, and next-step suggestion
    """
    state = _load_tracker()

    if not bug_id or bug_id not in state["bugs"]:
        # Hard enforcement: require pre-claimed bug_id
        return {
            "error": "bug_id is required. Call claim_bug_id(description=..., files_affected=[...]) first.",
            "valid_bugs": list(state["bugs"].keys()),
        }

    bug = state["bugs"][bug_id]

    # Add attempt
    attempt_num = len(bug["attempts"]) + 1
    attempt = {
        "id": attempt_num,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": description,
        "files_modified": list(files_modified),
        "result": result,
        "error_output": error_output,
    }
    bug["attempts"].append(attempt)
    bug["updated_at"] = datetime.now(timezone.utc).isoformat()

    if result == "resolved":
        bug["status"] = "resolved"

    # Update file list (union of all files touched across attempts)
    all_files = set(bug.get("files_affected", [])) | set(files_modified)
    bug["files_affected"] = sorted(all_files)

    state["bugs"][bug_id] = bug
    _save_tracker(state)

    # Determine stuck status
    attempt_count = len(bug["attempts"])
    if result == "resolved":
        stuck_status = "ok"
        message = f"Fix recorded (attempt {attempt_num}). Bug resolved. Call clear_tracker when verified."
    elif attempt_count >= bug.get("stuck_threshold", 6):
        stuck_status = "stuck"
        message = (f"STUCK after {attempt_count} attempts on `{bug_id}`. "
                   f"Generate a handoff to continue in a fresh session.")
    elif attempt_count >= 4:
        stuck_status = "warning"
        message = (f"Approaching limit ({attempt_count}/6 attempts) on `{bug_id}`. "
                   f"Consider trying a different approach before generating handoff.")
    else:
        stuck_status = "ok"
        message = f"Fix recorded (attempt {attempt_num}/{bug.get('stuck_threshold', 6)}) for `{bug_id}`."

    return {
        "bug_id": bug_id,
        "attempt_number": attempt_num,
        "total_active_bugs": sum(1 for b in state["bugs"].values() if b["status"] == "active"),
        "stuck_status": stuck_status,
        "message": message,
        "suggested_next_step": _suggest_next_step(bug_id, bug),
    }


def generate_handoff(bug_id: Optional[str] = None, include_file_diffs: bool = False) -> dict:
    """Generate HANDOFF.md from tracker state."""
    import subprocess

    state = _load_tracker()
    bugs_to_include = {}

    if bug_id:
        if bug_id in state["bugs"]:
            bugs_to_include[bug_id] = state["bugs"][bug_id]
    else:
        # Include all active (non-resolved) bugs
        for bid, b in state["bugs"].items():
            if b.get("status") != "resolved":
                bugs_to_include[bid] = b

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build handoff content
    lines = [f"# Auto-Handoff — {now}", ""]

    if not bugs_to_include:
        lines.extend([
            "## No Active Bugs",
            "",
            "All tracked issues have been resolved. Nothing to hand off.",
            "",
        ])
    else:
        # Goal section
        lines.append("## Goal")
        for bid, bug in bugs_to_include.items():
            lines.append(f"1. **{bug['description']}** ({len(bug['attempts'])} attempts)")
        lines.append("")

        # Current State table
        lines.append("## Current State")
        lines.append("| Bug | Attempts | Status | Last Attempt |")
        lines.append("|-----|----------|--------|--------------|")
        for bid, bug in bugs_to_include.items():
            last_desc = bug["attempts"][-1]["description"] if bug["attempts"] else "N/A"
            status_icon = "✅" if bug["status"] == "resolved" else ("🔴" if len(bug["attempts"]) >= 6 else "🟡")
            lines.append(f"| {bid} | {len(bug['attempts'])} | {status_icon} {bug['status']} | {last_desc[:50]}... |")
        lines.append("")

        # Files In Flight
        all_files = set()
        for bug in bugs_to_include.values():
            all_files.update(bug.get("files_affected", []))
        if all_files:
            lines.append("## Files In Flight")
            for f in sorted(all_files):
                lines.append(f"- `{f}`")
            lines.append("")

        # Failed Attempts (most critical section)
        lines.append("## Failed Attempts")
        for bid, bug in bugs_to_include.items():
            lines.append(f"### {bug['description']} (`{bid}`)")
            lines.append("")
            for attempt in bug["attempts"]:
                icon = "✅" if attempt["result"] == "resolved" else ("🟡" if attempt["result"] == "partial" else "❌")
                lines.append(f"**Attempt {attempt['id']}** ({attempt['timestamp'][:16]}): {attempt['description']}")
                lines.append(f"  Files: {', '.join(attempt.get('files_modified', []))}")
                if attempt.get("error_output"):
                    # Truncate long error output
                    err = attempt["error_output"][:500]
                    if len(attempt["error_output"]) > 500:
                        err += "\n... (truncated)"
                    lines.append(f"  Error: `{err}`")
                lines.append("")

            # Next step recommendation based on failure pattern
            last_err = bug["attempts"][-1].get("error_output", "") if bug["attempts"] else ""
            files_touched = set()
            for a in bug["attempts"]:
                files_touched.update(a.get("files_modified", []))
            lines.append(f"**Recommended next step:** Last {min(3, len(bug['attempts']))} attempts modified `{', '.join(files_touched)}`. "
                         f"Try a different file or hypothesis.")
            lines.append("")

        # Include git diffs if requested
        if include_file_diffs:
            lines.append("## Git Diffs")
            for f in sorted(all_files):
                try:
                    diff = subprocess.run(
                        ["git", "diff", "--", f],
                        capture_output=True, text=True, timeout=10
                    )
                    if diff.stdout.strip():
                        lines.append(f"### `{f}`")
                        lines.append("```diff")
                        lines.append(diff.stdout[:2000])
                        lines.append("```")
                        lines.append("")
                except Exception:
                    pass

    # Write HANDOFF.md
    project_root = os.environ.get("PROJECT_ROOT", ".")
    handoff_path = os.path.join(project_root, "HANDOFF.md")
    with open(handoff_path, "w") as f:
        f.write("\n".join(lines))

    return {
        "handoff_path": handoff_path,
        "bugs_covered": len(bugs_to_include),
        "stuck_bugs": [bid for bid, b in bugs_to_include.items() if len(b["attempts"]) >= 6],
        "message": f"Handoff written to {handoff_path} covering {len(bugs_to_include)} active bug(s).",
    }


def stuck_report() -> dict:
    """Return concise status summary for decision-making."""
    state = _load_tracker()
    active_bugs = []

    for bid, bug in state["bugs"].items():
        if bug.get("status") == "resolved":
            continue
        count = len(bug["attempts"])
        threshold = bug.get("stuck_threshold", 6)
        last_desc = bug["attempts"][-1]["description"][:80] if bug["attempts"] else "N/A"

        if count >= threshold:
            stuck_status = "stuck"
        elif count >= 4:
            stuck_status = "warning"
        else:
            stuck_status = "ok"

        active_bugs.append({
            "bug_id": bid,
            "description": bug["description"],
            "attempt_count": count,
            "threshold": threshold,
            "status": bug["status"],
            "last_attempt_description": last_desc,
            "stuck_status": stuck_status,
        })

    has_stuck = any(b["stuck_status"] == "stuck" for b in active_bugs)
    has_warning = any(b["stuck_status"] == "warning" for b in active_bugs)

    if has_stuck:
        suggested_action = "run_handoff"
        message = "One or more bugs are stuck. Generate a handoff to continue with fresh context."
    elif has_warning:
        suggested_action = "try_different_approach"
        warning_bugs = [b for b in active_bugs if b["stuck_status"] == "warning"]
        message = (f"{len(warning_bugs)} bug(s) approaching stuck threshold. "
                   f"Review failed attempts before continuing.")
    else:
        suggested_action = "continue_current"
        message = "No stuck bugs detected. Continue current work."

    return {
        "active_bugs": active_bugs,
        "has_stuck_bugs": has_stuck,
        "suggested_action": suggested_action,
        "message": message,
    }


def clear_tracker(bug_id: Optional[str] = None) -> dict:
    """Clear tracker state for one or all bugs."""
    state = _load_tracker()
    cleared = 0

    if bug_id:
        if bug_id in state["bugs"]:
            del state["bugs"][bug_id]
            cleared = 1
            if state.get("current_focus") == bug_id:
                # Find next active bug to focus on (use dict key, not value)
                remaining_keys = [k for k, v in state["bugs"].items() if v["status"] == "active"]
                state["current_focus"] = remaining_keys[0] if remaining_keys else None
    else:
        cleared = len(state["bugs"])
        state["bugs"] = {}
        state["current_focus"] = None

    _save_tracker(state)
    return {
        "cleared_bugs": cleared,
        "message": f"Cleared {cleared} bug(s) from tracker." if cleared else "No bugs to clear.",
    }
