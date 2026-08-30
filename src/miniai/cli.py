import argparse
import sys

from . import __version__
from .llm import MiniLLM, ResolutionCancelled
from .shell import PersistentShell
from .tags import expand_line, resolve_pending_tag


def ask_confirm(text: str) -> bool:
    """Show what miniai would insert/run and ask for a yes/no."""
    print(f"\nminiai propose :\n{text}\n")
    reply = input("Utiliser ce résultat ? [O/n] ").strip().lower()
    return reply in ("", "o", "oui", "y", "yes")


def build_key_bindings(llm: MiniLLM):
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add("c-g")
    def _(event):
        """Resolve the #@ ... currently being typed, without waiting for @# + Enter."""
        buf = event.app.current_buffer

        def resolver(request: str, prefix: str, suffix: str) -> str:
            def confirm(text: str) -> bool:
                answer = {}
                event.app.run_in_terminal(lambda: answer.setdefault("ok", ask_confirm(text)))
                return answer.get("ok", False)

            try:
                return llm.generate_bash(request, prefix, suffix, confirm=confirm)
            except ResolutionCancelled:
                raise
            except Exception as exc:  # pragma: no cover - interactive feedback only
                return f"<miniai llm error: {exc}>"

        try:
            new_text, new_point = resolve_pending_tag(buf.text, buf.cursor_position, resolver)
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
            return f"echo 'miniai llm error: {exc}' 1>&2"

    try:
        while True:
            try:
                line = session.prompt(f"miniai:{shell.cwd()}$ ")
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
        print("miniai: historique vide")
        return 0

    for e in events:
        arrow = f"{e['request']!r} -> {e['result']!r}"
        print(f"[{e['timestamp']}] {e['kind']:6} {arrow}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miniai",
        description=(
            "Console bash augmentée : les blocs #@ ... @# dans une ligne "
            "sont résolus par un LLM local avant exécution."
        ),
    )
    parser.add_argument("--version", action="version", version=f"miniai {__version__}")
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
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.history is not None:
        return print_history(args.history)

    llm = MiniLLM()

    if args.command is not None:
        return run_once(llm, args.command)

    return repl(llm)


if __name__ == "__main__":
    sys.exit(main())
