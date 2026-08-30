import argparse
import sys

from . import __version__


def complete(prompt: str) -> str:
    """Placeholder completion logic — wire up a real model call here."""
    return f"# TODO: completion for:\n{prompt}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miniai",
        description="CLI console de complétion de code assistée par IA.",
    )
    parser.add_argument("--version", action="version", version=f"miniai {__version__}")
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Texte ou code à compléter. Si absent, lu depuis stdin.",
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    prompt = args.prompt
    if prompt is None:
        prompt = sys.stdin.read()

    if not prompt.strip():
        parser.error("aucun prompt fourni (argument ou stdin)")

    print(complete(prompt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
