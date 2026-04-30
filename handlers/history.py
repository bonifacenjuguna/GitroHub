import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_active_session, get_state, set_state, clear_state
from utils.github_helper import get_github_client, get_error_message, format_time_ago
from handlers.core import escape_md
from github import GithubException

logger = logging.getLogger(__name__)


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.")
        return

    await show_log(update.message, telegram_id)


async def show_log(message, telegram_id: int, edit: bool = False):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        commits = list(repo.get_commits(sha=branch))[:10]

        text = (
            f"📜 *Commits — {escape_md(session['active_repo'].split('/')[-1])}*"
            f" @ `{escape_md(branch)}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for i, commit in enumerate(commits):
            sha_short = commit.sha[:7]
            msg = commit.commit.message.split("\n")[0][:40]
            when = format_time_ago(commit.commit.author.date)

            text += (
                f"{i+1}\\. `{escape_md(sha_short)}`  "
                f"\"{escape_md(msg)}\"\n"
                f"    {escape_md(when)}\n\n"
            )

            keyboard.append([
                InlineKeyboardButton(f"👁 {sha_short}",
                    callback_data=f"view_commit_{commit.sha}"),
                InlineKeyboardButton("↩️ Rollback",
                    callback_data=f"confirm_rollback_{commit.sha}_{sha_short}"),
            ])

        keyboard.append([
            InlineKeyboardButton("↩️ Undo Last", callback_data="confirm_undo"),
            InlineKeyboardButton("⬅️ Back", callback_data="home"),
        ])

        if edit and hasattr(message, 'edit_text'):
            await message.edit_text(text, parse_mode="MarkdownV2",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await message.reply_text(text, parse_mode="MarkdownV2",
                                     reply_markup=InlineKeyboardMarkup(keyboard))

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        commits = list(repo.get_commits(sha=branch))

        if not commits:
            await update.message.reply_text("❌ No commits to undo.")
            return

        last = commits[0]
        sha_short = last.sha[:7]
        msg = last.commit.message.split("\n")[0][:40]
        when = format_time_ago(last.commit.author.date)

        set_state(telegram_id, "confirming_undo", {
            "sha": last.sha,
            "parent_sha": commits[1].sha if len(commits) > 1 else None
        })

        keyboard = [[
            InlineKeyboardButton("✅ Yes, undo", callback_data="confirm_undo_action"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]

        await update.message.reply_text(
            f"↩️ *Undo last commit?*\n\n"
            f"`{escape_md(sha_short)}` — \"{escape_md(msg)}\"\n"
            f"{escape_md(when)}\n\n"
            f"⚠️ This will reverse the commit\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def do_undo(message, telegram_id: int):
    """Perform the actual undo by reverting to parent commit."""
    state_info = get_state(telegram_id)
    state_data = state_info.get("state_data", {})
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    parent_sha = state_data.get("parent_sha")
    if not parent_sha:
        await message.reply_text("❌ Cannot undo — no parent commit found.")
        clear_state(telegram_id)
        return

    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")

        # Force update ref to parent
        ref = repo.get_git_ref(f"heads/{branch}")
        ref.edit(parent_sha, force=True)
        clear_state(telegram_id)

        await message.reply_text(
            f"✅ *Commit reversed\\!*\n\n"
            f"↩️ Repo back to previous state on `{escape_md(branch)}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 View Log", callback_data="log"),
                InlineKeyboardButton("⬆️ Upload again", callback_data="upload_menu"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )

    except GithubException as e:
        clear_state(telegram_id)
        await message.reply_text(get_error_message(e.status))


async def cmd_rollback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await show_log(update.message, telegram_id)
        return

    sha = context.args[0]
    await confirm_rollback(update.message, telegram_id, sha, sha[:7])


async def confirm_rollback(message, telegram_id: int, sha: str, sha_short: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        commit = repo.get_commit(sha)
        msg = commit.commit.message.split("\n")[0][:40]
        when = format_time_ago(commit.commit.author.date)

        set_state(telegram_id, "confirming_rollback", {"sha": sha})

        keyboard = [[
            InlineKeyboardButton("✅ Yes, rollback",
                callback_data=f"do_rollback_{sha}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]

        await message.reply_text(
            f"↩️ *Rollback to* `{escape_md(sha_short)}`*?*\n\n"
            f"\"{escape_md(msg)}\"\n"
            f"{escape_md(when)}\n\n"
            f"⚠️ All commits after this will be lost\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def do_rollback(message, telegram_id: int, sha: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")

        ref = repo.get_git_ref(f"heads/{branch}")
        ref.edit(sha, force=True)
        clear_state(telegram_id)

        await message.reply_text(
            f"✅ *Rolled back successfully\\!*\n\n"
            f"📍 `{escape_md(branch)}` now at `{escape_md(sha[:7])}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 View Log", callback_data="log"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )

    except GithubException as e:
        clear_state(telegram_id)
        await message.reply_text(get_error_message(e.status))


async def view_commit(message, telegram_id: int, sha: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        commit = repo.get_commit(sha)
        files = list(commit.files)[:10]

        msg = commit.commit.message.split("\n")[0]
        when = format_time_ago(commit.commit.author.date)
        author = commit.commit.author.name

        text = (
            f"👁 *Commit* `{escape_md(sha[:7])}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 \"{escape_md(msg)}\"\n"
            f"👤 {escape_md(author)}\n"
            f"🕐 {escape_md(when)}\n\n"
            f"*Changed files:*\n"
        )

        for f in files:
            icon = {"added": "✨", "modified": "🟡",
                    "removed": "🗑️"}.get(f.status, "📄")
            additions = f"+{f.additions}" if f.additions else ""
            deletions = f"-{f.deletions}" if f.deletions else ""
            stats = f" ({additions} {deletions})".strip("() ")
            text += f"{icon} `{escape_md(f.filename)}`  `{escape_md(stats)}`\n"

        keyboard = [[
            InlineKeyboardButton("↩️ Rollback to this",
                callback_data=f"confirm_rollback_{sha}_{sha[:7]}"),
            InlineKeyboardButton("📜 Back to log", callback_data="log"),
        ]]

        await message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))
