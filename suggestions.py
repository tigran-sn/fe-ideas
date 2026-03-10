"""User-submitted ideas pending admin approval."""
import json
from pathlib import Path

_SUGGESTIONS_PATH = Path(__file__).parent / "suggestions.json"
_next_id = 0


def _load() -> list[dict]:
    if not _SUGGESTIONS_PATH.exists():
        return []
    with open(_SUGGESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: list[dict]) -> None:
    with open(_SUGGESTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add(title: str, description: str, from_user_id: int, from_username: str | None,
        difficulty: str | None = None, category: str | None = None) -> dict:
    """Append a suggestion; returns the new suggestion with id."""
    data = _load()
    new_id = max([s.get("id", -1) for s in data], default=-1) + 1
    entry = {
        "id": new_id,
        "title": title.strip(),
        "description": description.strip(),
        "from_user_id": from_user_id,
        "from_username": from_username or "",
    }
    if difficulty and (d := difficulty.strip().lower()):
        entry["difficulty"] = d
    if category and (c := category.strip().lower()):
        entry["category"] = c
    data.append(entry)
    _save(data)
    return entry


def get_all() -> list[dict]:
    return _load()


def get_by_id(suggestion_id: int) -> dict | None:
    for s in _load():
        if s.get("id") == suggestion_id:
            return s
    return None


def remove(suggestion_id: int) -> bool:
    data = _load()
    new_data = [s for s in data if s.get("id") != suggestion_id]
    if len(new_data) == len(data):
        return False
    _save(new_data)
    return True
