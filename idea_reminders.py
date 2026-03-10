"""Remind user about a specific idea after N days."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REMINDERS_PATH = Path(__file__).parent / "idea_reminders.json"


def _load() -> list[dict]:
    if not _REMINDERS_PATH.exists():
        return []
    with open(_REMINDERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: list[dict]) -> None:
    with open(_REMINDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add(user_id: int, chat_id: int, idea_id: int, days: int) -> None:
    now = datetime.now(timezone.utc)
    remind_at = (now + timedelta(days=days)).replace(hour=now.hour, minute=now.minute)
    entry = {
        "user_id": user_id,
        "chat_id": chat_id,
        "idea_id": idea_id,
        "remind_at": remind_at.isoformat(),
    }
    data = _load()
    data.append(entry)
    _save(data)


def get_due() -> list[tuple[int, int, int]]:
    """Return list of (chat_id, idea_id, user_id) where remind_at <= now. Removes them after."""
    now = datetime.now(timezone.utc)
    data = _load()
    due = []
    remaining = []
    for e in data:
        try:
            at = datetime.fromisoformat(e["remind_at"].replace("Z", "+00:00"))
            if at <= now:
                due.append((int(e["chat_id"]), int(e["idea_id"]), int(e["user_id"])))
            else:
                remaining.append(e)
        except (KeyError, ValueError):
            continue
    if due:
        _save(remaining)
    return due


def remove_by_user(user_id: int) -> None:
    """Remove all idea reminders for this user (for privacy / delete my data)."""
    data = _load()
    uid = int(user_id)
    remaining = [e for e in data if int(e.get("user_id", -1)) != uid]
    if len(remaining) != len(data):
        _save(remaining)
