---
description: Flash Claude's previous response in a new Terminal.app window (RSVP)
argument-hint: [text to read]
allowed-tools: Write, Bash
---

# Flash

Pops open a new Terminal.app window that flashes text one word at a time (RSVP / Spritz-style, with the ORP letter in red) using the `rsvp-term.py` script at `${CLAUDE_PLUGIN_ROOT}/data/rsvp-term.py`.

This is the terminal counterpart to `/speed`:
- `/speed` opens the browser-based fullscreen reader.
- `/flash` opens a **new Terminal.app window** that flashes the same content inline in a real TTY.

## Instructions

1. **Get the text:**
   - If arguments were provided (see the "Arguments" section below), use them.
   - Otherwise, extract the main content from your **previous response** in this conversation (the assistant message before the user ran `/flash`).

2. **Prepare the content:**
   - Strip markdown formatting (headers `#`, bold/italic `**` `*` `_`, inline code backticks, code fences, link syntax `[text](url)` → just `text`, blockquotes `>`, bullet markers `- ` / `* ` / `1. `).
   - Keep clean, readable prose — the kind of thing that's pleasant to flash one word at a time.
   - Do **not** escape quotes or backslashes — the text is written to a plain file, not embedded in a shell command.

3. **Write to the scratch file:**
   - Write the cleaned text to `/tmp/claude-flash.txt`, overwriting any previous run. Use the Write tool directly (no need to Read it first — overwriting is the intent).

4. **Launch a new Terminal.app window:**
   - Run this Bash command. The `${CLAUDE_PLUGIN_ROOT}` variable is expanded by the current shell (where Claude Code sets it) **before** `osascript` ever sees it, so the resolved absolute path is what gets passed into the Terminal window's shell:
     ```bash
     osascript \
       -e "tell application \"Terminal\" to do script \"python3 ${CLAUDE_PLUGIN_ROOT}/data/rsvp-term.py --wpm 600 < /tmp/claude-flash.txt\"" \
       -e 'tell application "Terminal" to activate'
     ```

5. **Confirm to the user:** Tell them a new Terminal window is popping up. Mention:
   - Default speed is **600 WPM**.
   - Inside the new window: **Space** to pause, **q** or **Ctrl+C** to quit.
   - The window will stay open after `[done — N words @ 600 wpm]` so they can read the footer.

## Notes

- `rsvp-term.py` auto-reopens `/dev/tty` for keystroke input when stdin is piped from a file, so pause/quit controls work even though the text comes through `< /tmp/claude-flash.txt`.
- This command mutates nothing except the scratch file at `/tmp/claude-flash.txt`. Safe to run repeatedly.
- macOS-only (depends on `osascript` and `Terminal.app`).

## Arguments
$ARGUMENTS
