"""Per-user last request date and streak (consecutive days)."""
import json
from datetime import date, timedelta, timezone
from pathlib import Path

_ACTIVITY_PATH = Path(__file__).parent / "activity.json"


def _load() -> dict:
    if not _ACTIVITY_PATH.exists():
        return {}
    with open(_ACTIVITY_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_ACTIVITY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _today_iso() -> str:
    return date.today().isoformat()


def record_request(user_id: int) -> None:
    today = _today_iso()
    data = _load()
    key = str(user_id)
    prev = data.get(key, {})
    last = prev.get("last_date")
    streak = prev.get("streak", 0)
    if last != today:
        try:
            last_d = date.fromisoformat(last) if last else None
        except ValueError:
            last_d = None
        today_d = date.fromisoformat(today)
        if last_d is not None and (today_d - last_d).days == 1:
            streak = (streak or 0) + 1
        else:
            streak = 1
        data[key] = {"last_date": today, "streak": streak}
        _save(data)


def get_streak(user_id: int) -> int:
    """Return current streak (consecutive days). 0 if no activity or streak broken."""
    data = _load()
    key = str(user_id)
    if key not in data:
        return 0
    last = data[key].get("last_date")
    today = _today_iso()
    if last != today:
        return 0
    return data[key].get("streak", 0)


def delete_user(user_id: int) -> None:
    """Remove activity data for this user (for privacy / delete my data)."""
    data = _load()
    key = str(user_id)
    if key in data:
        del data[key]
        _save(data)
