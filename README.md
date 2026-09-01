# shss

***SH**ell **S**imple **S**uggestion*

*English version. Version française : [LISEZMOI.md](LISEZMOI.md).*

An augmented bash console: on any line, a `#@ request @#` block is resolved
by a small local LLM before execution and replaced in place with bash. The
rest of the line is ordinary bash, run in a real persistent bash session
(`cd`, environment variables, etc. are kept from one line to the next).

> The built-in few-shot prompt is written in **French** (see
> `src/shss/llm.py`). English requests work, but French is what the model
> is tuned for here.

## Install via a Debian package (.deb)

The simplest option for everyday use — installs everything (Python
dependencies in a dedicated venv, the GGUF model, the `Ctrl-G` integration
in `~/.bashrc`, a man page) with no manual steps:

```bash
./packaging/build.sh
sudo apt install ./shss_0.2.2_all.deb
```

The package installs into `/opt/shss/` (Python venv, model, code), the
`shss` / `shss-resolve-inline` commands into `/usr/bin/`, and a man page
(`man shss`). It reuses a model already present through Ollama if it finds
one, otherwise downloads it from Hugging Face (~950 MB). It also adds
`source .../shell-integration/shss.bash` to the `~/.bashrc` of the user who
ran `sudo` (the `$SUDO_USER` variable) — if that can't be detected, the
line to add manually is printed at the end of the install.

Full details (package contents, `postinst`/`postrm` scripts, removal) in
[packaging/](packaging/).

## Install via Docker

