import logging
from io import BytesIO
from uuid import uuid4
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, InlineQueryHandler, MessageHandler, filters

import activity as activity_module
import config
import done as done_module
import feedback as feedback_module
import favorites
import idea_reminders as idea_reminders_module
import reminders
import seen
import suggestions as suggestions_module
import users as users_module
from ideas import (
    add_idea as ideas_add_idea,
    delete_idea as ideas_delete_idea,
    find_similar_title,
    get_all_ideas,
    get_idea_by_category,
    get_idea_by_difficulty,
    get_idea_by_difficulty_and_category,
    get_idea_by_id,
    get_ideas_by_category,
    get_ideas_by_tag,
    get_idea_of_the_day,
    get_random_idea_unseen,
    get_stats,
    search_ideas,
)

# Admin: user IDs waiting to send idea content (after /add_idea)
_add_idea_waiting: set[int] = set()
# User IDs waiting to send suggestion (after /suggest)
_suggest_waiting: set[int] = set()

DIFFICULTIES = ("beginner", "intermediate", "advanced")
CATEGORIES = ("ui", "game", "dashboard", "productivity")


def _is_admin(user_id: int) -> bool:
    return user_id in getattr(config, "ADMIN_USER_IDS", [])

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def format_idea(idea: dict) -> str:
    lines = [f"**{idea['title']}**", "", idea["description"]]
    if idea.get("difficulty"):
        lines.append(f"\n_Difficulty: {idea['difficulty']}_")
    if idea.get("category"):
        lines.append(f"_Category: {idea['category']}_")
    return "\n".join(lines)


