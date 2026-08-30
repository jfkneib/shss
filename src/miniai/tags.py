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
