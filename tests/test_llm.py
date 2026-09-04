import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import shss.llm as llm_module
from shss.llm import ResolutionCancelled, discover_gguf_path


def test_discover_gguf_path_env_override(monkeypatch):
    monkeypatch.setenv("SHSS_MODEL_PATH", "/some/where/model.gguf")
    assert discover_gguf_path() == "/some/where/model.gguf"


def test_discover_gguf_path_falls_back_to_system_model_path(monkeypatch, tmp_path):
    monkeypatch.delenv("SHSS_MODEL_PATH", raising=False)
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [])
    fake_model = tmp_path / "model.gguf"
    fake_model.write_bytes(b"")
    monkeypatch.setattr(llm_module, "SYSTEM_MODEL_PATH", str(fake_model))
    assert discover_gguf_path() == str(fake_model)


def test_discover_gguf_path_falls_back_to_downloaded_curated_model(monkeypatch, tmp_path):
    monkeypatch.delenv("SHSS_MODEL_PATH", raising=False)
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [])
    monkeypatch.setattr(llm_module, "SYSTEM_MODEL_PATH", str(tmp_path / "absent.gguf"))
    monkeypatch.setattr(llm_module, "SYSTEM_MODELS_DIR", tmp_path / "system")
    monkeypatch.setattr(llm_module, "MODELS_DIR", tmp_path / "user")
    (tmp_path / "user").mkdir()
    curated = tmp_path / "user" / f"{llm_module.CURATED_MODEL_FAMILY}-0.5b.gguf"
    curated.write_bytes(b"")

    assert discover_gguf_path(tag="0.5b") == str(curated)


def test_discover_gguf_path_prefers_system_model_over_absent_curated(monkeypatch, tmp_path):
    monkeypatch.delenv("SHSS_MODEL_PATH", raising=False)
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [])
    monkeypatch.setattr(llm_module, "SYSTEM_MODELS_DIR", tmp_path / "system")
    monkeypatch.setattr(llm_module, "MODELS_DIR", tmp_path / "user")
    system_model = tmp_path / "model.gguf"
    system_model.write_bytes(b"")
    monkeypatch.setattr(llm_module, "SYSTEM_MODEL_PATH", str(system_model))

    assert discover_gguf_path(tag="0.5b") == str(system_model)


def test_download_curated_model_rejects_unknown_tag():
    try:
        llm_module.download_curated_model("does-not-exist")
        assert False, "devrait lever KeyError"
    except KeyError:
        pass


def _isolate_models_dirs(monkeypatch, tmp_path):
    """Point both the shared and per-user curated-model directories at
    tmp_path subfolders that don't exist yet, so tests never touch the
    real /opt/shss/models or ~/.shss/models."""
    monkeypatch.setattr(llm_module, "SYSTEM_MODELS_DIR", tmp_path / "system")
    monkeypatch.setattr(llm_module, "MODELS_DIR", tmp_path / "user")


def test_download_curated_model_skips_if_already_present(monkeypatch, tmp_path):
    _isolate_models_dirs(monkeypatch, tmp_path)
    user_dir = tmp_path / "user"
    user_dir.mkdir(parents=True)
    existing = user_dir / f"{llm_module.CURATED_MODEL_FAMILY}-3b.gguf"
    existing.write_bytes(b"deja la")

    def fail_if_called(*a, **k):
        raise AssertionError("ne doit pas re-telecharger un fichier deja present")

    monkeypatch.setattr(llm_module.urllib.request, "urlretrieve", fail_if_called)

    path = llm_module.download_curated_model("3b")
    assert path == str(existing)


def test_download_curated_model_downloads_when_missing(monkeypatch, tmp_path):
    _isolate_models_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(llm_module.os, "geteuid", lambda: 1000)  # utilisateur normal
    calls = []

    def fake_urlretrieve(url, dest):
        calls.append((url, dest))
        Path(dest).write_bytes(b"contenu")

    monkeypatch.setattr(llm_module.urllib.request, "urlretrieve", fake_urlretrieve)

    path = llm_module.download_curated_model("3b")
    assert path == str(tmp_path / "user" / f"{llm_module.CURATED_MODEL_FAMILY}-3b.gguf")
    assert Path(path).read_bytes() == b"contenu"
    assert len(calls) == 1


