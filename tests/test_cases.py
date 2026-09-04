import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import shss.cases as cases_module


class FakeEmbedder:
    """Remplacant deterministe de cases.Embedder : associe quelques
    phrases connues a des vecteurs choisis a la main (similarite
    predictible), et compte les appels pour verifier le comportement
    de cache de reindex()."""

    VECTORS = {
        "energie consommee par le pc": [1.0, 0.0],
        "combien consomme mon ordinateur": [0.9, 0.1],
        "trie les fichiers par taille": [0.0, 1.0],
        "quelle est la consommation electrique de ma machine": [0.95, 0.05],
    }

    def __init__(self):
        self.model_path = "fake.gguf"
        self.calls = 0

    def embed(self, text):
        self.calls += 1
        return self.VECTORS.get(text, [0.0, 0.0])


def _setup_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("SHSS_CASES_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("SHSS_CASES_CACHE_PATH", str(tmp_path / "cases.embeddings.json"))


def _isolate_embed_model_dirs(monkeypatch, tmp_path):
    """Comme _isolate_models_dirs() dans test_llm.py, pour le modele
    d'embeddings : jamais /opt/shss/models ni ~/.shss/models en vrai."""
    monkeypatch.setattr(cases_module, "SYSTEM_MODELS_DIR", tmp_path / "system")
    monkeypatch.setattr(cases_module, "MODELS_DIR", tmp_path / "user")


def _raise_not_found(*args, **kwargs):
    raise FileNotFoundError("pas trouve via Ollama")


def test_load_cases_missing_file_returns_empty(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    assert cases_module.load_cases() == []


def test_add_and_save_round_trip(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = cases_module.add_case(
        [], "energie", ["energie consommee par le pc"], "#!/usr/bin/env bash\necho hi\n"
    )
    cases_module.save_cases(cases)

    reloaded = cases_module.load_cases()
    assert reloaded[0]["id"] == "energie"
    assert reloaded[0]["requests"] == ["energie consommee par le pc"]


def test_add_case_rejects_duplicate_id():
    existing = [{"id": "energie", "requests": ["x"], "script": "echo hi"}]
    try:
        cases_module.add_case(existing, "energie", ["y"], "echo bye")
        assert False, "devrait lever ValueError"
    except ValueError:
        pass


def test_add_case_requires_at_least_one_request():
    try:
        cases_module.add_case([], "energie", [], "echo hi")
        assert False, "devrait lever ValueError"
    except ValueError:
        pass


def test_remove_case_missing_id_raises_keyerror():
    try:
        cases_module.remove_case([], "absent")
        assert False, "devrait lever KeyError"
    except KeyError:
        pass


def test_update_case_replaces_only_given_fields():
    existing = [
        {"id": "energie", "requests": ["x"], "script": "echo x", "note": "ancienne note"},
        {"id": "tri", "requests": ["y"], "script": "echo y"},
    ]
    updated = cases_module.update_case(existing, "energie", script="echo nouveau")

    energie = next(c for c in updated if c["id"] == "energie")
    assert energie["script"] == "echo nouveau"
    assert energie["requests"] == ["x"]  # inchange
    assert energie["note"] == "ancienne note"  # inchange
    # ordre et l'autre cas preserves
    assert [c["id"] for c in updated] == ["energie", "tri"]


def test_update_case_missing_id_raises_keyerror():
    try:
        cases_module.update_case([], "absent", note="x")
        assert False, "devrait lever KeyError"
    except KeyError:
        pass


def test_remove_case_round_trip():
    existing = [{"id": "energie", "requests": ["x"], "script": "echo hi"}]
    remaining = cases_module.remove_case(existing, "energie")
    assert remaining == []


def test_reindex_then_find_matches_ranks_closest_case(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = [
        {
            "id": "energie",
            "requests": ["energie consommee par le pc", "combien consomme mon ordinateur"],
            "script": "echo energie",
        },
        {"id": "tri", "requests": ["trie les fichiers par taille"], "script": "echo tri"},
    ]
    embedder = FakeEmbedder()
    cache = cases_module.reindex(cases, embedder=embedder)
    assert embedder.calls == 3  # une par formulation

    matches = cases_module.find_matches(
        "quelle est la consommation electrique de ma machine",
        cases=cases,
        cache=cache,
        embedder=embedder,
        top_k=2,
    )
    assert matches[0][0]["id"] == "energie"
    assert matches[1][0]["id"] == "tri"
    assert matches[0][1] > matches[1][1]


def test_reindex_reuses_unchanged_vectors(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = [{"id": "energie", "requests": ["energie consommee par le pc"], "script": "x"}]
    embedder = FakeEmbedder()
    cases_module.reindex(cases, embedder=embedder)
    assert embedder.calls == 1

    # meme contenu -> pas de nouvel appel d'embedding
    cases_module.reindex(cases, embedder=embedder)
    assert embedder.calls == 1


def test_reindex_force_recomputes_everything(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = [{"id": "energie", "requests": ["energie consommee par le pc"], "script": "x"}]
    embedder = FakeEmbedder()
    cases_module.reindex(cases, embedder=embedder)
    cases_module.reindex(cases, embedder=embedder, force=True)
    assert embedder.calls == 2


def test_is_stale_true_when_case_added_after_last_reindex(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = [{"id": "energie", "requests": ["energie consommee par le pc"], "script": "x"}]
    cache = cases_module.reindex(cases, embedder=FakeEmbedder())
    assert not cases_module.is_stale(cases, cache)

    cases.append({"id": "tri", "requests": ["trie les fichiers par taille"], "script": "y"})
    assert cases_module.is_stale(cases, cache)


class _FakeLlamaCppHandle:
    """Remplacant du `Llama(..., embedding=True)` interne d'Embedder,
    pour tester le pooling sans charger de vrai modele."""

    def __init__(self, token_vectors):
        self._token_vectors = token_vectors

    def create_embedding(self, text):
        return {"data": [{"embedding": self._token_vectors}]}


def test_embedder_mean_pools_per_token_vectors():
    # Ce que renvoie reellement llama.cpp pour un modele sans pooling :
    # un vecteur par token -- Embedder doit les moyenner en un seul.
    embedder = cases_module.Embedder(model_path="fake.gguf")
    embedder._llm = _FakeLlamaCppHandle([[1.0, 3.0], [3.0, 5.0]])
    assert embedder.embed("peu importe") == [2.0, 4.0]


def test_embedder_passes_through_already_pooled_vector():
    embedder = cases_module.Embedder(model_path="fake.gguf")
    embedder._llm = _FakeLlamaCppHandle([1.0, 2.0, 3.0])
    assert embedder.embed("peu importe") == [1.0, 2.0, 3.0]


def test_find_matches_empty_before_any_reindex(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = [{"id": "energie", "requests": ["energie consommee par le pc"], "script": "x"}]
    # aucun reindex() -> pas de fichier de cache sur disque
    assert cases_module.find_matches("n'importe quoi", cases=cases, cache=None) == []


def test_extract_payload_finds_first_quoted_span():
    payload, normalized = cases_module.extract_payload('corrige moi ma ligne bash : "select | id"')
    assert payload == "select | id"
    assert normalized == 'corrige moi ma ligne bash : "..."'


def test_extract_payload_handles_single_quotes():
    payload, normalized = cases_module.extract_payload("corrige : 'select | id'")
    assert payload == "select | id"
    assert normalized == 'corrige : "..."'


def test_extract_payload_none_when_no_quotes():
    payload, normalized = cases_module.extract_payload("energie consommee par le pc")
    assert payload is None
    assert normalized == "energie consommee par le pc"


def test_add_case_with_input_mode_stdin_sets_input_field():
    cases = cases_module.add_case([], "fix", ["x"], "echo x", input_mode="stdin")
    assert cases[0]["input"] == "stdin"


def test_add_case_rejects_invalid_input_mode():
    try:
        cases_module.add_case([], "fix", ["x"], "echo x", input_mode="bogus")
        assert False, "devrait lever ValueError"
    except ValueError:
        pass


def test_update_case_can_set_and_clear_input_mode():
    cases = [{"id": "fix", "requests": ["x"], "script": "echo x"}]
    updated = cases_module.update_case(cases, "fix", input_mode="stdin")
    assert updated[0]["input"] == "stdin"

    cleared = cases_module.update_case(updated, "fix", input_mode="")
    assert "input" not in cleared[0]


def test_template_case_matches_regardless_of_quoted_content(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)

    class TemplateFakeEmbedder:
        """Un seul 'sujet' reconnu : peu importe le texte tant qu'il se
        normalise pareil (voir extract_payload) -- demontre que deux
        contenus entre guillemets differents matchent quand meme le
        meme cas, et que le VRAI contenu de la demande (pas celui de
        l'exemple stocke) est retourne comme payload."""

        def __init__(self):
            self.model_path = "fake.gguf"

        def embed(self, text):
            return [1.0, 0.0] if text == 'corrige moi ma ligne bash : "..."' else [0.0, 1.0]

    cases = [
        {
            "id": "fix-select",
            "requests": ['corrige moi ma ligne bash : "select | id from t"'],
            "script": "x",
            "input": "stdin",
        }
    ]
    embedder = TemplateFakeEmbedder()
    cache = cases_module.reindex(cases, embedder=embedder)

    match = cases_module.best_match(
        'corrige moi ma ligne bash : "select | truc | machin from autre_table"',
        cases=cases,
        cache=cache,
        embedder=embedder,
    )

    assert match is not None
    case, score, payload = match
    assert case["id"] == "fix-select"
    assert payload == "select | truc | machin from autre_table"


def test_curated_embed_model_path_prefers_system_dir(monkeypatch, tmp_path):
    _isolate_embed_model_dirs(monkeypatch, tmp_path)
    system_dir = tmp_path / "system"
    system_dir.mkdir()
    system_file = system_dir / cases_module.CURATED_EMBED_MODEL_FILENAME
    system_file.write_bytes(b"")
    assert cases_module.curated_embed_model_path() == str(system_file)


def test_curated_embed_model_path_falls_back_to_user_dir(monkeypatch, tmp_path):
    _isolate_embed_model_dirs(monkeypatch, tmp_path)
    expected = tmp_path / "user" / cases_module.CURATED_EMBED_MODEL_FILENAME
    assert cases_module.curated_embed_model_path() == str(expected)


def test_download_embedding_model_skips_if_already_present(monkeypatch, tmp_path):
    _isolate_embed_model_dirs(monkeypatch, tmp_path)
    user_dir = tmp_path / "user"
    user_dir.mkdir(parents=True)
    existing = user_dir / cases_module.CURATED_EMBED_MODEL_FILENAME
    existing.write_bytes(b"deja la")

    def fail_if_called(*a, **k):
        raise AssertionError("ne doit pas re-telecharger un fichier deja present")

    monkeypatch.setattr(cases_module.urllib.request, "urlretrieve", fail_if_called)

    assert cases_module.download_embedding_model() == str(existing)


def test_download_embedding_model_downloads_when_missing(monkeypatch, tmp_path):
    _isolate_embed_model_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(cases_module.os, "geteuid", lambda: 1000)  # utilisateur normal
    calls = []

    def fake_urlretrieve(url, dest):
        calls.append((url, dest))
        Path(dest).write_bytes(b"contenu")

    monkeypatch.setattr(cases_module.urllib.request, "urlretrieve", fake_urlretrieve)

    path = cases_module.download_embedding_model()
    assert path == str(tmp_path / "user" / cases_module.CURATED_EMBED_MODEL_FILENAME)
    assert Path(path).read_bytes() == b"contenu"
    assert len(calls) == 1


def test_download_embedding_model_as_root_goes_to_shared_dir(monkeypatch, tmp_path):
    _isolate_embed_model_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(cases_module.os, "geteuid", lambda: 0)  # simule sudo

    def fake_urlretrieve(url, dest):
        Path(dest).write_bytes(b"contenu")

    monkeypatch.setattr(cases_module.urllib.request, "urlretrieve", fake_urlretrieve)

    path = cases_module.download_embedding_model()
    assert path == str(tmp_path / "system" / cases_module.CURATED_EMBED_MODEL_FILENAME)


def test_discover_embedding_model_path_env_override(monkeypatch):
    monkeypatch.setenv("SHSS_EMBED_MODEL_PATH", "/some/where/embed.gguf")
    assert cases_module.discover_embedding_model_path() == "/some/where/embed.gguf"


def test_discover_embedding_model_path_falls_back_to_downloaded_curated(monkeypatch, tmp_path):
    monkeypatch.delenv("SHSS_EMBED_MODEL_PATH", raising=False)
    monkeypatch.setattr(cases_module, "_discover_ollama_only", _raise_not_found)
    _isolate_embed_model_dirs(monkeypatch, tmp_path)
    user_dir = tmp_path / "user"
    user_dir.mkdir(parents=True)
    curated = user_dir / cases_module.CURATED_EMBED_MODEL_FILENAME
    curated.write_bytes(b"")

    assert cases_module.discover_embedding_model_path() == str(curated)


def test_threshold_default_when_unset(monkeypatch):
    monkeypatch.delenv("SHSS_CASES_THRESHOLD", raising=False)
    assert cases_module._threshold() == cases_module.DEFAULT_THRESHOLD


def test_threshold_env_override(monkeypatch):
    monkeypatch.setenv("SHSS_CASES_THRESHOLD", "0.42")
    assert cases_module._threshold() == 0.42


def test_threshold_env_invalid_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("SHSS_CASES_THRESHOLD", "pas-un-nombre")
    assert cases_module._threshold() == cases_module.DEFAULT_THRESHOLD


def test_best_match_short_circuits_on_empty_store(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)

    def _boom(*a, **kw):
        raise AssertionError("ne doit pas instancier d'Embedder sur une base vide")

    monkeypatch.setattr(cases_module, "Embedder", _boom)
    assert cases_module.best_match("n'importe quoi") is None


def test_best_match_returns_case_above_threshold(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = [{"id": "energie", "requests": ["energie consommee par le pc"], "script": "x"}]
    embedder = FakeEmbedder()
    cache = cases_module.reindex(cases, embedder=embedder)

    match = cases_module.best_match(
        "energie consommee par le pc", cases=cases, cache=cache, embedder=embedder
    )
    assert match is not None
    case, score, payload = match
    assert case["id"] == "energie"
    assert payload is None  # aucun contenu entre guillemets dans cette demande


def test_best_match_returns_none_below_threshold(monkeypatch, tmp_path):
    _setup_paths(monkeypatch, tmp_path)
    cases = [{"id": "tri", "requests": ["trie les fichiers par taille"], "script": "x"}]
    embedder = FakeEmbedder()
    cache = cases_module.reindex(cases, embedder=embedder)

    match = cases_module.best_match(
        "un truc totalement sans rapport", cases=cases, cache=cache, embedder=embedder
    )
    assert match is None


def test_discover_embedding_model_path_raises_with_helpful_message(monkeypatch, tmp_path):
    monkeypatch.delenv("SHSS_EMBED_MODEL_PATH", raising=False)
    monkeypatch.setattr(cases_module, "_discover_ollama_only", _raise_not_found)
    _isolate_embed_model_dirs(monkeypatch, tmp_path)

    try:
        cases_module.discover_embedding_model_path()
        assert False, "devrait lever FileNotFoundError"
    except FileNotFoundError as exc:
        assert "download-model" in str(exc)
