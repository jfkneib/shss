import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from miniai.tags import expand_line, find_requests, resolve_pending_tag


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


def _upper_resolver(request, prefix, suffix):
    return request.upper()


def test_resolve_pending_tag_no_tag_returns_unchanged():
    line = "ls -la"
    assert resolve_pending_tag(line, len(line), _upper_resolver) == (line, len(line))


def test_resolve_pending_tag_open_tag_at_cursor():
    line = "ls #@ trie par taille"
    point = len(line)
    new_line, new_point = resolve_pending_tag(line, point, _upper_resolver)
    assert new_line == "ls TRIE PAR TAILLE"
    assert new_point == len(new_line)


def test_resolve_pending_tag_already_closed_tag_is_ignored():
    line = "ls #@ trie par taille @# -a"
    point = len(line)
    assert resolve_pending_tag(line, point, _upper_resolver) == (line, point)


def test_resolve_pending_tag_keeps_suffix_after_cursor():
    line = "ls #@ trie par taille -a"
    point = len("ls #@ trie par taille")
    new_line, new_point = resolve_pending_tag(line, point, _upper_resolver)
    assert new_line == "ls TRIE PAR TAILLE -a"
    assert new_point == len("ls TRIE PAR TAILLE")
