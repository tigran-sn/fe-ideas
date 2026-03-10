"""Per-user list of idea IDs marked as 'I've done this'."""
import json
from pathlib import Path

_DONE_PATH = Path(__file__).parent / "done.json"


def _load() -> dict:
    if not _DONE_PATH.exists():
        return {}
    with open(_DONE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_DONE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add(user_id: int, idea_id: int) -> None:
    data = _load()
    key = str(user_id)
    if key not in data:
        data[key] = []
    if idea_id not in data[key]:
        data[key].append(idea_id)
        _save(data)


def get(user_id: int) -> list[int]:
    data = _load()
    return list(data.get(str(user_id), []))


def remove(user_id: int, idea_id: int) -> bool:
    data = _load()
    key = str(user_id)
    if key not in data or idea_id not in data[key]:
        return False
    data[key].remove(idea_id)
    _save(data)
    return True