def _onboarding_keyboard() -> InlineKeyboardMarkup:
    """Keyboard shown after /start for quick first idea."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Random", callback_data="another_idea")],
        [
            InlineKeyboardButton("Beginner", callback_data="idea_beginner"),
            InlineKeyboardButton("Game", callback_data="cat_game"),
            InlineKeyboardButton("Dashboard", callback_data="cat_dashboard"),
        ],
        [
            InlineKeyboardButton("UI", callback_data="cat_ui"),
            InlineKeyboardButton("Productivity", callback_data="cat_productivity"),
        ],
    ])


def _filter_keyboard(
    idea: dict,
    user_id: int | None = None,
    bot_username: str | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("Another idea", callback_data="another_idea")],
        [
            InlineKeyboardButton("Beginner", callback_data="idea_beginner"),
            InlineKeyboardButton("Intermediate", callback_data="idea_intermediate"),
            InlineKeyboardButton("Advanced", callback_data="idea_advanced"),
        ],
        [
            InlineKeyboardButton("UI", callback_data="cat_ui"),
            InlineKeyboardButton("Game", callback_data="cat_game"),
            InlineKeyboardButton("Dashboard", callback_data="cat_dashboard"),
            InlineKeyboardButton("Productivity", callback_data="cat_productivity"),
        ],
    ]
    cat = (idea or {}).get("category")
    if idea is not None and "id" in idea:
        if cat:
            rows.append([InlineKeyboardButton("More like this", callback_data=f"morelike_{idea['id']}")])
    if idea is not None and "id" in idea and user_id is not None:
        saved = favorites.get_favorites(user_id)
        done_ids = done_module.get(user_id)
        idea_id = idea["id"]
        action_buttons = []
        if idea_id in saved:
            action_buttons.append(InlineKeyboardButton("Unsave", callback_data=f"unsave_{idea_id}"))
        else:
            action_buttons.append(InlineKeyboardButton("Save", callback_data=f"save_{idea_id}"))
        action_buttons.append(InlineKeyboardButton("Share", callback_data=f"share_{idea_id}"))
        if idea_id in done_ids:
            action_buttons.append(InlineKeyboardButton("Undo done", callback_data=f"undone_{idea_id}"))
        else:
            action_buttons.append(InlineKeyboardButton("I've done this", callback_data=f"done_{idea_id}"))
        if action_buttons:
            rows.append(action_buttons)
        rows.append([
            InlineKeyboardButton("👍 Helpful", callback_data=f"fb_{idea_id}_1"),
            InlineKeyboardButton("👎 Not helpful", callback_data=f"fb_{idea_id}_0"),
        ])
        rows.append([
            InlineKeyboardButton("Remind in 1 day", callback_data=f"remind_1_{idea_id}"),
            InlineKeyboardButton("Remind in 3 days", callback_data=f"remind_3_{idea_id}"),
            InlineKeyboardButton("Remind in 7 days", callback_data=f"remind_7_{idea_id}"),
        ])
    return InlineKeyboardMarkup(rows)


def _record_user(update: Update) -> None:
    uid = update.effective_user.id if update.effective_user else None
    cid = update.effective_chat.id if update.effective_chat else None
    if uid is not None and cid is not None:
        users_module.record(uid, cid)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    # Deep link: t.me/Bot?start=idea_42 -> show that idea
    if context.args and len(context.args) == 1 and context.args[0].startswith("idea_"):
        try:
            idea_id = int(context.args[0].replace("idea_", "", 1))
        except ValueError:
            pass
        else:
            idea = get_idea_by_id(idea_id)
            if idea:
                user_id = update.effective_user.id if update.effective_user else None
                if user_id is not None:
                    seen.add_seen(user_id, idea["id"])
                bot_username = context.bot.username if context.bot else None
                await update.message.reply_text(
                    format_idea(idea),
                    reply_markup=_filter_keyboard(idea, user_id, bot_username),
                    parse_mode="Markdown",
                )
                return
    await update.message.reply_text(
        "Hi! I suggest front-end pet project ideas.\n\n"
        "Use /idea for a random idea.\n"
        "Filter by difficulty: /idea beginner, /idea intermediate, /idea advanced.\n"
        "Filter by category: /idea ui, /idea game, /idea dashboard, /idea productivity.\n"
        "Combine: /idea <difficulty> <category> (e.g. /idea intermediate game).\n"
        "Search: /search <keyword> · Save with Save button · /saved to list.\n"
        "Idea of the day: /today · All commands: /help"
    )
    await update.message.reply_text(
        "Tap below to get your first idea:",
        reply_markup=_onboarding_keyboard(),
    )


def _get_filter_from_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[str | None, str | tuple]:
    """Return (filter_type, value): ('difficulty', 'beginner'), ('category', 'ui'), ('both', (diff, cat)), ('morelike', idea_id), or (None, None)."""
    if update.callback_query:
        data = update.callback_query.data or ""
        if data == "another_idea":
            return None, None
        if data.startswith("morelike_"):
            try:
                return "morelike", int(data.replace("morelike_", "", 1))
            except ValueError:
                return None, None
        if data.startswith("idea_") and data.replace("idea_", "", 1) in DIFFICULTIES:
            return "difficulty", data.replace("idea_", "", 1)
        if data.startswith("cat_") and data.replace("cat_", "", 1) in CATEGORIES:
            return "category", data.replace("cat_", "", 1)
        return None, None
    if context.args:
        args = [a.lower() for a in context.args]
        if len(args) >= 2 and args[0] == "tag":
            return "tag", args[1]
        if len(args) >= 2 and args[0] in DIFFICULTIES and args[1] in CATEGORIES:
            return "both", (args[0], args[1])
        if len(args) >= 1:
            if args[0] in DIFFICULTIES:
                return "difficulty", args[0]
            if args[0] in CATEGORIES:
                return "category", args[0]
    return None, None


async def send_idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        _record_user(update)
    filter_type, filter_value = _get_filter_from_update(update, context)
    user_id = update.effective_user.id if update.effective_user else None
    seen_ids = seen.get_seen(user_id) if user_id is not None else []
    idea = None
    no_ideas_msg = None
    if filter_type == "difficulty":
        idea = get_idea_by_difficulty(filter_value, exclude_ids=seen_ids)
        if not idea:
            idea = get_idea_by_difficulty(filter_value)
        if not idea:
            no_ideas_msg = f"No ideas found for difficulty \"{filter_value}\". Try /idea for a random idea."
    elif filter_type == "category":
        idea = get_idea_by_category(filter_value, exclude_ids=seen_ids)
        if not idea:
            idea = get_idea_by_category(filter_value)
        if not idea:
            no_ideas_msg = f"No ideas found for category \"{filter_value}\". Try /idea for a random idea."
    elif filter_type == "both":
        diff, cat = filter_value
        idea = get_idea_by_difficulty_and_category(diff, cat, exclude_ids=seen_ids)
        if not idea:
            idea = get_idea_by_difficulty_and_category(diff, cat)
        if not idea:
            no_ideas_msg = f"No ideas found for {diff} + {cat}. Try /idea for a random idea."
    elif filter_type == "morelike":
        current = get_idea_by_id(filter_value)
        if not current or not current.get("category"):
            no_ideas_msg = "No similar ideas (category missing). Try /idea for a random idea."
        else:
            cat = current["category"].lower()
            exclude = list(seen_ids) + [filter_value]
            idea = get_idea_by_category(cat, exclude_ids=exclude)
            if not idea:
                idea = get_idea_by_category(cat, exclude_ids=[filter_value])
            if not idea:
                no_ideas_msg = f"No other ideas in {cat}. Try /idea for a random idea."
    elif filter_type == "tag":
        tagged = get_ideas_by_tag(filter_value, limit=20)
        if tagged:
            import random as _r
            idea = _r.choice(tagged).copy()
        else:
            no_ideas_msg = f"No ideas with tag \"{filter_value}\". Try /idea or /search."
    else:
        done_ids = done_module.get(user_id) if user_id is not None else []
        idea, had_unseen = get_random_idea_unseen(seen_ids, done_ids=done_ids)
        if not had_unseen and user_id is not None:
            seen.clear_seen(user_id)
    if idea and user_id is not None:
        seen.add_seen(user_id, idea["id"])
        activity_module.record_request(user_id)
    if no_ideas_msg:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(no_ideas_msg)
        else:
            await update.message.reply_text(no_ideas_msg)
        return
    text = format_idea(idea)
    user_id = update.effective_user.id if update.effective_user else None
    bot_username = context.bot.username if context.bot else None
    keyboard = _filter_keyboard(idea, user_id, bot_username)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            text,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )


HELP_TEXT = """Commands:
/start — Welcome and link to open a shared idea
/idea — Random idea (or /idea beginner, /idea game, /idea tag react)
/search <keyword> — Search ideas (and tags)
/saved — Your saved ideas (with Remove buttons)
/today — Idea of the day
/top — Top ideas by helpful votes (👍/👎)
/mystats — Your seen, saved, done counts and streak
/privacy — What data we store
/delete_my_data — Delete all your data (with confirmation)
/export — Download all ideas; /export saved; add 'json' for JSON
/suggest — Submit a new idea for review
/remind on | off | time 10:00 — Daily idea (UTC)
/browse <category> — List 5 ideas from category (ui, game, dashboard, productivity)
/help — This message
/stats — Total ideas and counts
Admin: /add_idea, /suggestions, /approve <id>, /reject <id> [reason], /backup, /broadcast <text>, /delete_idea <id>, /cancel"""


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    await update.message.reply_text(HELP_TEXT)


async def mystats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        await update.message.reply_text("Could not identify user.")
        return
    seen_count = len(seen.get_seen(user_id))
    saved_count = len(favorites.get_favorites(user_id))
    done_count = len(done_module.get(user_id))
    streak = activity_module.get_streak(user_id)
    streak_line = f" You're on a **{streak}** day streak!" if streak else ""
    await update.message.reply_text(
        f"You've seen **{seen_count}** ideas, saved **{saved_count}**, marked **{done_count}** as done.{streak_line}\n\n"
        "Use /idea for more, /saved to list saved.",
        parse_mode="Markdown",
    )


async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    if not update.effective_user or not _is_admin(update.effective_user.id):
        await update.message.reply_text("You are not allowed to use this command.")
        return
    chat_id = update.effective_chat.id
    ideas = get_all_ideas()
    import json as _json
    raw = [{"title": i.get("title"), "description": i.get("description"), "difficulty": i.get("difficulty"), "category": i.get("category"), "tags": i.get("tags")} for i in ideas]
    bio = BytesIO(_json.dumps(raw, indent=2, ensure_ascii=False).encode("utf-8"))
    bio.name = "ideas_backup.json"
    await context.bot.send_document(chat_id=chat_id, document=bio, filename=bio.name)
    pending = suggestions_module.get_all()
    bio2 = BytesIO(_json.dumps(pending, indent=2, ensure_ascii=False).encode("utf-8"))
    bio2.name = "suggestions_backup.json"
    await context.bot.send_document(chat_id=chat_id, document=bio2, filename=bio2.name)
    await update.message.reply_text("Backup sent (ideas + suggestions).")


async def browse_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    if not context.args:
        await update.message.reply_text("Usage: /browse <category>\nCategories: ui, game, dashboard, productivity")
        return
    cat = context.args[0].lower()
    if cat not in CATEGORIES:
        await update.message.reply_text(f"Unknown category. Use one of: {', '.join(CATEGORIES)}")
        return
    ideas = get_ideas_by_category(cat, limit=5)
    if not ideas:
        await update.message.reply_text(f"No ideas in category \"{cat}\".")
        return
    lines = [f"**Browse: {cat}** (5 ideas)", ""]
    for i, idea in enumerate(ideas, 1):
        lines.append(f"{i}. **{idea['title']}**")
        lines.append((idea.get("description") or "")[:120] + ("..." if len(idea.get("description") or "") > 120 else ""))
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def delete_idea_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    if not update.effective_user or not _is_admin(update.effective_user.id):
        await update.message.reply_text("You are not allowed to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /delete_idea <id>")
        return
    try:
        idea_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /delete_idea <id> (numeric)")
        return
    if ideas_delete_idea(idea_id):
        await update.message.reply_text(f"Deleted idea id {idea_id}. IDs have been renumbered.")
    else:
        await update.message.reply_text(f"No idea with id {idea_id}.")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    if not update.effective_user or not _is_admin(update.effective_user.id):
        await update.message.reply_text("You are not allowed to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message text>")
        return
    text = " ".join(context.args)
    chat_ids = users_module.get_all_chat_ids()
    sent, failed = 0, 0
    for cid in chat_ids:
        try:
            await context.bot.send_message(chat_id=cid, text=text)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"Broadcast sent to {sent} users. Failed: {failed}.")


async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    top_ids = feedback_module.get_top_idea_ids(limit=5)
    if not top_ids:
        await update.message.reply_text("No feedback yet. Use 👍 / 👎 on ideas to see top ideas here.")
        return
    lines = ["**Top ideas** (by helpful votes):", ""]
    for i, idea_id in enumerate(top_ids, 1):
        idea = get_idea_by_id(idea_id)
        if idea:
            up, down = feedback_module.get(idea_id)
            lines.append(f"{i}. **{idea['title']}** (👍 {up} / 👎 {down})")
            lines.append((idea.get("description") or "")[:100] + ("..." if len(idea.get("description") or "") > 100 else ""))
            lines.append("")
    await update.message.reply_text("\n".join(lines).strip() or "No data.", parse_mode="Markdown")


PRIVACY_TEXT = """**Privacy**

