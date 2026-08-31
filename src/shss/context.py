"""Builds the hidden (never typed by the user) context block injected
into the prompt: a small preview of any file the request actually names.
Lets the model react to what's really on disk (e.g. a CSV's real
delimiter) instead of guessing.

Deliberately does NOT add a directory listing on every request: an
earlier version did, and it regressed plain one-liners ("trie par
taille" started generating a bogus "ls -la | sort -k 5" instead of
"-S") because the model treated the unrelated listing as something to
act on. Only inject something when there's an actual file to show.
"""

import os
import re

_FILENAME_RE = re.compile(r"[./\w~-]+\.[A-Za-z0-9]{1,6}")

MAX_PREVIEW_LINES = 5
MAX_PREVIEW_CHARS = 300


def _extract_candidate_paths(text: str):
    seen = []
    for match in _FILENAME_RE.findall(text):
        if match not in seen:
            seen.append(match)
    return seen


def _preview_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= MAX_PREVIEW_LINES:
                    break
                lines.append(line.rstrip("\n"))
    except OSError:
        return ""
    return "\n".join(lines)[:MAX_PREVIEW_CHARS]


def build_context(request: str) -> str:
    """Return a "Contexte : ..." block (already newline-terminated), or
    an empty string if there's nothing useful to add."""
    lines = []

    for candidate in _extract_candidate_paths(request):
        path = os.path.expanduser(candidate)
        if os.path.isfile(path):
            preview = _preview_file(path)
            if preview:
                lines.append(f"Aperçu de {candidate} :")
                lines.append(preview)

    if not lines:
        return ""
    return "\n".join(lines) + "\n"
