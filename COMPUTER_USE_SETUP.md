# Computer Use Agent — Setup Guide

## Prerequisites

### 1. Anthropic API Key
Get your key from [console.anthropic.com](https://console.anthropic.com):
```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

Or add to `~/.zshrc` for persistence:
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-your-key-here"' >> ~/.zshrc
source ~/.zshrc
```

### 2. macOS Accessibility Permission
pyautogui needs permission to control your computer:

1. **System Settings → Privacy & Security → Accessibility**
2. Click the `+` button
3. Navigate to `/usr/bin/python3` (or wherever Python is installed)
4. Enable the toggle for Terminal.app if running from there

Without this, pyautogui will fail silently or throw permission errors.

### 3. Verify Installation
```bash
cd /Users/padmanabhmishra/Documents/scnn
python3 -c "import pyautogui; print(f'pyautogui OK — screen: {pyautogui.size()}')"
python3 -c "from PIL import Image; print('Pillow OK')"
python3 -c "import anthropic; print(f'Anthropic SDK OK (v{anthropic.__version__})')"
```

## Usage

### Run the Agent
```bash
python3 computer_use_agent.py "Open Safari and go to example.com"
python3 computer_use_agent.py "Take a screenshot, then open Calculator"
python3 computer_use_agent.py "Type 'hello world' in Terminal"
```

### Daemon Mode (Optional)
For continuous listening, you can wrap it in a loop:
```bash
while true; do
  read -p "Task: " task
  python3 computer_use_agent.py "$task" || break
done
```

## What It Does

1. **Captures** your current screen via pyautogui
2. **Sends** the screenshot + task to Claude via Anthropic API
3. **Receives** tool calls (click/type/move/scroll/wait)
4. **Executes** each action against your desktop
5. **Screenshots** again and loops until done or max iterations (20)

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pyautogui` permission denied | Grant Accessibility to Terminal/Python |
| API returns 401 | Check `ANTHROPIC_API_KEY` is set correctly |
| No actions execute | Add print statements in `execute_action()` for debugging |
| Slow/skipped keystrokes | Increase `keyboard_delay=0.1` in the tool definition |

## Example Output
```
🖥️  Detected screen: 2560x1600
============================================================
🧠 Computer Use Agent — Task: Open Calculator and compute 42 * 7
============================================================

🔄 Iteration 1/20
⌨️ Typing: command + space...
🖱️ Clicking (1280, 900) with 'left' button
✅ Agent finished. Final text:
The calculation is complete: 42 × 7 = 294
```
