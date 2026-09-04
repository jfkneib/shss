import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from shss.tags import expand_line, find_requests, resolve_pending_tag


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


def test_find_requests_strips_profile_prefix():
    assert find_requests("ls #@pc-stats@ energie consommee @#") == ["energie consommee"]


def test_expand_line_profile_prefix_stripped_from_request(monkeypatch):
    monkeypatch.delenv("SHSS_CASES_PROFILE", raising=False)
    assert expand_line("#@pc-stats@ energie @#", _upper_resolver) == "ENERGIE"


def test_expand_line_profile_prefix_sets_env_var_during_resolution(monkeypatch):
    monkeypatch.delenv("SHSS_CASES_PROFILE", raising=False)
    seen = {}

    def resolver(request, prefix, suffix):
        seen["profile_during"] = os.environ.get("SHSS_CASES_PROFILE")
        return request

    expand_line("#@pc-stats@ energie @#", resolver)

    assert seen["profile_during"] == "pc-stats"
    assert "SHSS_CASES_PROFILE" not in os.environ  # restaure apres coup


def test_expand_line_profile_prefix_restores_previous_value(monkeypatch):
    monkeypatch.setenv("SHSS_CASES_PROFILE", "dev")
    seen = {}

    def resolver(request, prefix, suffix):
        seen["profile_during"] = os.environ.get("SHSS_CASES_PROFILE")
        return request

    expand_line("#@pc-stats@ energie @#", resolver)

    assert seen["profile_during"] == "pc-stats"
    assert os.environ["SHSS_CASES_PROFILE"] == "dev"  # remis, pas efface


def test_expand_line_without_profile_prefix_leaves_env_var_untouched(monkeypatch):
    monkeypatch.delenv("SHSS_CASES_PROFILE", raising=False)
    seen = {}

    def resolver(request, prefix, suffix):
        seen["profile_during"] = os.environ.get("SHSS_CASES_PROFILE")
        return request

    expand_line("#@ energie @#", resolver)

    assert seen["profile_during"] is None


def test_resolve_pending_tag_profile_prefix_on_open_tag():
    line = "ls #@pc-stats@ trie par taille"
    point = len(line)
    new_line, new_point = resolve_pending_tag(line, point, _upper_resolver)
    assert new_line == "ls TRIE PAR TAILLE"
    assert new_point == len(new_line)


def test_resolve_pending_tag_profile_prefix_on_closed_tag_sets_env_var(monkeypatch):
    monkeypatch.delenv("SHSS_CASES_PROFILE", raising=False)
    seen = {}

    def resolver(request, prefix, suffix):
        seen["profile_during"] = os.environ.get("SHSS_CASES_PROFILE")
        return request.upper()

    line = "ls #@pc-stats@ trie par taille @#"
    resolve_pending_tag(line, len(line), resolver)

    assert seen["profile_during"] == "pc-stats"
    assert "SHSS_CASES_PROFILE" not in os.environ


def test_resolve_pending_tag_no_tag_returns_unchanged():
    line = "ls -la"
    assert resolve_pending_tag(line, len(line), _upper_resolver) == (line, len(line))


def test_resolve_pending_tag_open_tag_at_cursor():
    line = "ls #@ trie par taille"
    point = len(line)
    new_line, new_point = resolve_pending_tag(line, point, _upper_resolver)
    assert new_line == "ls TRIE PAR TAILLE"
    assert new_point == len(new_line)


def test_resolve_pending_tag_already_closed_tag_at_cursor_is_resolved():
    line = "ls #@ trie par taille @#"
    point = len(line)
    new_line, new_point = resolve_pending_tag(line, point, _upper_resolver)
    assert new_line == "ls TRIE PAR TAILLE"
    assert new_point == len(new_line)


def test_resolve_pending_tag_closed_tag_with_cursor_further_right():
    line = "ls #@ trie par taille @# -a"
    point = len(line)
    new_line, new_point = resolve_pending_tag(line, point, _upper_resolver)
    assert new_line == "ls TRIE PAR TAILLE -a"
    assert new_point == len(new_line)


def test_resolve_pending_tag_keeps_suffix_after_cursor():
    line = "ls #@ trie par taille -a"
    point = len("ls #@ trie par taille")
    new_line, new_point = resolve_pending_tag(line, point, _upper_resolver)
    assert new_line == "ls TRIE PAR TAILLE -a"
    assert new_point == len("ls TRIE PAR TAILLE")
