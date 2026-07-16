#!/usr/bin/env bash
# Installer script to register the `agentworld` command locally.
set -euo pipefail

SRC_SCRIPT="$(pwd)/pure_airllm.py"
DEST_DIR="$HOME/.local/bin"
DEST="$DEST_DIR/agentworld"

mkdir -p "$DEST_DIR"
cp "$SRC_SCRIPT" "$DEST"
chmod +x "$DEST"

echo "Installed agentworld -> $DEST"
echo "If ~/.local/bin is not in your PATH, add the following to your shell profile (e.g. ~/.zshrc):"
echo "  export PATH=\"$HOME/.local/bin:\$PATH\""
echo "Then reload your shell: source ~/.zshrc  # or source ~/.bashrc"

echo "Run 'agentworld' to start the FastAPI server (requires Python deps)."
