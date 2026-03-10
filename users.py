"""Store chat_id per user for broadcast (and analytics)."""
import json
from pathlib import Path

_USERS_PATH = Path(__file__).parent / "users.json"


def _load() -> dict:
    if not _USERS_PATH.exists():
        return {}
    with open(_USERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def record(user_id: int, chat_id: int) -> None:
    data = _load()
    key = str(user_id)
    data[key] = {"chat_id": chat_id}
    _save(data)


def get_all_chat_ids() -> list[int]:
    data = _load()
    return [int(v["chat_id"]) for v in data.values() if "chat_id" in v]


def delete_user(user_id: int) -> None:
    """Remove user from broadcast list (for privacy / delete my data)."""
    data = _load()
    key = str(user_id)
    if key in data:
        del data[key]
        _save(data)