def test_download_curated_model_as_root_goes_to_shared_dir(monkeypatch, tmp_path):
    _isolate_models_dirs(monkeypatch, tmp_path)
    monkeypatch.setattr(llm_module.os, "geteuid", lambda: 0)  # simule sudo

    def fake_urlretrieve(url, dest):
        Path(dest).write_bytes(b"contenu")

    monkeypatch.setattr(llm_module.urllib.request, "urlretrieve", fake_urlretrieve)

    path = llm_module.download_curated_model("3b")
    assert path == str(tmp_path / "system" / f"{llm_module.CURATED_MODEL_FAMILY}-3b.gguf")


def test_curated_model_path_prefers_shared_over_per_user(monkeypatch, tmp_path):
    _isolate_models_dirs(monkeypatch, tmp_path)
    system_dir = tmp_path / "system"
    user_dir = tmp_path / "user"
    system_dir.mkdir(parents=True)
    user_dir.mkdir(parents=True)
    system_file = system_dir / f"{llm_module.CURATED_MODEL_FAMILY}-3b.gguf"
    user_file = user_dir / f"{llm_module.CURATED_MODEL_FAMILY}-3b.gguf"
    system_file.write_bytes(b"partage")
    user_file.write_bytes(b"prive")

    assert llm_module.curated_model_path("3b") == str(system_file)


def test_switch_model_falls_back_to_downloaded_curated_model(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [])
    _isolate_models_dirs(monkeypatch, tmp_path)
    user_dir = tmp_path / "user"
    user_dir.mkdir(parents=True)
    curated = user_dir / f"{llm_module.CURATED_MODEL_FAMILY}-3b.gguf"
    curated.write_bytes(b"x")

    instance = llm_module.MiniLLM.__new__(llm_module.MiniLLM)
    instance.model_path = "/whatever.gguf"
    instance._llm = "not-none-yet"

    new_path = instance.switch_model(tag="3b")

    assert new_path == str(curated)
    assert instance._llm is None


def test_switch_model_not_found_mentions_download_command(monkeypatch, tmp_path):
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [])
    _isolate_models_dirs(monkeypatch, tmp_path)

    instance = llm_module.MiniLLM.__new__(llm_module.MiniLLM)
    instance.model_path = "/whatever.gguf"
    instance._llm = None

    try:
        instance.switch_model(tag="3b")
        assert False, "devrait lever FileNotFoundError"
    except FileNotFoundError as exc:
        assert "model download 3b" in str(exc)


def test_switch_model_ignores_minaii_model_path_override(monkeypatch, tmp_path):
    # SHSS_MODEL_PATH doit gagner pour la resolution normale...
    monkeypatch.setenv("SHSS_MODEL_PATH", "/some/where/other.gguf")
    assert discover_gguf_path() == "/some/where/other.gguf"

    # ...mais switch_model() doit quand meme trouver le modele Ollama
    # explicitement demande, pas juste re-renvoyer l'override.
    library = tmp_path / "manifests" / "registry.ollama.ai" / "library" / "qwen2.5-coder"
    library.mkdir(parents=True)
    (library / "3b").write_text("{}")
    monkeypatch.setattr(llm_module, "_KNOWN_OLLAMA_DIRS", [str(tmp_path)])

    fake_blob = str(tmp_path / "blobs" / "sha256-fake3b")

    def fake_read_manifest_blob(models_dir, model, tag):
        if (model, tag) == ("qwen2.5-coder", "3b"):
            return fake_blob
        return None

    monkeypatch.setattr(llm_module, "_read_manifest_blob", fake_read_manifest_blob)

    instance = llm_module.MiniLLM.__new__(llm_module.MiniLLM)
    instance.model_path = "/some/where/other.gguf"
    instance._llm = "not-none-yet"

    new_path = instance.switch_model(tag="3b")

    assert new_path == fake_blob
    assert instance.model_path == fake_blob
    assert instance._llm is None


def test_env_int_parses_or_falls_back(monkeypatch):
    monkeypatch.setenv("SHSS_TEST_INT", "6")
    assert llm_module._env_int("SHSS_TEST_INT", 1) == 6
    monkeypatch.setenv("SHSS_TEST_INT", "")
    assert llm_module._env_int("SHSS_TEST_INT", 1) == 1
    monkeypatch.setenv("SHSS_TEST_INT", "pas-un-nombre")
    assert llm_module._env_int("SHSS_TEST_INT", 1) == 1
    monkeypatch.delenv("SHSS_TEST_INT", raising=False)
    assert llm_module._env_int("SHSS_TEST_INT", None) is None


