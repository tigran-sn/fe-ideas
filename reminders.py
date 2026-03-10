"""Per-user daily reminder (chat_id and optional time stored)."""
import json
from pathlib import Path

_REMINDERS_PATH = Path(__file__).parent / "reminders.json"


def _load() -> dict:
    if not _REMINDERS_PATH.exists():
        return {}
    with open(_REMINDERS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_REMINDERS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add(user_id: int, chat_id: int, time_str: str = "09:00") -> None:
    """time_str: "HH:MM" or "HH" in UTC (e.g. 09:00 or 9)."""
    data = _load()
    data[str(user_id)] = {"chat_id": chat_id, "time": (time_str or "09").strip() or "09"}
    _save(data)


def remove(user_id: int) -> bool:
    data = _load()
    key = str(user_id)
    if key not in data:
        return False
    del data[key]
    _save(data)
    return True


def set_time(user_id: int, time_str: str) -> None:
    data = _load()
    key = str(user_id)
    if key in data:
        data[key]["time"] = (time_str or "09").strip() or "09"
        _save(data)


def get_all_chat_ids() -> list[int]:
    """Return list of chat_ids to send daily idea to."""
    data = _load()
    return [int(v["chat_id"]) for v in data.values() if "chat_id" in v]


def get_chat_ids_for_hour(utc_hour: int, today_iso: str) -> list[tuple[int, int]]:
    """Return (user_id, chat_id) for users whose time matches this UTC hour and not yet sent today."""
    data = _load()
    out = []
    for uid, v in data.items():
        if "chat_id" not in v:
            continue
        if v.get("last_sent") == today_iso:
            continue
        t = (v.get("time") or "09").strip()
        if ":" in t:
            t = t.split(":")[0]
        try:
            h = int(t)
            if h == utc_hour:
                out.append((int(uid), int(v["chat_id"])))
        except ValueError:
            if utc_hour == 9:
                out.append((int(uid), int(v["chat_id"])))
    return out


def mark_sent(user_id: int, today_iso: str) -> None:
    data = _load()
    key = str(user_id)
    if key in data:
        data[key]["last_sent"] = today_iso
        _save(data)


def is_on(user_id: int) -> bool:
    return str(user_id) in _load()


def delete_user(user_id: int) -> None:
    """Remove reminder for this user (for privacy / delete my data)."""
    remove(user_id)


def get_time(user_id: int) -> str:
    data = _load()
    t = data.get(str(user_id), {}).get("time", "09")
    return t if ":" in t else f"{t}:00"
