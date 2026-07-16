#!/usr/bin/env python3
"""
Auto-Handoff MCP Server — detects stuck fix patterns and creates session handoffs.

Implements the Model Context Protocol (MCP) using JSON-RPC over stdio transport.
Claude Code spawns this as a subprocess and communicates via stdin/stdout.

Tools:
  - record_fix_attempt: Track a fix attempt and get stuck status
  - generate_handoff: Create HANDOFF.md from tracker state
  - stuck_report: Check current stuck status before attempting fixes
  - clear_tracker: Reset all tracked bugs (after resolution)

State is persisted in .claude/fix_tracker.json with file locking for atomicity.
"""

import json
import sys
import os

# Add project root to path so tracker module is importable
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", "/Users/padmanabhmishra/Documents/scnn")
sys.path.insert(0, PROJECT_ROOT)

from tracker import (
    record_fix_attempt, generate_handoff, stuck_report, clear_tracker,
    claim_bug_id, _suggest_next_step,
)


def _tool_definitions():
    """Return the list of tool definitions for MCP initialization."""
    return [
        {
            "name": "claim_bug_id",
            "description": (
                "Pre-register a bug with a stable, cross-session ID BEFORE attempting fixes. "
                "This is REQUIRED before record_fix_attempt on new issues. "
                "The same description+files always produces the same bug_id."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "One-sentence summary of what's broken (used in hash — keep consistent)",
                    },
                    "files_affected": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files that need fixing (affects the ID hash)",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "default": "medium",
                        "description": "Priority level for report sorting",
                    },
                },
                "required": ["description", "files_affected"],
            },
        },
        {
            "name": "record_fix_attempt",
            "description": (
                "Record a fix attempt on a PREVIOUSLY CLAIMED bug. "
                "You MUST have called claim_bug_id first — this tool rejects attempts without a valid bug_id."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bug_id": {
                        "type": "string",
                        "description": "REQUIRED: The stable ID from claim_bug_id. Never omit this.",
                    },
                    "description": {
                        "type": "string",
                        "description": "What you tried (1-2 sentences)",
                    },
                    "files_modified": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files that were changed during this attempt",
                    },
                    "result": {
                        "type": "string",
                        "enum": ["resolved", "partial", "failed"],
                        "description": "Outcome: resolved=fixed, partial=promising but incomplete, failed=no improvement",
                    },
                    "error_output": {
                        "type": ["string", "null"],
                        "description": "Error output or relevant console output. Omit for resolved/partial.",
                    },
                },
                "required": ["bug_id", "description", "files_modified", "result"],
            },
        },
        {
            "name": "generate_handoff",
            "description": (
                "Generate HANDOFF.md with full context from tracker. "
                "Call when stuck or before session clear."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bug_id": {
                        "type": ["string", "null"],
                        "description": "Specific bug to hand off on. Null for all active bugs.",
                    },
                    "include_file_diffs": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include git diffs of modified files in handoff.",
                    },
                },
            },
        },
        {
            "name": "stuck_report",
            "description": (
                "Return current stuck status for all tracked bugs. "
                "Call BEFORE attempting any fix to decide whether to continue or hand off."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "clear_tracker",
            "description": (
                "Clear tracker state for resolved bugs. "
                "Call when work on a bug is truly complete."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bug_id": {
                        "type": ["string", "null"],
                        "description": "Clear one bug. Null to clear all.",
                    },
                },
            },
        },
    ]


def _handle_message(body):
    """Process an incoming JSON-RPC request and return a response dict."""
    try:
        req = json.loads(body) if isinstance(body, str) else body
        method = req.get("method", "")
        params = req.get("params", {})
        msg_id = req.get("id")

        # Tool calls
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name == "claim_bug_id":
                result = claim_bug_id(
                    description=arguments["description"],
                    files_affected=arguments["files_affected"],
                    severity=arguments.get("severity", "medium"),
                )
            elif tool_name == "record_fix_attempt":
                # Enforce bug_id as required — no auto-creation on record
                if not arguments.get("bug_id"):
                    result = {
                        "error": "bug_id is REQUIRED. Call claim_bug_id(description=..., files_affected=[...]) first to get a stable ID.",
                        "hint": "Use the same description+files combination to always get the same bug_id across sessions.",
                    }
                else:
                    result = record_fix_attempt(
                        description=arguments["description"],
                        files_modified=arguments["files_modified"],
                        result=arguments["result"],
                        error_output=arguments.get("error_output"),
                        bug_id=arguments["bug_id"],
                    )
            elif tool_name == "generate_handoff":
                result = generate_handoff(
                    bug_id=arguments.get("bug_id"),
                    include_file_diffs=arguments.get("include_file_diffs", False),
                )
            elif tool_name == "stuck_report":
                result = stuck_report()
            elif tool_name == "clear_tracker":
                result = clear_tracker(bug_id=arguments.get("bug_id"))
            else:
                return {"jsonrpc": "2.0", "id": msg_id, "error": {
                    "code": -32601, "message": f"Method not found: {tool_name}"},
                }

            if isinstance(result, dict):
                content = [{"type": "text", "text": json.dumps(result, indent=2)}]
            else:
                content = [{"type": "text", "text": str(result)}]

            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "content": content,
            }}

        # List tools (during initialization)
        elif method == "tools/list":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {
                "tools": _tool_definitions(),
            }}

        # Initialize request from client — respond with capabilities
        elif method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "auto-handoff", "version": "1.0.0"},
                },
            }
            # Also send tools/list notification so client knows what's available
            return resp

        else:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {
                "code": -32601, "message": f"Method not found: {method}"},
            }

    except Exception as e:
        import traceback
        print(f"[auto-handoff] Error handling request: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return {"jsonrpc": "2.0", "id": msg_id, "error": {
            "code": -32603, "message": f"Internal error: {str(e)}"},
        }


def _send_response(response):
    """Write a JSON-RPC response as a single line to stdout (MCP stdio protocol)."""
    # MCP over stdio uses newline-delimited JSON — one message per line
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def _send_notification(notification):
    """Send a notification (no id, no response expected)."""
    sys.stdout.write(json.dumps(notification) + "\n")
    sys.stdout.flush()


def main():
    """Main loop: read JSON-RPC messages from stdin, respond on stdout."""
    print("[auto-handoff] MCP server started", file=sys.stderr)

    # Send initialization notification
    _send_notification({
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    })

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = _handle_message(line)
            if response is not None:
                _send_response(response)
        except Exception as e:
            print(f"[auto-handoff] Unhandled error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
