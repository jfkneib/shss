import argparse
import sys

from . import __version__
from .llm import MiniLLM, ResolutionCancelled
from .shell import PersistentShell
from .tags import expand_line, resolve_pending_tag


def ask_confirm(text: str) -> bool:
    """Show what shss would insert/run and ask for a yes/no."""
    print(f"\nshss propose :\n{text}\n")
    reply = input("Utiliser ce résultat ? [O/n] ").strip().lower()
    return reply in ("", "o", "oui", "y", "yes")


def build_key_bindings(llm: MiniLLM):
    from prompt_toolkit.application import run_in_terminal
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add("c-g")
    async def _(event):
        """Resolve the #@ ... currently being typed, without waiting for @# + Enter."""
        buf = event.app.current_buffer

        def resolver(request: str, prefix: str, suffix: str) -> str:
            try:
                return llm.generate_bash(request, prefix, suffix, confirm=ask_confirm)
            except ResolutionCancelled:
                raise
            except Exception as exc:  # pragma: no cover - interactive feedback only
                return f"<shss llm error: {exc}>"

        def do_resolve():
            return resolve_pending_tag(buf.text, buf.cursor_position, resolver)

        # run_in_terminal hands the real terminal back for the duration of
        # do_resolve() — needed because ask_confirm() blocks on input(),
        # which prompt_toolkit's own raw-mode rendering would otherwise
        # swallow (Application has no run_in_terminal *method*; this is
        # the standalone async function, awaited from an async handler).
        try:
            new_text, new_point = await run_in_terminal(do_resolve)
        except ResolutionCancelled:
            return
        buf.text = new_text
        buf.cursor_position = new_point

    return kb


def repl(llm: MiniLLM) -> int:
    from prompt_toolkit import PromptSession

    shell = PersistentShell()
    session = PromptSession(key_bindings=build_key_bindings(llm))

    def resolver(request: str, prefix: str, suffix: str) -> str:
        try:
            return llm.generate_bash(request, prefix, suffix)
        except Exception as exc:
            return f"echo 'shss llm error: {exc}' 1>&2"

    try:
        while True:
            try:
                line = session.prompt(f"shss:{shell.cwd()}$ ")
            except (EOFError, KeyboardInterrupt):
                break

            if not line.strip():
                continue
            if line.strip() in ("exit", "quit"):
                break

            expanded = expand_line(line, resolver)
            if expanded != line:
                print(f"→ {expanded}")

            output, _ = shell.run(expanded)
            if output:
                print(output, end="")
    finally:
        shell.close()

    return 0


def run_once(llm: MiniLLM, line: str) -> int:
    shell = PersistentShell()
    try:
        expanded = expand_line(line, llm.generate_bash)
        if expanded != line:
            print(f"→ {expanded}")
        output, code = shell.run(expanded)
        if output:
            print(output, end="")
        return code
    finally:
        shell.close()


def print_history(limit: int) -> int:
    from .history import read_events

    events = read_events(limit)
    if not events:
        print("shss: historique vide")
        return 0

    for e in events:
        arrow = f"{e['request']!r} -> {e['result']!r}"
        print(f"[{e['timestamp']}] {e['kind']:6} {arrow}")
    return 0


def print_models() -> int:
    """One "name:tag" per line, plain — meant for piping (e.g. into
    fzf, see shell-integration/shss.bash's model picker), as well as
    for direct use.

    Lists every model that can actually be switched to right now: the
    Ollama-managed ones, plus any curated model already downloaded (a
    machine without Ollama would otherwise get an empty list even after
    `#@ model download <tag> @#`). Curated models not yet downloaded are
    left out on purpose — `#@ models @#` shows those, with their size.
    """
    from pathlib import Path

    from .llm import (
        CURATED_MODEL_FAMILY,
        CURATED_MODELS,
        curated_model_path,
        list_local_models,
    )

    seen = set()
    for name, tag in list_local_models():
        print(f"{name}:{tag}")
        seen.add((name, tag))

    for tag in CURATED_MODELS:
        key = (CURATED_MODEL_FAMILY, tag)
        if key not in seen and Path(curated_model_path(tag)).is_file():
            print(f"{CURATED_MODEL_FAMILY}:{tag}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shss",
        description=(
            "Console bash augmentée : les blocs #@ ... @# dans une ligne "
            "sont résolus par un LLM local avant exécution."
        ),
    )
    parser.add_argument("--version", action="version", version=f"shss {__version__}")
    parser.add_argument(
        "-c",
        dest="command",
        help="Exécute une seule ligne (comme bash -c) puis quitte, au lieu de lancer le REPL.",
    )
    parser.add_argument(
        "--history",
        nargs="?",
        const=20,
        type=int,
        metavar="N",
        help="Affiche les N dernières résolutions (défaut 20) puis quitte.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help=(
            "Liste les modèles activables (Ollama + curatés téléchargés), "
            "une ligne 'nom:tag' par modèle, puis quitte."
        ),
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.history is not None:
        return print_history(args.history)

    if args.list_models:
        return print_models()

    llm = MiniLLM()

    if args.command is not None:
        return run_once(llm, args.command)

    return repl(llm)


if __name__ == "__main__":
    sys.exit(main())
