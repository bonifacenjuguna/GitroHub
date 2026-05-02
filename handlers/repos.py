"""Repo management — GitroHub v1.2"""
import logging

from github import GithubException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import (
    add_to_recent, clear_state, get_active_session,
    get_state, set_state, update_session,
)
from utils.github_helper import format_size, format_time_ago, get_error_message, get_github_client, h

logger = logging.getLogger(__name__)


async def cmd_repos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_repos(update.message, telegram_id, page=0, send_new=True)


async def show_repos(msg_or_query, telegram_id: int, page: int = 0,
                     sort: str = "updated", send_new: bool = False):
    gh = get_github_client(telegram_id)
    if not gh:
        text = "❌ Not logged in. Use /login first."
        if send_new:
            await msg_or_query.reply_text(text)
        else:
            await msg_or_query.edit_message_text(text)
        return

    try:
        user = gh.get_user()
        all_repos = list(user.get_repos())

        if sort == "stars":
            all_repos.sort(key=lambda r: r.stargazers_count, reverse=True)
        elif sort == "size":
            all_repos.sort(key=lambda r: r.size, reverse=True)
        elif sort == "name":
            all_repos.sort(key=lambda r: r.name.lower())
        else:
            all_repos.sort(key=lambda r: (r.pushed_at or r.updated_at), reverse=True)

        total = len(all_repos)
        public_count = sum(1 for r in all_repos if not r.private)
        private_count = total - public_count

        per_page = 5
        start = page * per_page
        page_repos = all_repos[start:start + per_page]
        total_pages = max(1, (total + per_page - 1) // per_page)

        text = (
            f"📦 <b>Your GitHub Repos — {h(user.login)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"Total: <b>{total}</b>   🌍 Public: {public_count}  🔒 Private: {private_count}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for repo in page_repos:
            vis = "🔒" if repo.private else "🌍"
            lang = repo.language or "?"
            updated = format_time_ago(repo.pushed_at or repo.updated_at)
            msg_preview = ""
            try:
                last_commit = list(repo.get_commits())
                if last_commit:
                    cm = last_commit[0].commit.message.split("\n")[0][:35]
                    msg_preview = f' — "{h(cm)}"'
            except Exception:
                pass

            text += (
                f"{vis} <b>{h(repo.name)}</b>\n"
                f"   {h(lang)} • ⭐{repo.stargazers_count} • 🍴{repo.forks_count} • {h(format_size(repo.size))}\n"
                f"   {h(updated)}{msg_preview}\n\n"
            )

            toggle_label = "🔒→🌍 Make Public" if repo.private else "🌍→🔒 Make Private"
            keyboard.append([
                InlineKeyboardButton(toggle_label, callback_data=f"toggle_vis_{repo.full_name}"),
                InlineKeyboardButton("📂 Open", callback_data=f"open_repo_{repo.full_name}"),
            ])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"repos_page_{page-1}_{sort}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if start + per_page < total:
            nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"repos_page_{page+1}_{sort}"))
        keyboard.append(nav)

        keyboard.append([
            InlineKeyboardButton("📅 Date", callback_data=f"repos_sort_updated_{page}"),
            InlineKeyboardButton("⭐ Stars", callback_data=f"repos_sort_stars_{page}"),
            InlineKeyboardButton("📦 Size", callback_data=f"repos_sort_size_{page}"),
            InlineKeyboardButton("🔤 A-Z", callback_data=f"repos_sort_name_{page}"),
        ])
        keyboard.append([
            InlineKeyboardButton("🔍 Search", callback_data="search_repos"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"repos_page_0_{sort}"),
            InlineKeyboardButton("➕ New", callback_data="create_repo"),
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


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_projects(update.message, telegram_id, send_new=True)


async def show_projects(msg_or_query, telegram_id: int, send_new: bool = False):
    session = get_active_session(telegram_id)
    if not session:
        text = "❌ Not logged in. Use /login first."
        if send_new:
            await msg_or_query.reply_text(text)
        else:
            await msg_or_query.edit_message_text(text)
        return

    username = session["github_username"]
    active_repo = session.get("active_repo")
    active_branch = session.get("active_branch", "main")
    recent_repos = session.get("recent_repos") or []
    pinned_repos = session.get("pinned_repos") or []

    text = f"🗄️ <b>Your Projects — {h(username)}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []

    if pinned_repos:
        text += "📌 <b>PINNED</b>\n"
        pin_row = []
        for repo in pinned_repos[:4]:
            name = repo.split("/")[-1]
            pin_row.append(InlineKeyboardButton(f"⭐ {name}", callback_data=f"open_repo_{repo}"))
        keyboard.append(pin_row)
        text += "\n"

    if active_repo:
        text += f"🟢 <b>ACTIVE</b>\n📁 <code>{h(active_repo)}</code> @ <code>{h(active_branch)}</code>\n\n"
        keyboard.append([
            InlineKeyboardButton("📂 Open", callback_data="browse"),
            InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
            InlineKeyboardButton("📜 Log", callback_data="log"),
        ])

    if recent_repos:
        text += "⏱ <b>RECENT</b>\n"
        for repo in recent_repos[:5]:
            name = repo.split("/")[-1]
            text += f"• {h(name)}\n"
            keyboard.append([
                InlineKeyboardButton(f"📁 {name}", callback_data=f"open_repo_{repo}"),
                InlineKeyboardButton("⬆️", callback_data=f"upload_to_{repo}"),
                InlineKeyboardButton("📜", callback_data=f"log_of_{repo}"),
            ])

    keyboard.append([
        InlineKeyboardButton("➕ New Repo", callback_data="create_repo"),
        InlineKeyboardButton("📦 All Repos", callback_data="repos"),
        InlineKeyboardButton("🔄 Refresh", callback_data="projects"),
    ])

    if send_new:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if context.args:
        repo_name = context.args[0]
        set_state(telegram_id, "creating_repo", {"name": repo_name, "step": "visibility"})
        await ask_visibility(update.message, repo_name)
    else:
        set_state(telegram_id, "creating_repo", {"step": "name"})
        await update.message.reply_text(
            "📝 <b>New Repo</b>\n\nWhat's the repo name?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        )


async def ask_visibility(message, repo_name: str):
    await message.reply_text(
        f"🔒 <b>Visibility for</b> <code>{h(repo_name)}</code>?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🌍 Public", callback_data="repo_vis_public"),
            InlineKeyboardButton("🔒 Private", callback_data="repo_vis_private"),
        ], [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    )


async def cmd_use(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    gh = get_github_client(telegram_id)
    if not gh:
        await update.message.reply_text("❌ Not logged in. Use /login first.", parse_mode="HTML")
        return
    if not context.args:
        await show_projects(update.message, telegram_id, send_new=True)
        return
    await _open_repo(update.message, telegram_id, context.args[0], send_new=True)


async def _open_repo(msg_or_query, telegram_id: int, repo_name: str, send_new: bool = False):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    if not gh or not session:
        return
    username = session["github_username"]
    if "/" not in repo_name:
        repo_name = f"{username}/{repo_name}"
    try:
        repo = gh.get_repo(repo_name)
        update_session(telegram_id, active_repo=repo.full_name, active_branch=repo.default_branch)
        add_to_recent(telegram_id, repo.full_name)
        is_own = repo.owner.login == username
        vis = "🔒 Private" if repo.private else "🌍 Public"
        readonly_note = "\n\n⚠️ <b>Read-only</b> — not your repo.\nYou can: /browse /read /download" if not is_own else ""

        text = (
            f"📁 <b>{h(repo.name)}</b>\n"
            f"{vis} • {h(repo.language or '?')} • {h(format_size(repo.size))}\n"
            f"Branch: <code>{h(repo.default_branch)}</code>{readonly_note}"
        )
        keyboard = [
            [InlineKeyboardButton("📂 Browse", callback_data="browse"),
             InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
             InlineKeyboardButton("⬇️ Download", callback_data="download_menu")],
            [InlineKeyboardButton("🌿 Branches", callback_data="branches"),
             InlineKeyboardButton("📜 Log", callback_data="log"),
             InlineKeyboardButton("📊 Stats", callback_data="stats")],
            [InlineKeyboardButton("📝 Issues", callback_data="issues"),
             InlineKeyboardButton("🚀 Releases", callback_data="releases"),
             InlineKeyboardButton("⚙️ Settings", callback_data="repo_settings")],
            [InlineKeyboardButton("📌 Pin", callback_data=f"pin_repo_{repo.full_name}"),
             InlineKeyboardButton("🏠 Home", callback_data="home")],
        ]
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


# Make _open_repo accessible for callback router
open_repo_from_callback = _open_repo
