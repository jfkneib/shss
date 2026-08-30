import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from miniai.tags import expand_line, find_requests


def test_find_requests_single():
    assert find_requests("ls #@ liste les pdf @#") == ["liste les pdf"]


def test_find_requests_multiple():
    line = "ls #@ demande 1 @#  #@ demande 2 @#"
    assert find_requests(line) == ["demande 1", "demande 2"]


def test_find_requests_none():
    assert find_requests("ls -la") == []


def test_expand_line_replaces_each_tag_independently():
    line = "echo #@ un @# et #@ deux @#"
    calls = []

    def resolver(request, prefix, suffix):
        calls.append(request)
        return request.upper()

    assert expand_line(line, resolver) == "echo UN et DEUX"
    assert calls == ["un", "deux"]


def test_expand_line_passes_surrounding_context():
    seen = {}

    def resolver(request, prefix, suffix):
        seen["prefix"] = prefix
        seen["suffix"] = suffix
        return "X"

    expand_line("ls #@ cachés @# -1", resolver)
    assert seen == {"prefix": "ls ", "suffix": " -1"}
