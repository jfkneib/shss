import json
import os
import time
from pathlib import Path


def _history_path() -> Path:
    override = os.environ.get("SHSS_HISTORY_PATH")
    if override:
        return Path(override)
    return Path.home() / ".shss" / "history.jsonl"


def log_event(request: str, prefix: str, suffix: str, result: str, kind: str) -> None:
    """Append one resolved #@ ... @# to the history file (JSON Lines)."""
    path = _history_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "request": request,
        "prefix": prefix,
        "suffix": suffix,
        "kind": kind,
        "result": result,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_events(limit: int = 20):
    """Return the last `limit` history entries, oldest first."""
    path = _history_path()
    if not path.is_file():
        return []

    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events[-limit:]
