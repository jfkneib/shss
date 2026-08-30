"""One-shot resolver used by the bash `bind -x` integration.

Given the current readline buffer and cursor position, resolves the
pending `#@ ... ` tag (if any) and prints, to stdout:

    <new READLINE_LINE>
    <new READLINE_POINT>
    <display text, 0+ lines: what was generated, for the calling bash
     function to show and confirm before actually applying the two
     lines above>

The confirmation itself intentionally does NOT happen here: a `bind -x`
handler runs with the terminal left in whatever raw/non-canonical mode
bash's readline was using, so reading interactively from this Python
subprocess's stdin (even by hand, bypassing input()) doesn't reliably
see keystrokes or their echo. Bash's own `read` builtin, run directly in
shell-integration/miniai.bash, does not have that problem — so that's
where the actual "utiliser ce résultat ?" prompt lives.
"""

import sys

from .llm import MiniLLM
from .tags import resolve_pending_tag


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: miniai-resolve-inline <line> <cursor_point>", file=sys.stderr)
        return 2

    line, point = argv[0], int(argv[1])
    llm = MiniLLM()
    display_holder = {}

    def resolver(request: str, prefix: str, suffix: str) -> str:
        def record_display(text: str) -> bool:
            display_holder["text"] = text
            return True  # always proceed here; bash asks the real question

        try:
            return llm.generate_bash(request, prefix, suffix, confirm=record_display)
        except Exception as exc:
            return f"<miniai llm error: {exc}>"

    new_line, new_point = resolve_pending_tag(line, point, resolver)

    print(new_line)
    print(new_point)
    print(display_holder.get("text", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
