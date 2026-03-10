"""Per-user set of idea IDs already shown (to reduce repeats)."""
import json
from pathlib import Path

_SEEN_PATH = Path(__file__).parent / "seen.json"


def _load_all() -> dict:
    if not _SEEN_PATH.exists():
        return {}
    with open(_SEEN_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_seen(user_id: int, idea_id: int) -> None:
    """Mark an idea as seen for this user (idempotent)."""
    data = _load_all()
    key = str(user_id)
    if key not in data:
        data[key] = []
    if idea_id not in data[key]:
        data[key].append(idea_id)
        _save(data)


def get_seen(user_id: int) -> list[int]:
    """Return list of idea IDs already shown to this user."""
    data = _load_all()
    return list(data.get(str(user_id), []))


def clear_seen(user_id: int) -> None:
    """Clear all seen ideas for this user (e.g. when all have been shown)."""
    data = _load_all()
    key = str(user_id)
    if key in data:
        data[key] = []
        _save(data)