To **try** shss without installing anything on the host, or to distribute
it through a registry. Inside a container, shss augments the **container's**
bash (not the host's): ideal for `-c` mode and demos; for the `Ctrl-G`
integration in your `~/.bashrc`, use the `.deb` package.

Build the images (once):

```bash
docker build --target cpu  -t shss:cpu  .    # ~400 MB on disk, CPU inference
docker build --target cuda -t shss:cuda .    # ~10 GB, GPU required (--gpus all)
```

The `cuda` image bundles the prebuilt CUDA `llama-cpp-python` wheel (no
compilation); it **only runs with `--gpus all`** on a host that has the
NVIDIA driver (`libcuda.so.1` is provided by the container runtime at
launch) — there is no CPU fallback. For CPU, use the `cpu` image.

Then, via the wrapper:

```bash
./run.sh                                 # REPL
./run.sh -c 'ls #@ sort by size @#'      # one-shot
```

`run.sh` mounts the current directory at `/work`, keeps the model in a
`shss-models` volume (downloaded once, ~941 MB for `1.5b-base`), passes
`--gpus all` automatically if an NVIDIA GPU is detected, and sets
`SHSS_N_THREADS` to the core count.

The model is **not** in the image; the entrypoint downloads it on first
launch from the curated list in [`src/shss/llm.py`](src/shss/llm.py).
Pick a bigger model:

```bash
SHSS_MODEL_TAG=7b ./run.sh pull   # download once into the volume
SHSS_MODEL_TAG=7b ./run.sh        # then use it
```

Without the wrapper:

```bash
docker volume create shss-models
docker run --rm -it \
  -v shss-models:/models -v "$PWD:/work" -w /work \
  shss:cpu
```

The resolution history is written to the volume
(`/models/history.jsonl`), so it persists. A **script-mode** result,
however, is written to the container's `/tmp`: the printed path is not
reachable from the host (an inherent container limitation — the one-line
fragment mode runs normally in `/work`).

`compose` alternative (`gpu` profile included): see
[compose.yaml](compose.yaml). The **`cpu`** image is published to GHCR on
every `v*` tag (`ghcr.io/jfkneib/shss:<version>` + `:latest`) and on
`main` (`:edge`) — see [.github/workflows/docker.yml](.github/workflows/docker.yml);
the `cuda` image is built locally.

**Podman**: `podman` replaces `docker` in all the commands above
(`podman build`, `podman compose build`, `podman pull …`). For the GPU,
podman uses `--device nvidia.com/gpu=all` instead of `--gpus all`;
`run.sh` remains Docker-specific.

### Performance tuning (env vars)

| Variable | Effect |
| --- | --- |
| `SHSS_N_THREADS` | number of inference threads — set to the number of **physical** cores (llama.cpp often guesses badly in a container); `run.sh` uses `nproc` |
| `SHSS_N_CTX` | context window (default 2048) — `1024` is plenty for the few-shot prompt + a file preview, and cuts RAM and prompt-eval time |
| `SHSS_N_GPU_LAYERS` | `auto` (default): offload everything if `nvidia-smi` is present, nothing otherwise. An integer forces the value. No effect on a llama.cpp binary built without CUDA (so the `cpu` image ignores the variable). |
| `SHSS_MODEL_TAG` | `0.5b`, `1.5b-base` (default), `3b`, `7b` — the GPU adds almost nothing below 1.5b, but becomes useful at 7b |

Give the container enough resources: `--cpus 4` minimum, and
`--memory` ≥ 1.5 GB (1.5b) / 6 GB (7b).

## Updating

Depending on how it was installed:

| Installed via | Update |
| --- | --- |
| `.deb` package | `cd <checkout> && git pull && ./packaging/build.sh && sudo apt install ./shss_<version>_all.deb` |
| git checkout only | `git pull` (nothing else) |
| Docker | `docker pull ghcr.io/jfkneib/shss:latest` (or `git pull && docker build --target cpu -t shss:cpu .`) |

In every case, what is **kept**: the GGUF model (never re-downloaded), the
Python venv, the `~/.bashrc` line, and your settings (`SHSS_MODEL_TAG`,
`SHSS_MODEL_PATH`… live in `~/.bashrc`, not in the package). The Docker
model lives in the `shss-models` volume, also preserved.

**`.deb` gotcha**: `apt install ./file.deb` only updates if the version is
**higher** — every release bumps `src/shss/__init__.py`. To force the same
version: `sudo apt install --reinstall ./shss_<version>_all.deb`.

### Via apt (`sudo apt upgrade`)

On every `v*` tag, CI publishes the `.deb` both as an asset on the
[Release](https://github.com/jfkneib/shss/releases) **and** in a flat apt
repo on the `apt` branch. Since the GitHub repo is private, apt
authenticates to it with a personal token (`repo` scope, read-only is
enough):

```bash
# 1. authentication (token in a root-only readable file)
sudo tee /etc/apt/auth.conf.d/shss.conf >/dev/null <<'EOF'
machine raw.githubusercontent.com
login x-access-token
password ghp_YOUR_TOKEN_HERE
EOF
sudo chmod 600 /etc/apt/auth.conf.d/shss.conf

# 2. the apt source
echo 'deb [trusted=yes] https://raw.githubusercontent.com/jfkneib/shss/apt/ ./' \
  | sudo tee /etc/apt/sources.list.d/shss.list

# 3. install, then update like any other package
sudo apt update && sudo apt install shss
sudo apt upgrade            # on every new release
```

Notes:

- `[trusted=yes]`: the repo is not GPG-signed yet (to be added).
- the auth file applies to **all** of `raw.githubusercontent.com` —
  acceptable on a personal machine.
- `raw.githubusercontent.com` has a CDN cache (~5 min): an `apt update`
  right after a release may not see the new version immediately.

Switch to a smaller/bigger model afterwards:

```bash
sudo shss -c '#@ model download 0.5b @#'   # once (shared machine-wide)
echo 'export SHSS_MODEL_TAG=0.5b' >> ~/.bashrc && source ~/.bashrc
```

## Usage (from a git checkout, no package)

```bash
./bin/shss
shss:/home/jfk$ ls #@ also show hidden files @#
→ ls -la
...

shss:/home/jfk$ exit
```

Several requests can appear on the same line, mixed with plain bash:

```bash
ls #@ first request @#  #@ second request @#
```

One-shot mode (like `bash -c`):

```bash
./bin/shss -c 'ls #@ also show hidden files @#'
```

In the REPL, `Ctrl-G` immediately resolves the tag nearest the cursor —
whether it is already closed with `@#` or still being typed — without
waiting for Enter. Before applying the result, `Ctrl-G` shows what would
be inserted (the fragment, or the full script source in script mode) and
asks for confirmation:

```text
shss propose :
-S

Utiliser ce résultat ? [O/n]
```

Answering no (`n`) leaves the line unchanged, as if `Ctrl-G` had not been
pressed — in the REPL, nothing is written or logged until you confirm.
This confirmation only exists for `Ctrl-G` — automatic resolution of an
already-closed tag on Enter (REPL or `-c`) stays direct, with no prompt,
so as not to break non-interactive uses.

### Integration in your normal bash console (without ./bin/shss)

`Ctrl-G` can also be wired directly into your usual bash session (no need
to run `./bin/shss`):

```bash
echo 'source /home/jfk/git/dev/shss/shell-integration/shss.bash' >> ~/.bashrc
```

Unlike the REPL, there is **no** yes/no confirmation here: reading a
keypress from a `bind -x` function proved unreliable — tested and
confirmed on a real machine (Terminator terminal): even a minimal `read`,
unrelated to shss, received no keystrokes (a known bash pitfall, not a
shss bug — see `shell-integration/shss.bash` for details). So `Ctrl-G`
shows what was generated (useful mostly in script mode, where the line
only shows a file path) then applies it **directly** — the line stays
editable before Enter, like any bash command, which serves as the check.

Details, limits, and a pitfall to know about (bash treats `#@ ... @#` as a
comment if you press Enter without going through `Ctrl-G` first) in
[docs/getting-started.md](docs/getting-started.md#7-intégration-dans-ta-console-bash-normale-sans-lancer-binshss)
(French).

## LLM model

The model used is `qwen2.5-coder:1.5b-base`, loaded **directly** through
[`llama-cpp-python`](https://github.com/abetlen/llama-cpp-python) (Python
binding for llama.cpp) — no Ollama server at runtime. The `.gguf` file
already downloaded by Ollama for that model is reused as-is (see
`src/shss/llm.py::discover_gguf_path`), without re-downloading it.

To point at another `.gguf` file:

```bash
export SHSS_MODEL_PATH=/path/to/model.gguf
```

**Ollama is not required.** The code never runs the `ollama` binary nor
contacts a server — it just reads a `.gguf` file on disk. Ollama is only a
convenient shortcut to obtain that file without downloading it yourself
(via `discover_gguf_path`, which reads the manifest Ollama left on disk).
Without Ollama installed, `SHSS_MODEL_PATH` pointing at any `.gguf`
(downloaded from Hugging Face, for example) is enough for shss to work the
same way.

**Caveat for the utility commands (next section):** `#@ models @#`,
`#@ model <tag> @#` and `Ctrl-Y` can only list/offer models **already
managed by Ollama** — that is the only model "registry" available on
disk, there is no generic equivalent for a standalone `.gguf`. Without
Ollama, `#@ models @#` says so clearly and still shows the actually active
model (the one pointed at by `SHSS_MODEL_PATH`) rather than implying
nothing is configured; to change model in that case, change
`SHSS_MODEL_PATH` yourself.

## Scripts and history

For a request too complex to fit on one line (several steps, a file
transformation…), the model can answer with a full script instead of a
bash fragment — it picks the language itself (Python, bash, …) via the
shebang line at the top of its answer (`#!/usr/bin/env python3`,
`#!/usr/bin/env bash`, …). The script is written to a temp file named by
date + a unique id (`/tmp/shss-<uid>/20260830-161859_d80a29.py`), made
executable, and that path replaces the tag in the line:

```bash
#@ format the file /tmp/dede.txt as json and write the result to /tmp/result.json @#
# → /tmp/shss-1000/20260830-161859_d80a29.py
```

Tested for real: it works, but with the same reliability limits as
elsewhere on this 1.5B model (e.g. it may drift slightly from the
requested file name, or fail to handle a complex data structure).

To help the model write a script matched to the **actual content** of a
file rather than guessing, a preview (first few lines) of any file
explicitly named in the request is slipped into the hidden prompt
(`src/shss/context.py::build_context`) — invisible to the user, who still
only sees what they type. On a CSV with a header, the result is clean
(uses `csv.DictReader`, good key names); on a less standard format (e.g.
`;`-separated values with no header), the model knows it should use the
`csv` module but does not always detect the right separator on its own.
Deliberately, **no listing of the current directory is added by default**:
an early version did it systematically and it broke simple requests
unrelated to files (`ls #@ sort by size @#` produced a nonsensical result
because of that irrelevant noise) — only a file explicitly mentioned (and
that exists) triggers a preview.

Every resolution (fragment or script) is recorded in a history —
`~/.shss/history.jsonl`, one JSON line per entry (timestamp, request,
result, type):

```bash
shss --history        # the last 20 resolutions
shss --history 50     # the last 50
```

`--history` does not need to load the model, so it is instant.

## Utility commands

Some requests between `#@ ... @#` are recognized and handled directly by
shss — never sent to the LLM, so instant:

```bash
#@ models @#                 # list Ollama + curated models, mark the active one
#@ model 3b @#                # switch model (e.g. 3b, or deepseek-coder:1.3b)
#@ model download 3b @#       # download a curated model (no Ollama)
#@ history 10 @#              # same as shss --history 10
#@ help @#                    # recall these commands
```

`#@ model <tag> @#` switches the model for the rest of the current
**REPL** session; in `-c` mode or via `Ctrl-G` in a normal console, each
call starts a fresh process, so the change does not survive that single
resolution — export `SHSS_MODEL_TAG` in `~/.bashrc` for a permanent
change, or use the `Ctrl-Y` picker below, which does persist for the whole
terminal session.

### Models downloadable without Ollama

`#@ models @#` always lists, in addition to Ollama models, a **curated**
list of `qwen2.5-coder` models downloadable directly from Hugging Face
(URLs checked by hand, Q4_K_M, except `0.5b` in Q8_0) — that is the only
family tested/reliable with this project's prompt (see "Known
limitations"). This covers the "no Ollama installed" case:

```bash
#@ model download 3b @#   # downloads ~1.9 GB
#@ model 3b @#             # activates it for the current REPL session
```

To activate it **permanently** (including in `-c` mode and via `Ctrl-G`),
once the file is downloaded:

```bash
export SHSS_MODEL_TAG=3b   # in ~/.bashrc; discover_gguf_path() finds
                           # the already-downloaded curated model
```

Currently in the list: `0.5b` (~506 MB, Q8_0), `1.5b-base` (~941 MB, the
default), `3b` (~1.9 GB), `7b` (~4.5 GB). `0.5b` is the lightest (very
constrained machine, minimal latency) at the cost of lower quality on
compound requests. The download is blocking and can take a while
depending on the connection; it only triggers on this explicit command,
never automatically.

**Model licenses.** `0.5b`, `1.5b-base` and `7b` are under **Apache 2.0**
(free use, including commercial). `3b` is the exception: **Qwen Research
License**, so **non-commercial / research use only** — the only one in the
list in that situation. shss ships no weights (it downloads them from
Hugging Face or reuses Ollama's), so distributing shss itself raises no
model-license question; what matters is how you use the model.

**Storage — shared when possible, per-user otherwise** (the `.gguf` file
is shared so it is not re-downloaded, but **which** model is active always
stays an individual, per-session choice):

- Run with `sudo` (e.g. `sudo shss -c '#@ model download 3b @#'`), the
  download goes to `/opt/shss/models/` — one download, **shared by all
  users on the machine**, consistent with the Debian package install
  ("installed once, everyone benefits").
- Without `sudo`, it goes to `~/.shss/models/` (per-user) — a normal user
  cannot write to `/opt/shss/`.
- `#@ models @#` and `#@ model <tag> @#` always check the shared location
  first, before the user's — if an admin already downloaded a model for
  everyone, nobody else needs to redo it.

### Interactive model picker (Ctrl-Y)

If [`fzf`](https://github.com/junegunn/fzf) is installed
(`sudo apt install fzf`), `Ctrl-Y` (in a console where
`shell-integration/shss.bash` is sourced) opens a real
filterable/keyboard-navigable list of the available models. The choice
becomes active for the rest of the terminal session (`export
SHSS_MODEL_NAME`/`SHSS_MODEL_TAG` in the current shell).

This was only possible after checking that `fzf` handles the terminal
correctly in a `bind -x` context on this machine — unlike bash's `read`,
which could not (see the previous section on the `Ctrl-G` confirmation
removed for the same reason). `Ctrl-Y` overrides the default readline
binding (`yank`, paste the last killed text) — change the key in
`shell-integration/shss.bash` if you use it.

## Known limitations

`qwen2.5-coder:1.5b-base` is a small base model with a minimal few-shot
prompt (see `src/shss/llm.py`) — it does not always understand the whole
request, especially when it **combines several criteria**. Observed
example:

```bash
ls #@ show text files sorted by size @#
# → ls -S   (the sort is taken into account, the "text files" filter is ignored)
```

Also tested with a few-shot example dedicated to that exact case (filter +
sort): no improvement, even on a request almost identical to the example.
So it is not a missing-examples problem but a capacity limit of the 1.5B
model on that kind of compound reasoning — a bigger model (3B/7B) would be
needed to make this kind of request reliable, at the cost of higher
latency.

The mechanism itself (tag detection, in-place injection, execution) works
correctly in every tested case — it is the generation quality that varies
with request complexity.

Another pitfall observed and fixed: without a repetition penalty,
`llama-cpp-python` can make the model loop on a degenerate pattern until
the `max_tokens` cutoff — e.g. a complex request generated
`grep -E "^[^ ]+ [^ ]+ [^ ]+ ..."` repeated dozens of times, a broken
fragment (a quote never closed) that hung bash waiting for the end of the
command. `repeat_penalty=1.1` (see `generate_bash` in `llm.py`) fixes that
class of bug; a more aggressive value (tested at 1.3) instead degraded a
case that worked well (the `█` prompt character leaking into a generated
script) — `1.1` is the compromise kept after that test.

## Repository layout

```text
bin/shss                 bash entry point for the REPL (uses .venv if present)
bin/shss-resolve-inline  entry point for the Ctrl-G bash integration
shell-integration/
  shss.bash              to source in ~/.bashrc: "native" Ctrl-G, Ctrl-Y (fzf)
src/shss/
  cli.py                   REPL / -c / --history / --list-models, Ctrl-G
  inline.py                one-off resolution (used by bin/shss-resolve-inline)
  tags.py                  detection/replacement of #@ ... @# tags
  llm.py                   GGUF model, prompt, fragment/script dispatch, model list
  commands.py              utility commands (models, model, history, help)
  history.py               JSONL log of resolutions (~/.shss/history.jsonl)
  context.py               preview of mentioned files, injected into the hidden prompt
  shell.py                 persistent bash session (sentinel-based)
tests/                     tests (do not load the model, unless noted otherwise)
docs/                      documentation
```

## Development

Requirements: Python 3.9+, bash, an accessible `qwen2.5-coder:1.5b-base`
GGUF model (already present through Ollama, or `SHSS_MODEL_PATH`).

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
./.venv/bin/python -m pytest
```

The tests import neither `llama-cpp-python` nor `prompt_toolkit` (deferred
imports everywhere), so `pip install -r requirements-dev.txt` alone is
enough to run `pytest`.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
