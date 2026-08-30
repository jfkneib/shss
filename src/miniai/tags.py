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
    """Find the last '#@' before `point` that isn't closed yet by '@#',
    and resolve it via resolver(request, prefix, suffix) — used to react
    to a keypress while the tag is still being typed, before Enter.

    Returns (new_line, new_point). If there is no pending tag before
    `point`, returns (line, point) unchanged.
    """
    before = line[:point]
    after = line[point:]

    idx = before.rfind("#@")
    if idx == -1 or "@#" in before[idx:]:
        return line, point

    request = before[idx + 2 :].strip()
    prefix = before[:idx]
    fragment = resolver(request, prefix, after)
    new_line = prefix + fragment + after
    return new_line, len(prefix) + len(fragment)
