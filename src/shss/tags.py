import re

TAG_RE = re.compile(r"#@\s*(.*?)\s*@#", re.DOTALL)


def find_requests(line: str):
    """Return the list of LLM request strings found in a line, in order."""
    return [m.group(1) for m in TAG_RE.finditer(line)]


def expand_line(line: str, resolver) -> str:
    """Replace every #@ ... @# tag in line with
    resolver(request_text, text_before_tag, text_after_tag)."""

    def _replace(m):
        return resolver(m.group(1), line[: m.start()], line[m.end() :])

    return TAG_RE.sub(_replace, line)


def resolve_pending_tag(line: str, point: int, resolver):
    """Resolve the tag closest to `point`, whether it's still being typed
    (no closing '@#' yet) or already fully closed — used to react to a
    keypress (Ctrl-G) at any moment while editing the line, before Enter.

    Returns (new_line, new_point). If there is nothing to resolve at or
    before `point`, returns (line, point) unchanged.
    """
    before = line[:point]
    after = line[point:]

    idx = before.rfind("#@")
    if idx != -1 and "@#" not in before[idx:]:
        request = before[idx + 2 :].strip()
        prefix = before[:idx]
        fragment = resolver(request, prefix, after)
        new_line = prefix + fragment + after
        return new_line, len(prefix) + len(fragment)

    last_match = None
    for m in TAG_RE.finditer(line):
        if m.end() <= point:
            last_match = m

    if last_match is None:
        return line, point

    prefix = line[: last_match.start()]
    suffix = line[last_match.end() :]
    fragment = resolver(last_match.group(1), prefix, suffix)
    new_line = prefix + fragment + suffix
    new_point = len(prefix) + len(fragment) + (point - last_match.end())
    return new_line, new_point
