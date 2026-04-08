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

def flash(words, wpm, orp_col):
    base = 60.0 / wpm
    paused = False
    keys = KeyListener()
    size = shutil.get_terminal_size((80, 24))
    mid_row = max(1, size.lines // 2)
    # Move cursor to middle row, col 1, then clear that line — used for every frame
    goto_mid = f"\033[{mid_row};1H\033[2K"
    # After exit, drop to the last row so the shell prompt reappears below the flashed area
    goto_bottom = f"\033[{size.lines};1H\n"
    sys.stdout.write(CLEAR_SCREEN + HIDE_CURSOR)
    sys.stdout.flush()
    try:
        i = 0
        while i < len(words):
            key = keys.poll()
            if key == ' ':
                paused = not paused
                if paused:
                    sys.stdout.write(
                        goto_mid + render_word(words[i], orp_col) + "   [paused]"
                    )
                    sys.stdout.flush()
                # fall through to loop; either sleeps briefly or resumes flashing
            elif key in ('q', 'Q', '\x03'):
                break
            if paused:
                time.sleep(0.05)
                continue
            w = words[i]
            sys.stdout.write(goto_mid + render_word(w, orp_col))
            sys.stdout.flush()
            time.sleep(timing(w, base))
            i += 1
        sys.stdout.write(goto_mid + f"[done — {len(words)} words @ {wpm} wpm]" + goto_bottom)
    except KeyboardInterrupt:
        sys.stdout.write(goto_mid + "[interrupted]" + goto_bottom)
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

    flash(words, args.wpm, orp_col)


if __name__ == "__main__":
    main()
