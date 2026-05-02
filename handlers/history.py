"""Commit history — GitroHub v1.2"""
import logging

from github import GithubException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import clear_state, get_active_session, get_state, set_state
from utils.github_helper import format_time_ago, get_error_message, get_github_client, h

logger = logging.getLogger(__name__)


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.", parse_mode="HTML")
        return
    await show_log(update.message, telegram_id, send_new=True)


async def show_log(msg_or_query, telegram_id: int, send_new: bool = False):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        commits = list(repo.get_commits(sha=branch))[:10]

        text = (
            f"📜 <b>Commits — {h(repo.name)}</b> @ <code>{h(branch)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        keyboard = []
        for i, commit in enumerate(commits):
            sha_short = commit.sha[:7]
            msg = commit.commit.message.split("\n")[0][:40]
            when = format_time_ago(commit.commit.author.date)
            text += f"{i+1}. <code>{h(sha_short)}</code>  \"{h(msg)}\"\n    {h(when)}\n\n"
            keyboard.append([
                InlineKeyboardButton(f"👁 {sha_short}", callback_data=f"view_commit_{commit.sha}"),
                InlineKeyboardButton("↩️ Rollback", callback_data=f"confirm_rollback_{commit.sha}_{sha_short}"),
            ])

        keyboard.append([
            InlineKeyboardButton("↩️ Undo Last", callback_data="confirm_undo"),
            InlineKeyboardButton("⬅️ Back", callback_data="home"),
        ])

        if send_new:
            await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    except GithubException as e:
        err = get_error_message(e.status)
        if send_new:
            await msg_or_query.reply_text(err, parse_mode="HTML")
        else:
            await msg_or_query.edit_message_text(err, parse_mode="HTML")


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        commits = list(repo.get_commits(sha=branch))
        if not commits:
            await update.message.reply_text("❌ No commits to undo.", parse_mode="HTML")
            return
        last = commits[0]
        sha_short = last.sha[:7]
        msg = last.commit.message.split("\n")[0][:40]
        when = format_time_ago(last.commit.author.date)
        set_state(telegram_id, "confirming_undo", {
            "sha": last.sha,
            "parent_sha": commits[1].sha if len(commits) > 1 else None
        })
        await update.message.reply_text(
            f"↩️ <b>Undo last commit?</b>\n\n"
            f"<code>{h(sha_short)}</code> — \"{h(msg)}\"\n{h(when)}\n\n"
            f"⚠️ This will reverse the commit.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes, undo", callback_data="confirm_undo_action"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def do_undo(message, telegram_id: int):
    state_info = get_state(telegram_id)
    state_data = state_info.get("state_data", {})
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    parent_sha = state_data.get("parent_sha")
    if not parent_sha:
        await message.reply_text("❌ Cannot undo — no parent commit found.", parse_mode="HTML")
        clear_state(telegram_id)
        return
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        ref = repo.get_git_ref(f"heads/{branch}")
        ref.edit(parent_sha, force=True)
        clear_state(telegram_id)
        await message.reply_text(
            f"✅ <b>Commit reversed!</b>\n↩️ <code>{h(branch)}</code> back to previous state.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 Log", callback_data="log"),
                InlineKeyboardButton("⬆️ Upload again", callback_data="upload_menu"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        clear_state(telegram_id)
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_rollback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await show_log(update.message, telegram_id, send_new=True)
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
        await message.reply_text(
            f"↩️ <b>Rollback to</b> <code>{h(sha_short)}</code>?\n\n"
            f"\"{h(msg)}\"\n{h(when)}\n\n"
            f"⚠️ All commits after this will be lost.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes, rollback", callback_data=f"do_rollback_{sha}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


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
            f"✅ <b>Rolled back!</b>\n📍 <code>{h(branch)}</code> now at <code>{h(sha[:7])}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 Log", callback_data="log"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        clear_state(telegram_id)
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


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
            f"👁 <b>Commit</b> <code>{h(sha[:7])}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💬 \"{h(msg)}\"\n"
            f"👤 {h(author)}\n"
            f"🕐 {h(when)}\n\n"
            f"<b>Changed files:</b>\n"
        )
        for f in files:
            icon = {"added": "✨", "modified": "🟡", "removed": "🗑️"}.get(f.status, "📄")
            stats = f"+{f.additions} -{f.deletions}"
            text += f"{icon} <code>{h(f.filename)}</code>  <code>{stats}</code>\n"
        await message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("↩️ Rollback to this", callback_data=f"confirm_rollback_{sha}_{sha[:7]}"),
                InlineKeyboardButton("📜 Back to log", callback_data="log"),
            ]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")
