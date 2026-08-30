"""One-shot resolver used by the bash `bind -x` integration: given the
current readline buffer and cursor position, resolve the pending
`#@ ... ` tag (if any) and print the new line and new cursor position,
one per line, for the calling bash function to assign back to
READLINE_LINE / READLINE_POINT.
"""

import sys

from .llm import MiniLLM, ResolutionCancelled
from .tags import resolve_pending_tag


def ask_confirm(text: str) -> bool:
    """Show what miniai would insert/run and ask for a yes/no.

    Writes to stderr and reads stdin directly (not input(), whose prompt
    goes to stdout) so the exchange stays interactive in the terminal
    without polluting the stdout that shell-integration/miniai.bash
    captures via `out=$(...)`.
    """
    print(f"\nminiai propose :\n{text}\n", file=sys.stderr)
    print("Utiliser ce résultat ? [O/n] ", end="", file=sys.stderr, flush=True)
    reply = sys.stdin.readline().strip().lower()
    return reply in ("", "o", "oui", "y", "yes")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: miniai-resolve-inline <line> <cursor_point>", file=sys.stderr)
        return 2

    line, point = argv[0], int(argv[1])
    llm = MiniLLM()

    def resolver(request: str, prefix: str, suffix: str) -> str:
        try:
            return llm.generate_bash(request, prefix, suffix, confirm=ask_confirm)
        except ResolutionCancelled:
            raise
        except Exception as exc:
            return f"<miniai llm error: {exc}>"

    try:
        new_line, new_point = resolve_pending_tag(line, point, resolver)
    except ResolutionCancelled:
        new_line, new_point = line, point

    print(new_line)
    print(new_point)
    return 0


if __name__ == "__main__":
    sys.exit(main())