def test_gpu_layers_auto_detects_nvidia(monkeypatch):
    monkeypatch.delenv("SHSS_N_GPU_LAYERS", raising=False)
    monkeypatch.setattr(llm_module.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    assert llm_module._gpu_layers() == -1
    monkeypatch.setattr(llm_module.shutil, "which", lambda name: None)
    assert llm_module._gpu_layers() == 0


def test_gpu_layers_explicit_value_wins(monkeypatch):
    monkeypatch.setattr(llm_module.shutil, "which", lambda name: None)
    monkeypatch.setenv("SHSS_N_GPU_LAYERS", "20")
    assert llm_module._gpu_layers() == 20
    monkeypatch.setenv("SHSS_N_GPU_LAYERS", "0")
    assert llm_module._gpu_layers() == 0


def test_n_ctx_env_override(monkeypatch):
    monkeypatch.setenv("SHSS_N_CTX", "1024")
    instance = llm_module.MiniLLM.__new__(llm_module.MiniLLM)
    instance.model_path = "/x.gguf"
    instance._llm = None
    instance._n_ctx = llm_module._env_int("SHSS_N_CTX", 2048)
    assert instance._n_ctx == 1024


class _FakeLlama:
    def __init__(self, text):
        self.text = text
        self.last_prompt = None

    def __call__(self, prompt, **kwargs):
        self.last_prompt = prompt
        return {"choices": [{"text": self.text}]}


def _fake_shss(monkeypatch, tmp_path, fake_text):
    monkeypatch.setenv("SHSS_HISTORY_PATH", str(tmp_path / "history.jsonl"))
    monkeypatch.setattr(llm_module, "SCRIPT_DIR", tmp_path / "scripts")
    # Base de cas curates isolee (vide) : jamais ~/.shss/cases.json reel,
    # meme s'il existe sur la machine qui fait tourner les tests.
    monkeypatch.setenv("SHSS_CASES_PATH", str(tmp_path / "cases.json"))
    monkeypatch.setenv("SHSS_CASES_CACHE_PATH", str(tmp_path / "cases.embeddings.json"))

    instance = llm_module.MiniLLM.__new__(llm_module.MiniLLM)
    instance._llm = _FakeLlama(fake_text)
    instance._ensure_loaded = lambda: None
    return instance


def test_generate_bash_inline_takes_only_first_line(monkeypatch, tmp_path):
    llm = _fake_shss(monkeypatch, tmp_path, "-la\n\nLigne: du bruit en trop")
    assert llm.generate_bash("affiche aussi les fichiers caches", "ls ", "") == "-la"


def test_generate_bash_script_mode_writes_file_and_returns_its_path(monkeypatch, tmp_path):
    script_text = (
        "#!/usr/bin/env python3\n"
        'import json\nwith open("a.txt") as f:\n    pass\n'
    )
    llm = _fake_shss(monkeypatch, tmp_path, script_text)

    result = llm.generate_bash("formate a.txt en json")

    result_path = Path(result)
    assert result_path.is_file()
    assert result_path.suffix == ".py"
    assert result_path.read_text() == script_text.strip()
    assert oct(result_path.stat().st_mode)[-3:] == "700"


def test_generate_bash_logs_to_history(monkeypatch, tmp_path):
    from shss.history import read_events

    llm = _fake_shss(monkeypatch, tmp_path, "-S")
    llm.generate_bash("trie par taille", "ls ", "")

    events = read_events()
    assert len(events) == 1
    assert events[0]["request"] == "trie par taille"
    assert events[0]["result"] == "-S"
    assert events[0]["kind"] == "inline"


def test_generate_bash_confirm_sees_the_final_display_text(monkeypatch, tmp_path):
    llm = _fake_shss(monkeypatch, tmp_path, "-la\n\nLigne: du bruit en trop")
    seen = {}

    def confirm(text):
        seen["text"] = text
        return True

    result = llm.generate_bash("affiche aussi les fichiers caches", confirm=confirm)
    assert seen["text"] == "-la"
    assert result == "-la"


def test_generate_bash_confirm_false_cancels_without_side_effects(monkeypatch, tmp_path):
    from shss.history import read_events

    llm = _fake_shss(monkeypatch, tmp_path, "#!/usr/bin/env python3\nprint('hi')")

    try:
        llm.generate_bash("fait un truc", confirm=lambda text: False)
        assert False, "devrait lever ResolutionCancelled"
    except ResolutionCancelled:
        pass

    assert read_events() == []


def test_generate_bash_uses_confident_case_match_without_calling_llm(monkeypatch, tmp_path):
    import shss.cases as cases_module
    from shss.history import read_events

    llm = _fake_shss(monkeypatch, tmp_path, "ne devrait jamais etre lu")
    case = {"id": "energie", "requests": ["x"], "script": "#!/usr/bin/env bash\necho watts\n"}
    monkeypatch.setattr(cases_module, "best_match", lambda request, **kw: (case, 0.9, None))

    result = llm.generate_bash("energie consommee par le pc")

    script_path = result.rsplit(" ", 1)[-1]  # apres le prefixe SHSS_REQUEST=...
    assert Path(script_path).read_text() == case["script"]
    assert llm._llm.last_prompt is None  # le LLM de generation n'a jamais tourne
    events = read_events()
    assert events[0]["kind"] == "case"
    assert events[0]["result"] == result


def test_generate_bash_falls_through_to_llm_without_confident_case_match(monkeypatch, tmp_path):
    import shss.cases as cases_module

    llm = _fake_shss(monkeypatch, tmp_path, "-S")
    monkeypatch.setattr(cases_module, "best_match", lambda request, **kw: None)

    result = llm.generate_bash("trie par taille", "ls ", "")

    assert result == "-S"
    assert llm._llm.last_prompt is not None


def test_generate_bash_case_match_still_honors_confirm(monkeypatch, tmp_path):
    import shss.cases as cases_module

    llm = _fake_shss(monkeypatch, tmp_path, "ne devrait jamais etre lu")
    case = {"id": "energie", "requests": ["x"], "script": "#!/usr/bin/env bash\necho watts\n"}
    monkeypatch.setattr(cases_module, "best_match", lambda request, **kw: (case, 0.9, None))

    try:
        llm.generate_bash("energie consommee par le pc", confirm=lambda text: False)
        assert False, "devrait lever ResolutionCancelled"
    except ResolutionCancelled:
        pass
    assert not (tmp_path / "scripts").exists()


def test_generate_bash_template_case_pipes_payload_via_stdin(monkeypatch, tmp_path):
    import shlex

    import shss.cases as cases_module
    from shss.history import read_events

    llm = _fake_shss(monkeypatch, tmp_path, "ne devrait jamais etre lu")
    case = {
        "id": "fix-select",
        "requests": ["x"],
        "script": "#!/usr/bin/env python3\nimport sys\nprint(sys.stdin.read())\n",
        "input": "stdin",
    }
    payload = "select | id | name |   from t;"
    monkeypatch.setattr(cases_module, "best_match", lambda request, **kw: (case, 0.9, payload))

    written = {}
    real_write_script = llm_module._write_script

    def spy_write_script(text):
        path = real_write_script(text)
        written["path"] = path
        return path

    monkeypatch.setattr(llm_module, "_write_script", spy_write_script)

    request = 'corrige moi ma ligne bash : "select | id | name |   from t;"'
    result = llm.generate_bash(request)

    # le resultat est une ligne bash (pipe), pas juste le chemin du script
    assert result.startswith("printf '%s' ")
    assert payload in result  # shlex.quote garde le contenu lisible pour ce texte simple
    assert result.endswith(written["path"])
    # la demande complete est passee au script via une variable d'env,
    # jamais collee dans son code
    assert f"SHSS_REQUEST={shlex.quote(request)}" in result
    assert request not in Path(written["path"]).read_text()
    # le script lui-meme, sur disque, ne contient jamais le payload en dur
    assert payload not in Path(written["path"]).read_text()

    events = read_events()
    assert events[0]["kind"] == "case"
    assert events[0]["result"] == result


def test_generate_bash_plain_case_match_still_gets_request_env_var(monkeypatch, tmp_path):
    # Un cas sans "input" garde le comportement d'avant (pas de pipe),
    # mais dispose quand meme de SHSS_REQUEST.
    import shlex

    import shss.cases as cases_module

    llm = _fake_shss(monkeypatch, tmp_path, "ne devrait jamais etre lu")
    case = {"id": "energie", "requests": ["x"], "script": "#!/usr/bin/env bash\necho watts\n"}
    monkeypatch.setattr(cases_module, "best_match", lambda request, **kw: (case, 0.9, None))

    result = llm.generate_bash("energie consommee par le pc")

    assert "printf" not in result  # pas de pipe, contrairement a un cas gabarit
    assert result.startswith(f"SHSS_REQUEST={shlex.quote('energie consommee par le pc')} ")
    assert result.endswith(".sh")
