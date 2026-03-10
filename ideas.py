import json
import random
from pathlib import Path

_IDEAS_PATH = Path(__file__).parent / "ideas.json"
_ideas_cache: list[dict] | None = None


def _invalidate_cache() -> None:
    """Clear the in-memory ideas cache so the next load reads from disk."""
    global _ideas_cache
    _ideas_cache = None


def _load_ideas() -> list[dict]:
    global _ideas_cache
    if _ideas_cache is None:
        with open(_IDEAS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _ideas_cache = []
        for i, idea in enumerate(raw):
            idea = idea.copy()
            idea["id"] = i
            _ideas_cache.append(idea)
    return _ideas_cache


def get_idea_by_id(idea_id: int) -> dict | None:
    """Return the idea with the given id, or None."""
    ideas = _load_ideas()
    for i in ideas:
        if i.get("id") == idea_id:
            return i.copy()
    return None


def get_random_idea() -> dict:
    """Return one random front-end project idea."""
    ideas = _load_ideas()
    return random.choice(ideas).copy()


def get_random_idea_unseen(
    seen_ids: list[int],
    done_ids: list[int] | None = None,
) -> tuple[dict, bool]:
    """Return a random idea, preferring ones not in seen_ids (and not in done_ids if given). Returns (idea, had_unseen)."""
    ideas = _load_ideas()
    seen_set = set(seen_ids)
    done_set = set(done_ids or [])
    unseen = [i for i in ideas if i.get("id") not in seen_set and i.get("id") not in done_set]
    if unseen:
        return random.choice(unseen).copy(), True
    unseen_any = [i for i in ideas if i.get("id") not in seen_set]
    if unseen_any:
        return random.choice(unseen_any).copy(), True
    return random.choice(ideas).copy(), False


def get_ideas_by_category(category: str, limit: int = 5, exclude_ids: list[int] | None = None) -> list[dict]:
    """Return up to limit ideas from the category (for browse)."""
    ideas = _load_ideas()
    filtered = [i for i in ideas if (i.get("category") or "").lower() == category.lower()]
    if exclude_ids:
        excl = set(exclude_ids)
        filtered = [i for i in filtered if i.get("id") not in excl]
    random.shuffle(filtered)
    return [i.copy() for i in filtered[:limit]]


def get_ideas_by_tag(tag: str, limit: int = 5) -> list[dict]:
    """Return ideas that have tag in their tags list (case-insensitive)."""
    if not tag or not tag.strip():
        return []
    ideas = _load_ideas()
    t = tag.strip().lower()
    matched = [i.copy() for i in ideas if t in [x.lower() for x in (i.get("tags") or [])]]
    return matched[:limit]


def get_idea_by_category(category: str, exclude_ids: list[int] | None = None) -> dict | None:
    """Return one random idea from the given category, or None if no match. Optionally exclude ids."""
    ideas = _load_ideas()
    filtered = [i for i in ideas if i.get("category", "").lower() == category.lower()]
    if exclude_ids:
        excl = set(exclude_ids)
        filtered = [i for i in filtered if i.get("id") not in excl]
    return random.choice(filtered).copy() if filtered else None


def get_idea_by_difficulty(difficulty: str, exclude_ids: list[int] | None = None) -> dict | None:
    """Return one random idea for the given difficulty, or None if no match. Optionally exclude ids."""
    ideas = _load_ideas()
    filtered = [i for i in ideas if i.get("difficulty", "").lower() == difficulty.lower()]
    if exclude_ids:
        excl = set(exclude_ids)
        filtered = [i for i in filtered if i.get("id") not in excl]
    return random.choice(filtered).copy() if filtered else None


def get_idea_by_difficulty_and_category(
    difficulty: str,
    category: str,
    exclude_ids: list[int] | None = None,
) -> dict | None:
    """Return one random idea matching both difficulty and category, or None."""
    ideas = _load_ideas()
    filtered = [
        i for i in ideas
        if (i.get("difficulty") or "").lower() == difficulty.lower()
        and (i.get("category") or "").lower() == category.lower()
    ]
    if exclude_ids:
        excl = set(exclude_ids)
        filtered = [i for i in filtered if i.get("id") not in excl]
    return random.choice(filtered).copy() if filtered else None


def get_all_ideas() -> list[dict]:
    """Return all ideas (with id). For export."""
    return [i.copy() for i in _load_ideas()]


def get_stats() -> dict:
    """Return counts: total, by difficulty, by category."""
    ideas = _load_ideas()
    by_difficulty: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for i in ideas:
        d = (i.get("difficulty") or "").strip().lower()
        c = (i.get("category") or "").strip().lower()
        if d:
            by_difficulty[d] = by_difficulty.get(d, 0) + 1
        if c:
            by_category[c] = by_category.get(c, 0) + 1
    return {"total": len(ideas), "by_difficulty": by_difficulty, "by_category": by_category}


def get_idea_of_the_day() -> dict:
    """Return one idea deterministically chosen by today's date (UTC)."""
    import hashlib
    from datetime import datetime, timezone
    ideas = _load_ideas()
    if not ideas:
        raise ValueError("No ideas in database")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    index = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(ideas)
    return ideas[index].copy()


def find_similar_title(title: str) -> dict | None:
    """Return an existing idea whose title is very similar (equal ignore case), or None."""
    if not title or not title.strip():
        return None
    ideas = _load_ideas()
    t = title.strip().lower()
    for i in ideas:
        if (i.get("title") or "").strip().lower() == t:
            return i.copy()
    return None


def delete_idea(idea_id: int) -> bool:
    """Remove idea at id and renumber remaining. Returns True if removed. Invalidates cache."""
    raw = []
    if _IDEAS_PATH.exists():
        with open(_IDEAS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    if idea_id < 0 or idea_id >= len(raw):
        return False
    raw.pop(idea_id)
    with open(_IDEAS_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    _invalidate_cache()
    return True


def search_ideas(query: str, limit: int = 5, search_tags: bool = True) -> list[dict]:
    """Return ideas whose title or description contains the query (case-insensitive), up to limit. If search_tags, also match tags."""
    if not query or not query.strip():
        return []
    ideas = _load_ideas()
    q = query.strip().lower()
    matched = []
    for i in ideas:
        if q in (i.get("title") or "").lower() or q in (i.get("description") or "").lower():
            matched.append(i.copy())
        elif search_tags and (i.get("tags")):
            if any(q in (t or "").lower() for t in i["tags"]):
                matched.append(i.copy())
    return matched[:limit]


def add_idea(
    title: str,
    description: str,
    difficulty: str | None = None,
    category: str | None = None,
) -> dict:
    """Append a new idea to ideas.json and invalidate cache. Returns the new idea (with id from next load)."""
    raw = []
    if _IDEAS_PATH.exists():
        with open(_IDEAS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    new_idea = {"title": title.strip(), "description": description.strip()}
    if difficulty and difficulty.strip():
        new_idea["difficulty"] = difficulty.strip().lower()
    if category and category.strip():
        new_idea["category"] = category.strip().lower()
    raw.append(new_idea)
    with open(_IDEAS_PATH, "w", encoding="utf-8") as f:
        json.dump(raw, f, indent=2, ensure_ascii=False)
    _invalidate_cache()
    return new_idea
