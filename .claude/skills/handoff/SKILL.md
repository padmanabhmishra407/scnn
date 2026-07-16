---
name: handoff
description: "Session context handoff — summarize current state for a fresh session to continue work without re-reading history"
trigger: /handoff
---

# /handoff Skill

## Inline Focus Message (shown when skill is triggered)
```
🔄 **Handoff Required**: A fresh session needs context continuity. Generate a HANDOFF.md summary so the next session can pick up exactly where this one left off — no re-reading git history, no re-discovering bugs. Use `--inline` to print only (no file write), or omit for default HANDOFF.md in project root.
```

## Purpose
Generate a comprehensive session context summary so a fresh Claude Code session can pick up exactly where the previous one left off — no re-reading git history, no re-discovering bugs.

## When to Use
- Before ending a long working session with incomplete work
- When switching between sessions and you want continuity
- When handing off work to another developer or agent

## Behavior

When invoked, produce and write a `HANDOFF.md` file in the project root containing:

1. **Goal** — what were we trying to accomplish? (1-2 sentences)
2. **Current State** — where exactly did we leave off? What's done vs pending?
3. **Files In Flight** — which files are being modified and what state they're in now
4. **What Changed** — summary of all modifications made this session
5. **Failed Attempts** — things tried that didn't work (so the next session doesn't repeat them)
6. **Next Step** — exactly what to do next, with file paths and line numbers if applicable

## Output Modes
- **Default**: Write `HANDOFF.md` in project root AND print summary to terminal
- **With `--inline` flag**: Print only to terminal (no file write)
- **With `--to <path>` flag**: Write to custom path instead of default

## Template

```markdown
# HANDOFF — [YYYY-MM-DD HH:MM UTC]

## Goal
[What we were working on]

## Current State
[Where exactly we left off. What's done, what's pending.]

## Files In Flight
| File | Status | Notes |
|------|--------|-------|
| `path/to/file.py` | Modified | [what changed, current state] |
| `path/to/other.py` | Created | [new file, purpose] |

## What Changed This Session
- [bullet list of all meaningful changes]

## Failed Attempts
1. **Attempt**: [description] — **Why it failed**: [reason]
2. ...

## Next Step
[Exact action to take next, with file paths and line numbers]

## Context Notes
[Anything else a fresh session needs to know: env quirks, known bugs, design decisions made.]
```