This bot stores the following for your account:
• **Seen** — IDs of ideas you were shown (to reduce repeats)
• **Saved** — IDs of ideas you saved
• **Done** — IDs of ideas you marked as "I've done this"
• **Activity** — Last date you requested an idea and streak count
• **Reminders** — If you use /remind on: your chat ID and reminder time
• **Broadcast list** — Your chat ID (so we can send you the daily idea or broadcasts)

We do not sell or share your data. Feedback (👍/👎) is stored per idea, not per user.

To delete all your data: /delete_my_data"""


async def privacy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    await update.message.reply_text(PRIVACY_TEXT, parse_mode="Markdown")


async def delete_my_data_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        await update.message.reply_text("Could not identify user.")
        return
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Yes, delete my data", callback_data="confirm_delete_my_data"),
            InlineKeyboardButton("Cancel", callback_data="cancel_delete_my_data"),
        ],
    ])
    await update.message.reply_text(
        "This will remove your saved ideas, seen list, done list, activity, reminders, and you from the broadcast list. "
        "You can keep using the bot afterward. Confirm:",
        reply_markup=keyboard,
    )


async def delete_my_data_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    if query.data == "confirm_delete_my_data":
        seen.delete_user(user_id)
        favorites.delete_user(user_id)
        done_module.delete_user(user_id)
        activity_module.delete_user(user_id)
        reminders.delete_user(user_id)
        idea_reminders_module.remove_by_user(user_id)
        users_module.delete_user(user_id)
        await query.edit_message_text("Your data has been deleted. You can continue using the bot.")
    else:
        await query.edit_message_text("Cancelled. Your data was not deleted.")


async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    if not update.effective_user or not _is_admin(update.effective_user.id):
        await update.message.reply_text("You are not allowed to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /reject <id> [reason]")
        return
    try:
        sid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /reject <id> (numeric)")
        return
    s = suggestions_module.get_by_id(sid)
    if not s:
        await update.message.reply_text(f"No suggestion with id {sid}.")
        return
    reason = " ".join(context.args[1:]).strip() if len(context.args) > 1 else None
    from_user_id = s.get("from_user_id")
    from_username = s.get("from_username") or "User"
    suggestions_module.remove(sid)
    if from_user_id:
        try:
            msg = f"Your suggestion \"{s['title']}\" was not added to the bot."
            if reason:
                msg += f" Reason: {reason}"
            msg += " You can submit another with /suggest."
            await context.bot.send_message(chat_id=from_user_id, text=msg)
        except Exception:
            pass
    await update.message.reply_text(f"Rejected suggestion #{sid}. Submitter notified.")


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    st = get_stats()
    lines = [f"Total ideas: {st['total']}", ""]
    if st["by_difficulty"]:
        lines.append("By difficulty:")
        for d in ("beginner", "intermediate", "advanced"):
            if d in st["by_difficulty"]:
                lines.append(f"  {d}: {st['by_difficulty'][d]}")
        lines.append("")
    if st["by_category"]:
        lines.append("By category:")
        for c in ("ui", "game", "dashboard", "productivity"):
            if c in st["by_category"]:
                lines.append(f"  {c}: {st['by_category'][c]}")
    await update.message.reply_text("\n".join(lines))


def _export_content(ideas: list[dict]) -> str:
    lines = []
    for i, idea in enumerate(ideas, 1):
        lines.append(f"{i}. {idea.get('title', '')}")
        lines.append(idea.get("description", ""))
        if idea.get("difficulty") or idea.get("category"):
            lines.append(f"   Difficulty: {idea.get('difficulty', '—')} | Category: {idea.get('category', '—')}")
        lines.append("")
    return "\n".join(lines).strip() or "No ideas."


async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    if not chat_id:
        return
    args = [a.lower() for a in (context.args or [])]
    use_saved = "saved" in args
    use_json = "json" in args
    if use_saved and user_id is not None:
        ids_list = favorites.get_favorites(user_id)
        ideas = []
        for iid in ids_list:
            idea = get_idea_by_id(iid)
            if idea:
                ideas.append(idea)
        filename = "my_saved_ideas.json" if use_json else "my_saved_ideas.txt"
    else:
        ideas = get_all_ideas()
        filename = "all_ideas.json" if use_json else "all_ideas.txt"
    if use_json:
        import json as _json
        content = _json.dumps(ideas, indent=2, ensure_ascii=False).encode("utf-8")
    else:
        content = _export_content(ideas).encode("utf-8")
    bio = BytesIO(content)
    bio.name = filename
    await update.message.reply_document(document=bio, filename=filename)


SUGGEST_FORMAT = (
    "Send your idea in this format (use double newline to separate):\n\n"
    "Title\n\n"
    "Description (one or more lines)\n\n"
    "difficulty, category\n\n"
    "Last line optional. Difficulty: beginner, intermediate, advanced. "
    "Category: ui, game, dashboard, productivity.\n\n"
    "Send /cancel to abort."
)


async def suggest_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        await update.message.reply_text("Could not identify user.")
        return
    _suggest_waiting.add(user_id)
    await update.message.reply_text("Submit an idea for the bot. Admins can approve it to add to the list.\n\n" + SUGGEST_FORMAT)


async def suggestions_list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None or not _is_admin(user_id):
        await update.message.reply_text("You are not allowed to use this command.")
        return
    pending = suggestions_module.get_all()
    if not pending:
        await update.message.reply_text("No pending suggestions. Use /approve <id> to approve one.")
        return
    lines = ["Pending suggestions (use /approve <id> to add to the bot):", ""]
    for s in pending:
        lines.append(f"ID {s['id']}: **{s.get('title', '')}** (from @{s.get('from_username', '')})")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None or not _is_admin(user_id):
        await update.message.reply_text("You are not allowed to use this command.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve <id>")
        return
    try:
        sid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Usage: /approve <id> (numeric id)")
        return
    s = suggestions_module.get_by_id(sid)
    if not s:
        await update.message.reply_text(f"No suggestion with id {sid}.")
        return
    ideas_add_idea(
        s["title"],
        s["description"],
        difficulty=s.get("difficulty"),
        category=s.get("category"),
    )
    suggestions_module.remove(sid)
    from_user_id = s.get("from_user_id")
    from_username = s.get("from_username") or "User"
    try:
        await context.bot.send_message(
            chat_id=from_user_id,
            text=f"Your suggestion \"{s['title']}\" was approved and added to the bot. Thanks!",
        )
    except Exception:
        pass
    await update.message.reply_text(f"Approved suggestion #{sid} and notified @{from_username}.")


async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _record_user(update)
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    if user_id is None or chat_id is None:
        await update.message.reply_text("Could not identify user or chat.")
        return
    if not context.args:
        if reminders.is_on(user_id):
            t = reminders.get_time(user_id)
            await update.message.reply_text(f"Daily reminder is ON at {t} UTC. Use /remind off to stop or /remind time HH:MM to change.")
        else:
            await update.message.reply_text("Daily reminder is OFF. Use /remind on to get one idea at 09:00 UTC.")
        return
    arg = context.args[0].lower()
    if arg == "on":
        time_str = context.args[1] if len(context.args) > 1 else "09:00"
        reminders.add(user_id, chat_id, time_str=time_str)
        await update.message.reply_text(f"Daily reminder is ON at {reminders.get_time(user_id)} UTC. Use /remind off to stop.")
    elif arg == "off":
        reminders.remove(user_id)
        await update.message.reply_text("Daily reminder is OFF.")
    elif arg == "time" and len(context.args) >= 2:
        time_str = context.args[1]
        if reminders.is_on(user_id):
            reminders.set_time(user_id, time_str)
            await update.message.reply_text(f"Reminder time set to {reminders.get_time(user_id)} UTC.")
        else:
            await update.message.reply_text("Turn on reminders first: /remind on")
    else:
        await update.message.reply_text("Use /remind on, /remind off, or /remind time HH:MM")


async def remind_idea_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Remind in 1/3/7 days' button: schedule reminder and confirm."""
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith("remind_") or "_" not in data:
        return
    parts = data.split("_")
    if len(parts) != 3 or parts[1] not in ("1", "3", "7"):
        return
    try:
        days = int(parts[1])
        idea_id = int(parts[2])
    except ValueError:
        return
    user_id = update.effective_user.id if update.effective_user else None
    chat_id = update.effective_chat.id if update.effective_chat else None
    if user_id is None or chat_id is None:
        return
    idea_reminders_module.add(user_id, chat_id, idea_id, days)
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"I'll remind you about this idea in {days} day(s).")


