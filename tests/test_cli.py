import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from miniai.cli import complete


def test_complete_echoes_prompt():
    result = complete("def add(a, b):")
    assert "def add(a, b):" in result
