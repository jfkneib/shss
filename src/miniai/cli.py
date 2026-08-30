import argparse
import sys

from . import __version__
from .llm import MiniLLM
from .shell import PersistentShell
from .tags import expand_line


def build_key_bindings(llm: MiniLLM):
    from prompt_toolkit.key_binding import KeyBindings

    kb = KeyBindings()

    @kb.add("c-g")
    def _(event):
        """Resolve the #@ ... currently being typed, without waiting for @# + Enter."""
        buf = event.app.current_buffer
        text = buf.text
        cursor = buf.cursor_position
        before = text[:cursor]

        idx = before.rfind("#@")
        if idx == -1 or "@#" in before[idx:]:
            return

        request = before[idx + 2 :]
        try:
            fragment = llm.generate_bash(request)
        except Exception as exc:  # pragma: no cover - interactive feedback only
            fragment = f"<miniai llm error: {exc}>"

        buf.text = text[:idx] + fragment + text[cursor:]
        buf.cursor_position = idx + len(fragment)

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
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    llm = MiniLLM()

    if args.command is not None:
        return run_once(llm, args.command)

    return repl(llm)


if __name__ == "__main__":
    sys.exit(main())
