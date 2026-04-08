---
description: Flash Claude's previous response in a new Terminal.app window (RSVP)
argument-hint: [text to read]
allowed-tools: Write, Bash
---

# Flash

Pops open a new Terminal.app window that flashes text one word at a time (RSVP / Spritz-style, with the ORP letter in red) using the `rsvp-term.py` script at `${CLAUDE_PLUGIN_ROOT}/data/rsvp-term.py`. The window is opened with a 36pt font so the flashing words are large and easy to read, and the script itself runs a 3-second countdown at the ORP column before starting so the reader's eyes have time to fixate on the focal point.

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

4. **Launch a new Terminal.app window with a big font:**
   - Run this Bash command verbatim. `${CLAUDE_PLUGIN_ROOT}` is expanded by the current shell (where Claude Code sets it) **before** `osascript` sees it, so the resolved absolute path is what ends up in the Terminal window's shell. `${RSVP_FONT_SIZE:-36}` reads the user's preferred font size from their shell environment (set via `export RSVP_FONT_SIZE=42` in `~/.zshrc` or equivalent) and falls back to **36pt** if unset. The third `-e` sets that font size on the new window after `do script` creates it — targeting `window 1` works because `do script` makes its new window frontmost.
     ```bash
     FONT_SIZE=${RSVP_FONT_SIZE:-36}
     osascript \
       -e "tell application \"Terminal\" to do script \"python3 ${CLAUDE_PLUGIN_ROOT}/data/rsvp-term.py --wpm 600 < /tmp/claude-flash.txt\"" \
       -e 'tell application "Terminal" to activate' \
       -e "tell application \"Terminal\" to set font size of window 1 to $FONT_SIZE"
     ```

5. **Confirm to the user:** Tell them a new Terminal window is popping up. Mention:
   - A **3-second countdown** (3, 2, 1) appears at the ORP column before words start, so they have time to find the focal point with their eyes.
   - Default speed is **600 WPM**. Default font size is **36pt**, overridable via the `RSVP_FONT_SIZE` environment variable (set in the user's shell config).
   - Inside the new window: **Space** to pause, **q** or **Ctrl+C** to quit.
   - The window will stay open after `[done — N words @ 600 wpm]` so they can read the footer.

## Notes

- `rsvp-term.py` auto-reopens `/dev/tty` for keystroke input when stdin is piped from a file, so pause/quit controls work even though the text comes through `< /tmp/claude-flash.txt`.
- This command mutates nothing except the scratch file at `/tmp/claude-flash.txt`. Safe to run repeatedly.
- macOS-only (depends on `osascript` and `Terminal.app`).

## Arguments
$ARGUMENTS
