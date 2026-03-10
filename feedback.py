"""Per-idea feedback counts (helpful / not helpful)."""
import json
from pathlib import Path

_FEEDBACK_PATH = Path(__file__).parent / "feedback.json"


def _load() -> dict:
    if not _FEEDBACK_PATH.exists():
        return {}
    with open(_FEEDBACK_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_FEEDBACK_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def add(idea_id: int, helpful: bool) -> None:
    data = _load()
    key = str(idea_id)
    if key not in data:
        data[key] = {"up": 0, "down": 0}
    if helpful:
        data[key]["up"] = data[key].get("up", 0) + 1
    else:
        data[key]["down"] = data[key].get("down", 0) + 1
    _save(data)


def get(idea_id: int) -> tuple[int, int]:
    data = _load()
    key = str(idea_id)
    if key not in data:
        return 0, 0
    return data[key].get("up", 0), data[key].get("down", 0)


def get_top_idea_ids(limit: int = 5) -> list[int]:
    """Return idea_ids sorted by helpful ratio (up / (up+down+1)), then by up count. At least one vote."""
    data = _load()
    scored = []
    for idea_id_str, v in data.items():
        up = v.get("up", 0)
        down = v.get("down", 0)
        if up + down == 0:
            continue
        try:
            idea_id = int(idea_id_str)
        except ValueError:
            continue
        ratio = up / (up + down + 1)
        scored.append((idea_id, ratio, up))
    scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return [x[0] for x in scored[:limit]]
