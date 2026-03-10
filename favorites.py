"""Per-user favorite idea IDs stored in a JSON file."""
import json
from pathlib import Path

_FAVORITES_PATH = Path(__file__).parent / "favorites.json"


def _load_all() -> dict:
    if not _FAVORITES_PATH.exists():
        return {}
    with open(_FAVORITES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_FAVORITES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add_favorite(user_id: int, idea_id: int) -> bool:
    """Add idea to user's favorites. Returns True if added, False if already present."""
    data = _load_all()
    key = str(user_id)
    if key not in data:
        data[key] = []
    if idea_id in data[key]:
        return False
    data[key].append(idea_id)
    _save(data)
    return True


def remove_favorite(user_id: int, idea_id: int) -> bool:
    """Remove idea from user's favorites. Returns True if removed, False if not present."""
    data = _load_all()
    key = str(user_id)
    if key not in data or idea_id not in data[key]:
        return False
    data[key].remove(idea_id)
    _save(data)
    return True


def get_favorites(user_id: int) -> list[int]:
    """Return list of idea IDs saved by the user."""
    data = _load_all()
    return list(data.get(str(user_id), []))


def delete_user(user_id: int) -> None:
    """Remove all favorites for this user (for privacy / delete my data)."""
    data = _load_all()
    key = str(user_id)
    if key in data:
        del data[key]
        _save(data)
