import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from miniai.cli import build_parser


def test_parser_dash_c():
    args = build_parser().parse_args(["-c", "ls -la"])
    assert args.command == "ls -la"


def test_parser_no_args_means_repl():
    args = build_parser().parse_args([])
    assert args.command is None