async def send_daily_ideas_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job: run every hour; send idea of the day; send due idea reminders."""
    from datetime import datetime, timezone
    try:
        idea = get_idea_of_the_day()
    except ValueError:
        idea = None
    now = datetime.now(timezone.utc)
    utc_hour = now.hour
    today_iso = now.strftime("%Y-%m-%d")
    if idea:
        text = "Idea of the day:\n\n" + format_idea(idea)
        for user_id, chat_id in reminders.get_chat_ids_for_hour(utc_hour, today_iso):
            try:
                await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
                reminders.mark_sent(user_id, today_iso)
            except Exception as e:
                logger.warning("Daily reminder failed for chat %s: %s", chat_id, e)
    for chat_id, idea_id, _user_id in idea_reminders_module.get_due():
        try:
            reminder_idea = get_idea_by_id(idea_id)
            if reminder_idea:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="Reminder: you asked to be reminded about this idea.\n\n" + format_idea(reminder_idea),
                    parse_mode="Markdown",
                )
        except Exception as e:
            logger.warning("Idea reminder failed for chat %s: %s", chat_id, e)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /search <keyword>\nExample: /search timer")
        return
    query = " ".join(context.args)
    results = search_ideas(query, limit=3)
    if not results:
        await update.message.reply_text(f'No ideas found for "{query}".')
        return
    lines = [f'Search results for "{query}":', ""]
    for i, idea in enumerate(results, 1):
        lines.append(f"{i}. **{idea['title']}**")
        lines.append(idea["description"])
        if idea.get("difficulty") or idea.get("category"):
            lines.append(f"   _Difficulty: {idea.get('difficulty', '—')} | Category: {idea.get('category', '—')}_")
        lines.append("")
    text = "\n".join(lines).strip()
    await update.message.reply_text(text, parse_mode="Markdown")


def _saved_list_keyboard(idea_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(f"Remove #{idea_id}", callback_data=f"saved_remove_{idea_id}")] for idea_id in idea_ids]
    return InlineKeyboardMarkup(rows)


async def saved_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        await update.message.reply_text("Could not identify user.")
        return
    ids_list = favorites.get_favorites(user_id)
    if not ids_list:
        await update.message.reply_text("You have no saved ideas. Use /idea and tap Save on ideas you like.")
        return
    lines = ["Your saved ideas (tap Remove to unsave):", ""]
    for i, idea_id in enumerate(ids_list, 1):
        idea = get_idea_by_id(idea_id)
        if idea:
            lines.append(f"{i}. **{idea['title']}**")
        else:
            lines.append(f"{i}. (idea not found)")
    keyboard = _saved_list_keyboard(ids_list)
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=keyboard)


async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("fb_") or "_" not in data:
        return
    parts = data.split("_")
    if len(parts) != 3:
        return
    try:
        idea_id = int(parts[1])
        helpful = parts[2] == "1"
    except (ValueError, IndexError):
        return
    feedback_module.add(idea_id, helpful)
    await query.answer("Thanks for your feedback!", show_alert=False)


async def done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    if data.startswith("done_"):
        try:
            idea_id = int(data.replace("done_", "", 1))
        except ValueError:
            return
        done_module.add(user_id, idea_id)
        await query.answer("Marked as done!", show_alert=False)
    elif data.startswith("undone_"):
        try:
            idea_id = int(data.replace("undone_", "", 1))
        except ValueError:
            return
        done_module.remove(user_id, idea_id)
        await query.answer("Undone.", show_alert=False)
    else:
        return
    idea = get_idea_by_id(idea_id)
    if idea:
        bot_username = context.bot.username if context.bot else None
        keyboard = _filter_keyboard(idea, user_id, bot_username)
        await query.edit_message_reply_markup(reply_markup=keyboard)


async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = (update.inline_query.query or "").strip()
    if q:
        ideas = search_ideas(q, limit=10)
    else:
        ideas = get_all_ideas()[:10]
    results = []
    for idea in ideas:
        title = idea.get("title", "Idea")[:64]
        desc = (idea.get("description") or "")[:200]
        if len(idea.get("description") or "") > 200:
            desc += "..."
        text = format_idea(idea)
        results.append(
            InlineQueryResultArticle(
                id=str(uuid4()),
                title=title,
                description=desc,
                input_message_content=InputTextMessageContent(text, parse_mode="Markdown"),
            )
        )
    await update.inline_query.answer(results, cache_time=60)


async def share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    if not data.startswith("share_"):
        return
    try:
        idea_id = int(data.replace("share_", "", 1))
    except ValueError:
        return
    await query.answer("Link sent below.", show_alert=False)
    bot_username = context.bot.username if context.bot else None
    if not bot_username:
        await query.message.reply_text("Share link is not available (bot username missing).")
        return
    link = f"https://t.me/{bot_username}?start=idea_{idea_id}"
    await query.message.reply_text(
        f"Share this idea — anyone opening the link will see it:\n\n{link}\n\nCopy or forward this message to share."
    )


async def saved_remove_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None or not data.startswith("saved_remove_"):
        return
    try:
        idea_id = int(data.replace("saved_remove_", "", 1))
    except ValueError:
        return
    favorites.remove_favorite(user_id, idea_id)
    await query.answer("Removed from saved.", show_alert=False)
    ids_list = favorites.get_favorites(user_id)
    if not ids_list:
        await query.edit_message_text("Your saved ideas (tap Remove to unsave):\n\nNo saved ideas.")
        return
    lines = ["Your saved ideas (tap Remove to unsave):", ""]
    for i, iid in enumerate(ids_list, 1):
        idea = get_idea_by_id(iid)
        if idea:
            lines.append(f"{i}. **{idea['title']}**")
        else:
            lines.append(f"{i}. (idea not found)")
    keyboard = _saved_list_keyboard(ids_list)
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=keyboard)


async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        idea = get_idea_of_the_day()
    except ValueError:
        await update.message.reply_text("No ideas in the database yet.")
        return
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is not None:
        seen.add_seen(user_id, idea["id"])
        activity_module.record_request(user_id)
    bot_username = context.bot.username if context.bot else None
    await update.message.reply_text(
        "Idea of the day:\n\n" + format_idea(idea),
        reply_markup=_filter_keyboard(idea, user_id, bot_username),
        parse_mode="Markdown",
    )


async def save_unsave_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        return
    if data.startswith("save_"):
        try:
            idea_id = int(data.replace("save_", "", 1))
        except ValueError:
            return
        added = favorites.add_favorite(user_id, idea_id)
        if added:
            await query.answer("Saved!", show_alert=False)
        else:
            await query.answer("Already in favorites.", show_alert=False)
    elif data.startswith("unsave_"):
        try:
            idea_id = int(data.replace("unsave_", "", 1))
        except ValueError:
            return
        favorites.remove_favorite(user_id, idea_id)
        await query.answer("Removed from favorites.", show_alert=False)
    else:
        return
    idea = get_idea_by_id(idea_id)
    if idea:
        bot_username = context.bot.username if context.bot else None
        text = format_idea(idea)
        keyboard = _filter_keyboard(idea, user_id, bot_username)
        await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode="Markdown")


ADD_IDEA_FORMAT = (
    "Send your idea in this format (use double newline to separate):\n\n"
    "Title\n\n"
    "Description (one or more lines)\n\n"
    "difficulty, category\n\n"
    "The last line is optional. Difficulty: beginner, intermediate, or advanced. "
    "Category: ui, game, dashboard, or productivity.\n\n"
    "Example:\n\n"
    "My Cool App\n\n"
    "Build a todo app with drag and drop.\n\n"
    "intermediate, productivity\n\n"
    "Send /cancel to abort."
)


async def add_idea_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id is None:
        await update.message.reply_text("Could not identify user.")
        return
    if not _is_admin(user_id):
        await update.message.reply_text("You are not allowed to use this command.")
        return
    _add_idea_waiting.add(user_id)
    await update.message.reply_text(ADD_IDEA_FORMAT)


async def cancel_add_idea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id if update.effective_user else None
    if user_id in _add_idea_waiting:
        _add_idea_waiting.discard(user_id)
        await update.message.reply_text("Cancelled.")
    elif user_id in _suggest_waiting:
        _suggest_waiting.discard(user_id)
        await update.message.reply_text("Cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")


def _parse_idea_message(text: str) -> tuple[str, str, str | None, str | None] | None:
    """Parse message into (title, description, difficulty, category) or None if invalid."""
    parts = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(parts) < 2:
        return None
    title = parts[0]
    description = parts[1]
    if not title or not description:
        return None
    difficulty, category = None, None
    if len(parts) >= 3:
        opt = parts[2].lower().strip()
        bits = [b.strip() for b in opt.split(",")]
        if len(bits) >= 1 and bits[0] in DIFFICULTIES:
            difficulty = bits[0]
        if len(bits) >= 2 and bits[1] in CATEGORIES:
            category = bits[1]
    return title, description, difficulty, category


async def receive_idea_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user_id = update.effective_user.id
    text = update.message.text or ""
    parsed = _parse_idea_message(text)

    if user_id in _suggest_waiting:
        _suggest_waiting.discard(user_id)
        if parsed is None:
            await update.message.reply_text("Invalid format. Need at least: Title and Description.\n\n" + SUGGEST_FORMAT)
            return
        title, description, difficulty, category = parsed
        similar = find_similar_title(title)
        if similar:
            await update.message.reply_text(f"A similar title already exists: «{similar.get('title', '')}». Submitting anyway for review.")
        username = (update.effective_user.username or "").strip()
        try:
            s = suggestions_module.add(title, description, user_id, username or None, difficulty, category)
            await update.message.reply_text(f"Thanks! Your suggestion \"{title}\" was submitted. Admins will review it.")
            for admin_id in getattr(config, "ADMIN_USER_IDS", []):
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"New suggestion #{s['id']} from @{username or 'user'}: **{title}**",
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.exception("Failed to add suggestion")
            await update.message.reply_text(f"Failed to save suggestion: {e}")
        return

    if user_id not in _add_idea_waiting:
        return
    if parsed is None:
        await update.message.reply_text(
            "Invalid format. Need at least: Title and Description (separated by a blank line).\n\n" + ADD_IDEA_FORMAT
        )
        return
    title, description, difficulty, category = parsed
    _add_idea_waiting.discard(user_id)
    similar = find_similar_title(title)
    if similar:
        await update.message.reply_text(f"Warning: A similar title already exists: «{similar.get('title', '')}». Added anyway.")
    try:
        ideas_add_idea(title, description, difficulty=difficulty, category=category)
    except Exception as e:
        logger.exception("Failed to add idea")
        await update.message.reply_text(f"Failed to save idea: {e}")
        return
    msg = f"Added idea: **{title}**"
    if difficulty:
        msg += f" ({difficulty}"
        if category:
            msg += f", {category})"
        else:
            msg += ")"
    elif category:
        msg += f" ({category})"
    msg += "."
    await update.message.reply_text(msg, parse_mode="Markdown")


async def _set_bot_commands(application: Application) -> None:
    """Register command list so they appear in the Telegram menu when user taps /."""
    await application.bot.set_my_commands([
        BotCommand("start", "Welcome and get first idea"),
        BotCommand("idea", "Random idea (or: beginner, game, tag react)"),
        BotCommand("search", "Search ideas by keyword or tag"),
        BotCommand("saved", "Your saved ideas"),
        BotCommand("today", "Idea of the day"),
        BotCommand("top", "Top ideas by helpful votes"),
        BotCommand("mystats", "Your seen, saved, done counts"),
        BotCommand("privacy", "Privacy notice"),
        BotCommand("delete_my_data", "Delete all your data"),
        BotCommand("export", "Download ideas (export saved, export json)"),
        BotCommand("suggest", "Submit a new idea for review"),
        BotCommand("remind", "Daily idea: on | off | time 10:00"),
        BotCommand("browse", "List 5 ideas: browse game"),
        BotCommand("help", "List all commands"),
        BotCommand("stats", "Total ideas and counts"),
        BotCommand("cancel", "Cancel add_idea or suggest"),
    ])


def main() -> None:
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(_set_bot_commands)
        .build()
    )
    if app.job_queue:
        app.job_queue.run_repeating(send_daily_ideas_job, interval=3600)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("idea", send_idea))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("saved", saved_list))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("mystats", mystats_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("suggest", suggest_cmd))
    app.add_handler(CommandHandler("suggestions", suggestions_list_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("remind", remind_cmd))
    app.add_handler(CommandHandler("browse", browse_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("delete_idea", delete_idea_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("privacy", privacy_cmd))
    app.add_handler(CommandHandler("delete_my_data", delete_my_data_cmd))
    app.add_handler(CommandHandler("reject", reject_cmd))
    app.add_handler(InlineQueryHandler(inline_query_handler))
    app.add_handler(CallbackQueryHandler(
        send_idea,
        pattern="^(another_idea|idea_beginner|idea_intermediate|idea_advanced|cat_ui|cat_game|cat_dashboard|cat_productivity|morelike_\\d+)$",
    ))
    app.add_handler(CallbackQueryHandler(save_unsave_callback, pattern=r"^(save_|unsave_)\d+$"))
    app.add_handler(CallbackQueryHandler(feedback_callback, pattern=r"^fb_\d+_[01]$"))
    app.add_handler(CallbackQueryHandler(done_callback, pattern=r"^(done_|undone_)\d+$"))
    app.add_handler(CallbackQueryHandler(share_callback, pattern=r"^share_\d+$"))
    app.add_handler(CallbackQueryHandler(saved_remove_callback, pattern=r"^saved_remove_\d+$"))
    app.add_handler(CallbackQueryHandler(delete_my_data_confirm_callback, pattern=r"^(confirm_delete_my_data|cancel_delete_my_data)$"))
    app.add_handler(CallbackQueryHandler(remind_idea_callback, pattern=r"^remind_[137]_\d+$"))
    app.add_handler(CommandHandler("add_idea", add_idea_cmd))
    app.add_handler(CommandHandler("cancel", cancel_add_idea))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_idea_message))
    logger.info("Bot starting (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
