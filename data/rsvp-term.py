#!/usr/bin/env python3
"""
Terminal RSVP (Rapid Serial Visual Presentation) reader.

Flashes words one at a time in place with the ORP letter in red, Spritz-style.
Port of the core logic from reader.html for use in a real TTY.

Usage:
    python3 rsvp-term.py "text to read"
    python3 rsvp-term.py "text" --wpm 800
    pbpaste | python3 rsvp-term.py
    echo "some words" | python3 rsvp-term.py -w 500

Controls (TTY only):
    Space  pause / resume
    q      quit
    Ctrl+C quit

Exit codes:
    0  finished or user quit cleanly
    1  no input / no words to show
"""
import sys
import time
import re
import argparse
import select
import shutil

RED = "\033[31m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K\r"
CLEAR_SCREEN = "\033[2J"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


# ---------- core logic (ported from reader.html) ----------

def orp_index(w):
    """Optimal Recognition Point index for a word — ~1/3 in."""
    if not w:
        return 0
    if len(w) > 13:
        return 4
    return [0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3][len(w)]


def split_path(w):
    """Split long path-like tokens into segments so they flash at a readable pace."""
    slash_count = w.count('/')
    if len(w) <= 12 or slash_count < 2:
        return [w]
    prefix = ''
    m = re.match(r'^([a-z][a-z0-9+.-]*://)', w, re.I)
    if m:
        prefix = m.group(1)
        w = w[len(prefix):]
        if '/' not in w:
            return [prefix + w]
    parts = w.split('/')
    leads = w.startswith('/')
    out = []
    first = True
    for i, p in enumerate(parts):
        if p == '':
            continue
        seg = p
        if first:
            if prefix:
                seg = prefix + seg
            elif leads:
                seg = '/' + seg
            first = False
        if i < len(parts) - 1:
            seg = seg + '/'
        out.append(seg)
    return out if out else [prefix + w]


def timing(w, base):
    """Per-word dwell time (seconds) — longer for punctuation and long tokens."""
    t = base
    last = w[-1:] if w else ''
    if last in '.!?':
        t *= 2.2
    elif last in ',;:':
        t *= 1.5
    if len(w) > 18:
        t *= 1.6
    elif len(w) > 12:
        t *= 1.3
    elif len(w) > 10:
        t *= 1.1
    return t


def tokenize(text):
    raw = re.sub(r'\s+', ' ', text).strip().split(' ')
    out = []
    for w in raw:
        if w:
            out.extend(split_path(w))
    return out


# ---------- rendering ----------

def render_word(w, orp_col):
    """Build an ANSI-colored line with the ORP char aligned at column `orp_col`."""
    i = orp_index(w)
    before = w[:i]
    orp_char = w[i:i + 1]
    after = w[i + 1:]
    pad = max(0, orp_col - len(before))
    return (' ' * pad) + before + RED + orp_char + RESET + after


# ---------- non-blocking key input ----------

class KeyListener:
    """Put the TTY in cbreak mode so we can poll for single keypresses without blocking."""

    def __init__(self):
        self.enabled = False
        self.old = None
        self.termios = None
        self.fd = None
        try:
            import termios
            import tty
            if sys.stdin.isatty():
                self.termios = termios
                self.fd = sys.stdin.fileno()
                self.old = termios.tcgetattr(self.fd)
                tty.setcbreak(self.fd)
                self.enabled = True
        except Exception:
            pass

    def poll(self):
        if not self.enabled:
            return None
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if r:
            return sys.stdin.read(1)
        return None

    def restore(self):
        if self.enabled and self.old is not None:
            self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.old)


# ---------- main flash loop ----------

HINTS_TEXT = "space pause  ·  b back  ·  q quit"


def _wait_for_key(keys, timeout_s):
    """Poll for a keypress, returning the key char or None on timeout.
    If timeout_s is None, waits indefinitely. Poll interval is 20ms, so
    key presses are noticed within ~20ms instead of at the end of a
    blocking sleep — critical for space/b to feel responsive."""
    deadline = None if timeout_s is None else time.monotonic() + timeout_s
    while True:
        key = keys.poll()
        if key is not None:
            return key
        if deadline is not None and time.monotonic() >= deadline:
            return None
        time.sleep(0.02)


