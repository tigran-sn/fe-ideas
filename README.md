# Front-end Ideas Telegram Bot

A Telegram bot that suggests front-end pet project ideas on demand.

## Setup

1. **Create a bot and get a token**
   - Open Telegram and search for [@BotFather](https://t.me/BotFather).
   - Send `/newbot`, follow the prompts, and choose a name and username.
   - Copy the token BotFather gives you.

2. **Configure the token**
   - In the project root, create a file named `.env`.
   - Add one line: `BOT_TOKEN=your_token_here` (replace with your actual token).
   - Optional: add `ADMIN_USER_IDS=your_telegram_user_id` (or comma-separated IDs) to allow those users to add ideas via `/add_idea`.
   - Do not commit `.env`; it is listed in `.gitignore`.

3. **Install dependencies and run**
   ```bash
   pip install -r requirements.txt
   python main.py
   ```

The bot will start and listen for messages. In Telegram, open your bot and send `/start` or `/idea` to get a random front-end project idea. Use the "Another idea" button to get more without typing `/idea` again.

## Commands

- `/start` — Welcome and quick buttons for first idea. Share link: `t.me/YourBot?start=idea_42`.
- `/idea` — Random idea. Filter: `/idea beginner`, `/idea game`, `/idea intermediate game`, or `/idea tag react` (if ideas have tags).
- Under each idea: **Save**, **Share**, **I've done this**, **More like this**, **👍 Helpful** / **👎 Not helpful** (feedback), and **Remind in 1/3/7 days** (sends the idea back to you when due).
- `/search <keyword>` — Search in title, description, and tags.
- `/saved` — Your saved ideas with **Remove** per idea.
- `/today` — Idea of the day.
- `/top` — Top ideas by helpful votes (👍/👎).
- `/mystats` — Your counts: seen, saved, done; plus your **streak** (consecutive days you requested an idea).
- `/privacy` — What data the bot stores (seen, saved, done, activity, reminders, broadcast list).
- `/delete_my_data` — Delete all your data; confirmation required.
- `/export` — Download all ideas. `/export saved` for your saved; add `json` for JSON (e.g. `/export json`, `/export saved json`).
- `/suggest` — Submit an idea for review (duplicate title warned). `/cancel` to abort.
- `/remind on` — Daily idea at 09:00 UTC. `/remind time 10:00` to set time (UTC). `/remind off` to stop.
- `/browse <category>` — List 5 ideas from category (ui, game, dashboard, productivity).
- `/help` — Full command list.
- `/stats` — Total ideas and counts by difficulty/category.
- **Admin:** `/add_idea`, `/suggestions`, `/approve <id>`, `/reject <id> [reason]` (reject suggestion, optionally notify submitter), `/backup` (download ideas + suggestions), `/broadcast <text>`, `/delete_idea <id>`.

**Inline mode:** Enable in BotFather (Bot Settings → Inline Mode). Then type `@YourBot keyword` in any chat to get matching ideas as inline results.

## Project structure

- `main.py` — Bot entry point, commands, callbacks, inline handler, hourly job (daily ideas + idea reminders).
- `ideas.py` — Ideas CRUD, filters, search, tags, delete, stats.
- `ideas.json` — Curated ideas (optional `tags`: `["react", "api"]` for `/idea tag react`).
- `config.py` — `BOT_TOKEN`, `ADMIN_USER_IDS` from `.env`.
- `favorites.py`, `seen.py`, `done.py` — Per-user saved, seen, done.
- `feedback.py` — Per-idea 👍/👎 counts; `get_top_idea_ids()` for `/top`.
- `activity.py` — Per-user last request date and streak (for `/mystats`).
- `idea_reminders.py` — Per-user “remind me in N days” for a specific idea; due reminders sent by the hourly job.
- `suggestions.py`, `reminders.py`, `users.py` — Suggestions, daily reminder (on/off + time), broadcast list.

Data files (created at runtime, in `.gitignore`): `seen.json`, `favorites.json`, `done.json`, `feedback.json`, `users.json`, `reminders.json`, `suggestions.json`, `activity.json`, `idea_reminders.json`.