def _render(word_or_digit, index, total, orp_col, paused):
    """Redraw the full frame: word at middle row, progress bar + hints near bottom.

    Re-queries terminal size on every call so the layout adapts to font-size
    changes that happen mid-session — e.g. /flash bumps the Terminal.app window
    to 48pt *after* rsvp-term.py has started, which shrinks the row count from
    under the script's feet. Without re-querying, the bar and hints would end
    up off-screen.
    """
    sz = shutil.get_terminal_size((80, 24))
    rows, cols = sz.lines, sz.columns
    mid_row = max(1, rows // 2)
    bar_row = max(mid_row + 2, rows - 2)
    hints_row = max(bar_row + 1, rows - 1)

    # Middle row — word with optional [paused] suffix
    pause_suffix = "   [paused]" if paused else ""
    mid_content = render_word(word_or_digit, orp_col) + pause_suffix

    # Progress bar — filled/empty block chars + word count
    if total > 0:
        count_str = f"{index}/{total}"
        bar_width = max(10, min(40, cols - len(count_str) - 4))
        filled = min(bar_width, int((index / total) * bar_width))
        bar = "█" * filled + "░" * (bar_width - filled)
        progress_line = f"{bar}  {count_str}"
    else:
        progress_line = ""

    # Dimmed hints row (ANSI 2 = faint)
    hints_line = "\033[2m" + HINTS_TEXT + "\033[0m"

    out = (
        f"\033[{mid_row};1H\033[2K" + mid_content +
        f"\033[{bar_row};1H\033[2K" + progress_line +
        f"\033[{hints_row};1H\033[2K" + hints_line
    )
    sys.stdout.write(out)
    sys.stdout.flush()


def flash(words, wpm, orp_col, countdown_seconds=3):
    base = 60.0 / wpm
    paused = False
    total = len(words)
    keys = KeyListener()
    sys.stdout.write(CLEAR_SCREEN + HIDE_CURSOR)
    sys.stdout.flush()
    quit_early = False
    try:
        # Countdown: big digits at the ORP column, one per second, so the
        # reader's eyes can fixate on the focal spot before the words begin.
        # Uses _render so the progress bar and hints are already visible
        # underneath the countdown — readers can orient to the full layout.
        for n in range(countdown_seconds, 0, -1):
            _render(str(n), 0, total, orp_col, False)
            time.sleep(1)

        # Main word loop — non-blocking, driven by _wait_for_key so key
        # presses are noticed within ~20ms instead of only at word boundaries.
        i = 0
        while 0 <= i < total:
            # position = i + 1 so the bar + count read as "word X of N"
            # (the user thinks of the first word as 1/N, not 0/N)
            _render(words[i], i + 1, total, orp_col, paused)
            timeout = None if paused else timing(words[i], base)
            key = _wait_for_key(keys, timeout)
            if key == ' ':
                paused = not paused
            elif key in ('b', 'B'):
                # Back one word AND pause, so the reader can re-read it at leisure
                i = max(0, i - 1)
                paused = True
            elif key in ('q', 'Q', '\x03'):
                quit_early = True
                break
            elif key is None:
                # Timeout: advance to the next word
                i += 1
            # any other key: ignore and redraw (no state change)

        # Exit message — clear screen, center the footer, cursor to bottom row
        sz = shutil.get_terminal_size((80, 24))
        footer = (
            f"[quit at {i + 1}/{total}]" if quit_early
            else f"[done — {total} words @ {wpm} wpm]"
        )
        sys.stdout.write(
            CLEAR_SCREEN +
            f"\033[{max(1, sz.lines // 2)};1H" + footer +
            f"\033[{sz.lines};1H\n"
        )
    except KeyboardInterrupt:
        sz = shutil.get_terminal_size((80, 24))
        sys.stdout.write(
            CLEAR_SCREEN +
            f"\033[{max(1, sz.lines // 2)};1H[interrupted]" +
            f"\033[{sz.lines};1H\n"
        )
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()
        keys.restore()


def main():
    ap = argparse.ArgumentParser(
        description="Terminal RSVP reader with Spritz-style ORP highlighting.",
    )
    ap.add_argument("text", nargs="?", help="text to read (or pipe via stdin)")
    ap.add_argument("-w", "--wpm", type=int, default=600,
                    help="words per minute (default: 600)")
    ap.add_argument("-c", "--col", type=int, default=None,
                    help="column for the ORP letter (default: terminal width / 2)")
    ap.add_argument("--countdown", type=int, default=3, metavar="N",
                    help="countdown seconds before flashing starts (default: 3, 0 to skip)")
    args = ap.parse_args()

    if args.text is not None:
        text = args.text
    else:
        if sys.stdin.isatty():
            ap.error("no text provided and stdin is a TTY — pass text as argument or pipe it in")
        text = sys.stdin.read()

    words = tokenize(text)
    if not words:
        print("(no words to show)", file=sys.stderr)
        sys.exit(1)

    term_width = shutil.get_terminal_size((80, 24)).columns
    orp_col = args.col if args.col else max(10, term_width // 2)

    # If we read text from stdin (pipe), reattach stdin to the TTY so KeyListener works.
    if not sys.stdin.isatty():
        try:
            sys.stdin = open('/dev/tty', 'r')
        except Exception:
            pass

    flash(words, args.wpm, orp_col, args.countdown)


if __name__ == "__main__":
    main()
