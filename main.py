"""
GitroHub Bot — v1.3
Complete rewrite: HTML parse mode, global error handler,
all callbacks handled, stable & crash-resistant.
"""
import asyncio
import base64
import logging
import os
import traceback

from aiohttp import web
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    MessageHandler, filters,
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", 0))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.environ.get("PORT", 8080))
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


# ── Admin guard ───────────────────────────────────────────────────────────────

def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID


def admin_only(func):
    async def wrapper(update: Update, context):
        if not is_admin(update):
            from handlers.core import send_private_message
            await send_private_message(update, update.effective_user.id)
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


# ── Global error handler ──────────────────────────────────────────────────────

async def error_handler(update: object, context) -> None:
    """Log errors and notify admin without crashing the bot."""
    logger.error("Exception while handling update:", exc_info=context.error)

    if isinstance(context.error, BadRequest):
        logger.warning(f"BadRequest: {context.error}")
        return  # Don't notify user for bad requests — usually safe to ignore

    if isinstance(update, Update) and update.effective_user:
        try:
            if update.callback_query:
                await update.callback_query.answer("❌ Something went wrong. Please try again.", show_alert=True)
            elif update.message:
                await update.message.reply_text(
                    "❌ <b>An error occurred</b>\nPlease try again or use /cancel to reset.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌ Cancel & Reset", callback_data="cancel"),
                        InlineKeyboardButton("🏠 Home", callback_data="home"),
                    ]])
                )
        except Exception:
            pass


# ── Callback router ───────────────────────────────────────────────────────────

async def handle_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    telegram_id = update.effective_user.id

    from database.db import (
        clear_state, get_active_session, get_state,
        set_state, update_session, add_to_recent,
    )
    from utils.github_helper import h, get_error_message

    # ── Helper: safe edit ─────────────────────────────────────────────────────
    async def edit(text, keyboard=None, parse_mode="HTML"):
        try:
            await query.edit_message_text(
                text, parse_mode=parse_mode,
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
            )
        except BadRequest as e:
            if "message is not modified" not in str(e).lower():
                raise

    # ── noop ──────────────────────────────────────────────────────────────────
    if data == "noop":
        return

    # ── cancel ────────────────────────────────────────────────────────────────
    if data == "cancel":
        clear_state(telegram_id)
        await edit(
            "❌ <b>Cancelled — nothing was changed.</b>\n\n💡 Use /help to see what you can do",
            [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
        )
        return

    # ── home ──────────────────────────────────────────────────────────────────
    if data == "home":
        session = get_active_session(telegram_id)
        if session:
            username = session["github_username"]
            repo = session.get("active_repo") or "No active repo"
            branch = session.get("active_branch") or "main"
            keyboard = [
                [InlineKeyboardButton("📂 Projects", callback_data="projects"),
                 InlineKeyboardButton("📦 Repos", callback_data="repos"),
                 InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu")],
                [InlineKeyboardButton("⬇️ Download", callback_data="download_menu"),
                 InlineKeyboardButton("🌿 Branches", callback_data="branches"),
                 InlineKeyboardButton("📜 Log", callback_data="log")],
                [InlineKeyboardButton("📊 Stats", callback_data="stats"),
                 InlineKeyboardButton("👤 Accounts", callback_data="show_accounts"),
                 InlineKeyboardButton("❓ Help", callback_data="help_back")],
            ]
            await edit(
                f"🏠 <b>Home</b>\n\n"
                f"👤 <code>{h(username)}</code>\n"
                f"📁 <code>{h(repo)}</code> @ <code>{h(branch)}</code>",
                keyboard
            )
        else:
            from handlers.auth import generate_oauth_url
            oauth_url, state = generate_oauth_url(telegram_id)
            set_state(telegram_id, "awaiting_oauth", {"state": state})
            await edit(
                "🏠 <b>Home</b>\n\nNot logged in.",
                [[InlineKeyboardButton("🔗 Connect GitHub", url=oauth_url)]]
            )
        return

    # ── Auth ──────────────────────────────────────────────────────────────────

    if data == "login_start":
        from handlers.auth import generate_oauth_url
        oauth_url, state = generate_oauth_url(telegram_id)
        set_state(telegram_id, "awaiting_oauth", {"state": state})
        await edit(
            "🔐 <b>Connect your GitHub account</b>\n\n"
            "Tap the button below to authorize GitroHub on GitHub.\n"
            "⏳ Waiting for GitHub approval...",
            [[InlineKeyboardButton("🔗 Connect GitHub Account", url=oauth_url)],
             [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data == "show_accounts":
        from handlers.auth import show_accounts_edit
        await show_accounts_edit(query, telegram_id)
        return

    if data.startswith("switch_account_"):
        username = data[len("switch_account_"):]
        from database.db import switch_session
        switch_session(telegram_id, username)
        session = get_active_session(telegram_id)
        repo = session.get("active_repo") or "None"
        branch = session.get("active_branch") or "main"
        await edit(
            f"✅ <b>Now on {h(username)}</b> 👋\n\n"
            f"📍 Restored:\nRepo: <code>{h(repo)}</code>\nBranch: <code>{h(branch)}</code>",
            [[InlineKeyboardButton("📂 Projects", callback_data="projects"),
              InlineKeyboardButton("📦 Repos", callback_data="repos")],
             [InlineKeyboardButton("🏠 Home", callback_data="home")]]
        )
        return

    if data.startswith("remove_account_"):
        username = data[len("remove_account_"):]
        await edit(
            f"⚠️ <b>Remove {h(username)}?</b>\n\nThis disconnects the account. Your GitHub data is untouched.",
            [[InlineKeyboardButton("✅ Yes, remove", callback_data=f"confirm_remove_{username}"),
              InlineKeyboardButton("❌ Cancel", callback_data="show_accounts")]]
        )
        return

    if data.startswith("confirm_remove_"):
        username = data[len("confirm_remove_"):]
        from database.db import delete_session
        delete_session(telegram_id, username)
        await edit(
            f"✅ <code>{h(username)}</code> disconnected.",
            [[InlineKeyboardButton("👤 Accounts", callback_data="show_accounts"),
              InlineKeyboardButton("🏠 Home", callback_data="home")]]
        )
        return

    if data.startswith("confirm_logout_"):
        username = data[len("confirm_logout_"):]
        from database.db import delete_session
        delete_session(telegram_id, username)
        await edit(
            f"✅ Logged out from <code>{h(username)}</code>.",
            [[InlineKeyboardButton("🔗 Login again", callback_data="login_start"),
              InlineKeyboardButton("👤 Accounts", callback_data="show_accounts")]]
        )
        return

    # ── Repos & Projects ──────────────────────────────────────────────────────

    if data == "projects":
        from handlers.repos import show_projects
        await show_projects(query, telegram_id, send_new=False)
        return

    if data == "repos":
        from handlers.repos import show_repos
        await show_repos(query, telegram_id, page=0, send_new=False)
        return

    if data.startswith("repos_page_"):
        parts = data.split("_")
        page = int(parts[2])
        sort = parts[3] if len(parts) > 3 else "updated"
        from handlers.repos import show_repos
        await show_repos(query, telegram_id, page=page, sort=sort, send_new=False)
        return

    if data.startswith("repos_sort_"):
        parts = data.split("_")
        sort = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 0
        from handlers.repos import show_repos
        await show_repos(query, telegram_id, page=page, sort=sort, send_new=False)
        return

    if data == "create_repo":
        from database.db import set_state
        set_state(telegram_id, "creating_repo", {"step": "name"})
        await edit(
            "📝 <b>New Repo</b>\n\nWhat's the repo name?",
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data.startswith("open_repo_"):
        repo_full = data[len("open_repo_"):]
        from handlers.repos import open_repo_from_callback
        await open_repo_from_callback(query, telegram_id, repo_full, send_new=False)
        return

    if data.startswith("upload_to_"):
        repo_full = data[len("upload_to_"):]
        from database.db import update_session, add_to_recent
        update_session(telegram_id, active_repo=repo_full)
        add_to_recent(telegram_id, repo_full)
        await edit(
            f"✅ Active repo set to <code>{h(repo_full)}</code>\n\nNow upload your files:",
            [[InlineKeyboardButton("📄 Single file", callback_data="upload_single"),
              InlineKeyboardButton("📦 Batch", callback_data="upload_batch")],
             [InlineKeyboardButton("🗜️ ZIP Mirror", callback_data="upload_mirror"),
              InlineKeyboardButton("🗜️ ZIP Update", callback_data="upload_update")],
             [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data.startswith("log_of_"):
        repo_full = data[len("log_of_"):]
        from database.db import update_session
        update_session(telegram_id, active_repo=repo_full)
        from handlers.history import show_log
        await show_log(query, telegram_id, send_new=False)
        return

    if data.startswith("pin_repo_"):
        repo_name = data[len("pin_repo_"):]
        session = get_active_session(telegram_id)
        if session:
            pinned = list(session.get("pinned_repos") or [])
            if repo_name not in pinned:
                pinned.append(repo_name)
                update_session(telegram_id, pinned_repos=pinned)
        await query.answer("📌 Pinned!", show_alert=False)
        return

    if data.startswith("toggle_vis_"):
        repo_full = data[len("toggle_vis_"):]
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(repo_full)
            is_private = repo.private
            action = "Make Public" if is_private else "Make Private"
            warning = "⚠️ <b>Making PUBLIC!</b> Everyone can see it.\n\n" if is_private else "⚠️ <b>Making PRIVATE?</b>\n\n"
            await edit(
                f"{warning}Repo: <code>{h(repo_full)}</code>\nCurrent: {'🔒 Private' if is_private else '🌍 Public'}",
                [[InlineKeyboardButton(f"✅ Yes, {action}", callback_data=f"confirm_vis_{repo_full}"),
                  InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
            )
        except GithubException as e:
            await edit(get_error_message(e.status))
        return

    if data.startswith("confirm_vis_"):
        repo_full = data[len("confirm_vis_"):]
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(repo_full)
            repo.edit(private=not repo.private)
            new_vis = "🔒 Private" if repo.private else "🌍 Public"
            await edit(
                f"✅ <code>{h(repo_full)}</code> is now {new_vis}",
                [[InlineKeyboardButton("📂 Open", callback_data=f"open_repo_{repo_full}"),
                  InlineKeyboardButton("🏠 Home", callback_data="home")]]
            )
        except GithubException as e:
            await edit(get_error_message(e.status))
        return

    # ── Repo settings ─────────────────────────────────────────────────────────

    if data == "repo_settings":
        session = get_active_session(telegram_id)
        if not session or not session.get("active_repo"):
            await edit("❌ No active repo.")
            return
        repo_name = session["active_repo"]
        await edit(
            f"⚙️ <b>Settings — {h(repo_name.split('/')[-1])}</b>",
            [[InlineKeyboardButton("✏️ Rename", callback_data="rs_rename"),
              InlineKeyboardButton("🔒 Visibility", callback_data=f"toggle_vis_{repo_name}")],
             [InlineKeyboardButton("📄 Edit README", callback_data="rs_readme"),
              InlineKeyboardButton("🏷️ Topics", callback_data="rs_topics")],
             [InlineKeyboardButton("📋 Make Template", callback_data="rs_template"),
              InlineKeyboardButton("📤 Transfer", callback_data="rs_transfer")],
             [InlineKeyboardButton("🗑️ Delete Repo", callback_data="rs_delete"),
              InlineKeyboardButton("⬅️ Back", callback_data=f"open_repo_{repo_name}")]]
        )
        return

    if data == "rs_delete":
        session = get_active_session(telegram_id)
        if session and session.get("active_repo"):
            set_state(telegram_id, "deleting_repo_step1", {"repo": session["active_repo"]})
            await edit(
                f"⚠️ <b>Delete {h(session['active_repo'])} permanently?</b>\n\n"
                f"This is IRREVERSIBLE.\n\n<b>Step 1/3</b> — Type the repo name in chat:",
                [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
            )
        return

    if data == "rs_rename":
        set_state(telegram_id, "awaiting_rename_input", {})
        await edit("✏️ <b>Rename repo</b>\n\nType the new name:",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "rs_readme":
        session = get_active_session(telegram_id)
        if session and session.get("active_repo"):
            from handlers.files import start_edit
            await start_edit(query.message, telegram_id, "README.md")
        return

    if data == "rs_topics":
        session = get_active_session(telegram_id)
        if session and session.get("active_repo"):
            from utils.github_helper import get_github_client
            from github import GithubException
            gh = get_github_client(telegram_id)
            try:
                repo = gh.get_repo(session["active_repo"])
                topics = repo.get_topics()
                set_state(telegram_id, "awaiting_topics", {})
                await edit(
                    f"🏷️ <b>Topics — {h(repo.name)}</b>\n\nCurrent: <code>{h(', '.join(topics) or 'None')}</code>\n\nType new topics (comma separated):",
                    [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
                )
            except GithubException as e:
                await edit(get_error_message(e.status))
        return

    if data == "rs_template":
        session = get_active_session(telegram_id)
        if session and session.get("active_repo"):
            from utils.github_helper import get_github_client
            from github import GithubException
            gh = get_github_client(telegram_id)
            try:
                repo = gh.get_repo(session["active_repo"])
                repo.edit(is_template=True)
                await edit(f"✅ <code>{h(session['active_repo'])}</code> is now a template repo.",
                           [[InlineKeyboardButton("⬅️ Back", callback_data="repo_settings")]])
            except GithubException as e:
                await edit(get_error_message(e.status))
        return

    if data == "rs_transfer":
        set_state(telegram_id, "awaiting_transfer_username", {})
        await edit("📤 <b>Transfer repo</b>\n\nType the GitHub username to transfer to:\n\n⚠️ Requires 3-step verification.",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "do_delete_repo":
        session = get_active_session(telegram_id)
        if not session or not session.get("active_repo"):
            await edit("❌ No active repo.")
            return
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        repo_full = session["active_repo"]
        try:
            gh.get_repo(repo_full).delete()
            update_session(telegram_id, active_repo=None, active_branch="main")
            clear_state(telegram_id)
            await edit(
                f"💀 <b>{h(repo_full.split('/')[-1])}</b> permanently deleted.",
                [[InlineKeyboardButton("📦 All Repos", callback_data="repos"),
                  InlineKeyboardButton("🏠 Home", callback_data="home")]]
            )
        except GithubException as e:
            clear_state(telegram_id)
            await edit(get_error_message(e.status))
        return

    if data.startswith("confirm_rename_"):
        new_name = data[len("confirm_rename_"):]
        session = get_active_session(telegram_id)
        if not session or not session.get("active_repo"):
            await edit("❌ No active repo.")
            return
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        old_full = session["active_repo"]
        try:
            repo = gh.get_repo(old_full)
            repo.edit(name=new_name)
            new_full = f"{old_full.split('/')[0]}/{new_name}"
            update_session(telegram_id, active_repo=new_full)
            clear_state(telegram_id)
            await edit(
                f"✅ Renamed to <code>{h(new_name)}</code>.",
                [[InlineKeyboardButton("📂 Open", callback_data=f"open_repo_{new_full}"),
                  InlineKeyboardButton("🏠 Home", callback_data="home")]]
            )
        except GithubException as e:
            clear_state(telegram_id)
            await edit(get_error_message(e.status))
        return

    # ── Browse & Files ────────────────────────────────────────────────────────

    if data in ("browse", "browse_root"):
        from handlers.files import show_browse
        await show_browse(query, telegram_id, "", send_new=False)
        return

    if data.startswith("browse_"):
        path = data[len("browse_"):]
        from handlers.files import show_browse
        await show_browse(query, telegram_id, path, send_new=False)
        return

    if data.startswith("read_file_"):
        path = data[len("read_file_"):]
        from handlers.files import read_file
        await read_file(query.message, telegram_id, path)
        return

    if data.startswith("edit_file_"):
        path = data[len("edit_file_"):]
        from handlers.files import start_edit
        await start_edit(query.message, telegram_id, path)
        return

    if data.startswith("delete_file_"):
        path = data[len("delete_file_"):]
        await edit(
            f"🗑️ <b>Delete</b> <code>{h(path)}</code>?\n\nThis cannot be undone.",
            [[InlineKeyboardButton("✅ Yes, delete", callback_data=f"confirm_delete_{path}"),
              InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data.startswith("confirm_delete_"):
        path = data[len("confirm_delete_"):]
        session = get_active_session(telegram_id)
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(session["active_repo"])
            branch = session.get("active_branch", "main")
            fc = repo.get_contents(path, ref=branch)
            repo.delete_file(path, f"Delete {path}", fc.sha, branch=branch)
            await edit(
                f"🗑️ <code>{h(path)}</code> deleted.",
                [[InlineKeyboardButton("📂 Browse", callback_data="browse"),
                  InlineKeyboardButton("🏠 Home", callback_data="home")]]
            )
        except GithubException as e:
            await edit(get_error_message(e.status))
        return

    if data.startswith("copy_url_"):
        path = data[len("copy_url_"):]
        session = get_active_session(telegram_id)
        if session:
            branch = session.get("active_branch", "main")
            url = f"https://github.com/{session['active_repo']}/blob/{branch}/{path}"
            await edit(
                f"🔗 <b>File URL:</b>\n<code>{h(url)}</code>\n\nCopy the link above.",
                [[InlineKeyboardButton("⬅️ Back", callback_data=f"browse_{'/'.join(path.split('/')[:-1])}"),
                  InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
            )
        return

    if data.startswith("upload_to_path_"):
        path = data[len("upload_to_path_"):]
        set_state(telegram_id, "awaiting_single_file", {"path": path})
        await edit(
            f"📬 <b>Ready — send your file</b>\n\nWill upload to: <code>{h(path or 'repo root')}</code>",
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data in ("search_repo", "search_repos"):
        session = get_active_session(telegram_id)
        set_state(telegram_id, "awaiting_search", {})
        label = session["active_repo"] if session and session.get("active_repo") else "repo"
        await edit(
            f"🔍 <b>Search in</b> <code>{h(label)}</code>\n\nSend your search term:",
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data.startswith("confirm_move_"):
        rest = data[len("confirm_move_"):]
        if "_TO_" in rest:
            src, dst = rest.split("_TO_", 1)
            session = get_active_session(telegram_id)
            from utils.github_helper import get_github_client
            from github import GithubException
            gh = get_github_client(telegram_id)
            try:
                repo = gh.get_repo(session["active_repo"])
                branch = session.get("active_branch", "main")
                fc = repo.get_contents(src, ref=branch)
                content = base64.b64decode(fc.content).decode("utf-8", errors="replace")
                repo.create_file(dst, f"Move {src} to {dst}", content, branch=branch)
                repo.delete_file(src, f"Move {src} to {dst}", fc.sha, branch=branch)
                await edit(
                    f"✅ Moved <code>{h(src)}</code> → <code>{h(dst)}</code>",
                    [[InlineKeyboardButton("📂 Browse", callback_data="browse"),
                      InlineKeyboardButton("🏠 Home", callback_data="home")]]
                )
            except GithubException as e:
                await edit(get_error_message(e.status))
        return

    # ── Upload ────────────────────────────────────────────────────────────────

    if data == "upload_menu":
        from handlers.upload import show_upload_menu
        await show_upload_menu(query, telegram_id, edit=True)
        return

    if data == "upload_single":
        set_state(telegram_id, "awaiting_path_declare", {})
        await edit(
            "📄 <b>Single file upload</b>\n\nUse: <code>/upload src/app.py</code>\nThen send your file.",
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data == "upload_batch":
        set_state(telegram_id, "batch_declare_paths", {})
        await edit(
            "📦 <b>Batch upload</b>\n\nDeclare paths first:\ne.g. <code>/batch src/app.py utils/helper.js</code>",
            [[InlineKeyboardButton("⭐ Saved Paths", callback_data="batch_saved_paths"),
              InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data == "upload_mirror":
        set_state(telegram_id, "awaiting_zip_mirror", {})
        await edit(
            "🗜️ <b>Mirror mode</b>\n\n⚠️ ZIP becomes exact repo state. Missing files will be deleted.\n\n📬 Send your ZIP now",
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data == "upload_update":
        set_state(telegram_id, "awaiting_zip_update", {})
        await edit(
            "🗜️ <b>Update mode</b>\n\nOnly adds &amp; modifies. Never deletes.\n\n📬 Send your ZIP now",
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data == "batch_saved_paths":
        session = get_active_session(telegram_id)
        if not session:
            return
        from database.db import get_saved_paths
        paths = get_saved_paths(telegram_id, session["github_username"], session["active_repo"])
        if not paths:
            await edit("⭐ No saved paths yet. Use /savedpaths to add some.",
                       [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
            return
        keyboard = [[InlineKeyboardButton(p, callback_data=f"batch_add_path_{p}")] for p in paths]
        keyboard.append([InlineKeyboardButton("✅ Done selecting", callback_data="batch_paths_done")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await edit("⭐ <b>Select paths for batch:</b>", keyboard)
        return

    if data.startswith("batch_add_path_"):
        path = data[len("batch_add_path_"):]
        state_info = get_state(telegram_id)
        sd = state_info.get("state_data", {})
        paths = sd.get("paths", [])
        if path not in paths:
            paths.append(path)
        set_state(telegram_id, "batch_declare_paths", {**sd, "paths": paths})
        await query.answer(f"✅ Added: {path}", show_alert=False)
        return

    if data == "batch_paths_done":
        state_info = get_state(telegram_id)
        sd = state_info.get("state_data", {})
        paths = sd.get("paths", [])
        if not paths:
            await query.answer("No paths selected!", show_alert=True)
            return
        set_state(telegram_id, "batch_collecting", {"paths": paths, "files": {}, "current_index": 0})
        path_list = "\n".join(f"{i+1}. <code>{h(p)}</code>" for i, p in enumerate(paths))
        await edit(
            f"✅ <b>{len(paths)} paths registered:</b>\n{path_list}\n\n📬 Now send files <b>IN ORDER</b>.",
            [[InlineKeyboardButton("❌ Cancel Batch", callback_data="cancel")]]
        )
        return

    if data == "batch_review":
        state_info = get_state(telegram_id)
        sd = state_info.get("state_data", {})
        files = sd.get("files", {})
        session = get_active_session(telegram_id)
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        new_f, modified_f, unchanged_f = [], [], []
        for path, content in files.items():
            try:
                existing = repo.get_contents(path, ref=branch)
                old = base64.b64decode(existing.content).decode("utf-8", errors="replace")
                (modified_f if old != content else unchanged_f).append(path)
            except Exception:
                new_f.append(path)
        set_state(telegram_id, "confirming_batch_commit", {**sd, "new_files": new_f, "modified_files": modified_f})
        text = f"🔄 <b>Changes — {h(session['active_repo'])}</b>\n\n"
        if new_f:
            text += "✨ <b>New:</b>\n" + "\n".join(f"  + <code>{h(f)}</code>" for f in new_f) + "\n\n"
        if modified_f:
            text += "🟡 <b>Modified:</b>\n" + "\n".join(f"  ~ <code>{h(f)}</code>" for f in modified_f) + "\n\n"
        if unchanged_f:
            text += f"⏭️ <b>Unchanged:</b> {len(unchanged_f)} (skipped)\n"
        await edit(text, [
            [InlineKeyboardButton("✏️ Write message", callback_data="commit_write"),
             InlineKeyboardButton("🤖 Auto-generate", callback_data="commit_auto")],
            [InlineKeyboardButton("✅ Commit", callback_data="confirm_batch_commit"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ])
        return

    if data == "mismatch_use_path":
        sd = get_state(telegram_id).get("state_data", {})
        from handlers.upload import process_single_file
        set_state(telegram_id, "awaiting_single_file", sd)
        await process_single_file(update, context, sd.get("path", ""), sd.get("file_id", ""))
        return

    if data == "mismatch_use_file":
        sd = get_state(telegram_id).get("state_data", {})
        sent_fn = sd.get("sent_filename", "")
        declared = sd.get("path", "")
        parent = "/".join(declared.split("/")[:-1])
        new_path = f"{parent}/{sent_fn}" if parent else sent_fn
        from handlers.upload import process_single_file
        set_state(telegram_id, "awaiting_single_file", sd)
        await process_single_file(update, context, new_path, sd.get("file_id", ""))
        return

    if data == "confirm_sensitive":
        sd = get_state(telegram_id).get("state_data", {})
        set_state(telegram_id, "confirming_single_commit", sd)
        from handlers.upload import show_diff_preview
        await show_diff_preview(query.message, sd.get("path", ""), "", 0, is_new=True)
        return

    # ── Commit flow ───────────────────────────────────────────────────────────

    if data == "commit_write":
        sd = get_state(telegram_id).get("state_data", {})
        set_state(telegram_id, "awaiting_commit_message", sd)
        await edit("💬 <b>Write your commit message:</b>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "commit_auto":
        sd = get_state(telegram_id).get("state_data", {})
        new_f = sd.get("new_files", [])
        mod_f = sd.get("modified_files", [])
        del_f = sd.get("deleted_files", [])
        path = sd.get("path", "")
        parts = []
        if path:
            parts.append(f"Updated {path.split('/')[-1]}")
        if new_f:
            parts.append(f"Added {', '.join(f.split('/')[-1] for f in new_f[:3])}")
        if mod_f:
            parts.append(f"Updated {', '.join(f.split('/')[-1] for f in mod_f[:3])}")
        if del_f:
            parts.append(f"Removed {', '.join(f.split('/')[-1] for f in del_f[:2])}")
        auto_msg = "; ".join(parts) if parts else "Updated files"
        await edit(
            f"🤖 <b>Suggested message:</b>\n\n\"{h(auto_msg)}\"",
            [[InlineKeyboardButton("✅ Use this", callback_data=f"use_msg_{auto_msg}"),
              InlineKeyboardButton("✏️ Edit it", callback_data="commit_write")],
             [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data == "commit_recent":
        session = get_active_session(telegram_id)
        if not session:
            return
        from database.db import get_commit_history
        history = get_commit_history(telegram_id, session["github_username"], session["active_repo"])
        if not history:
            await query.answer("No recent messages yet.", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(msg[:45], callback_data=f"use_msg_{msg}")] for msg in history]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await edit("📋 <b>Recent commit messages:</b>", keyboard)
        return

    if data == "commit_templates":
        session = get_active_session(telegram_id)
        if not session:
            return
        from database.db import get_templates
        templates = get_templates(telegram_id, session["github_username"], session["active_repo"])
        if not templates:
            await query.answer("No templates yet. Use /templates to add.", show_alert=True)
            return
        keyboard = [[InlineKeyboardButton(t["template"][:45], callback_data=f"use_template_{t['id']}")] for t in templates]
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await edit("📝 <b>Commit templates:</b>", keyboard)
        return

    if data.startswith("use_template_"):
        tmpl_id = data[len("use_template_"):]
        session = get_active_session(telegram_id)
        if not session:
            return
        from database.db import get_templates
        templates = get_templates(telegram_id, session["github_username"], session["active_repo"])
        tmpl = next((t["template"] for t in templates if str(t["id"]) == tmpl_id), None)
        if tmpl:
            sd = get_state(telegram_id).get("state_data", {})
            set_state(telegram_id, "awaiting_commit_message", sd)
            await edit(f"📝 <b>Complete the template:</b>\n\n<code>{h(tmpl)}</code>\n\nSend your full message:",
                       [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("use_msg_"):
        commit_msg = data[len("use_msg_"):]
        state_info = get_state(telegram_id)
        current_state = state_info.get("state", "")
        if "batch" in current_state or "confirming_batch" in current_state:
            from handlers.upload import do_commit_batch
            await do_commit_batch(query.message, telegram_id, commit_msg)
        elif "zip" in current_state or "confirming_zip" in current_state:
            from handlers.upload import do_commit_zip
            await do_commit_zip(query.message, telegram_id, commit_msg)
        else:
            from handlers.upload import do_commit_single
            await do_commit_single(query.message, telegram_id, commit_msg)
        return

    if data == "confirm_batch_commit":
        sd = get_state(telegram_id).get("state_data", {})
        set_state(telegram_id, "confirming_batch_commit", sd)
        await edit("💬 <b>Commit message?</b>",
                   [[InlineKeyboardButton("✏️ Write", callback_data="commit_write"),
                     InlineKeyboardButton("🤖 Auto-generate", callback_data="commit_auto")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "confirm_zip_commit":
        sd = get_state(telegram_id).get("state_data", {})
        set_state(telegram_id, "confirming_zip_commit", sd)
        await edit("💬 <b>Commit message?</b>",
                   [[InlineKeyboardButton("✏️ Write", callback_data="commit_write"),
                     InlineKeyboardButton("🤖 Auto-generate", callback_data="commit_auto")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "preview_tree":
        sd = get_state(telegram_id).get("state_data", {})
        session = get_active_session(telegram_id)
        from utils.github_helper import get_github_client, build_tree
        from github import GithubException
        new_f = set(sd.get("new_files", []))
        mod_f = set(sd.get("modified_files", []))
        del_f = set(sd.get("deleted_files", []))
        path = sd.get("path", "")
        if path:
            (new_f if sd.get("is_new") else mod_f).add(path)
        gh = get_github_client(telegram_id)
        branch = session.get("active_branch", "main")
        try:
            repo = gh.get_repo(session["active_repo"])
            contents = repo.get_contents("", ref=branch)
            if not isinstance(contents, list):
                contents = [contents]
            tree = build_tree(contents, changed_files=mod_f, new_files=new_f, deleted_files=del_f)
        except Exception:
            tree = "Unable to generate tree"
        await edit(
            f"👁 <b>Preview — after commit</b>\n<code>{h(session['active_repo'])}</code> @ <code>{h(branch)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n<pre>{h(tree)}</pre>\n\n✨ New  🟡 Modified  🗑️ Deleted",
            [[InlineKeyboardButton("✅ Looks good, commit", callback_data="confirm_zip_commit"),
              InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    # ── Download ──────────────────────────────────────────────────────────────

    if data == "download_menu":
        session = get_active_session(telegram_id)
        keyboard = []
        if session and session.get("active_repo"):
            keyboard.append([InlineKeyboardButton(
                f"⬇️ {session['active_repo'].split('/')[-1]}",
                callback_data=f"dl_{session['active_repo']}"
            )])
        keyboard.append([InlineKeyboardButton("📦 My repos", callback_data="repos"),
                         InlineKeyboardButton("🔗 By URL/name", callback_data="dl_by_url")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await edit("⬇️ <b>Download</b>\n\nWhich repo?", keyboard)
        return

    if data == "dl_by_url":
        set_state(telegram_id, "awaiting_download_target", {})
        await edit("🔗 <b>Download by URL or name</b>\n\nSend the repo URL or <code>user/repo</code>:",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("dl_"):
        repo_name = data[3:]
        from handlers.extras import do_download
        await do_download(query.message, telegram_id, repo_name, context)
        return

    # ── Branches ──────────────────────────────────────────────────────────────

    if data == "branches":
        from handlers.branches import show_branches
        await show_branches(query, telegram_id, send_new=False)
        return

    if data == "new_branch":
        set_state(telegram_id, "awaiting_new_branch", {})
        await edit("🌿 <b>New Branch</b>\n\nType the branch name:",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("switch_branch_"):
        branch = data[len("switch_branch_"):]
        from handlers.branches import do_switch_branch
        await do_switch_branch(query.message, telegram_id, branch)
        return

    if data.startswith("merge_branch_"):
        branch = data[len("merge_branch_"):]
        session = get_active_session(telegram_id)
        current = session.get("active_branch", "main") if session else "main"
        await edit(
            f"🔀 <b>Merge branch?</b>\n\nFrom: <code>{h(branch)}</code>\nInto: <code>{h(current)}</code>",
            [[InlineKeyboardButton("✅ Merge", callback_data=f"confirm_merge_{branch}"),
              InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data.startswith("confirm_merge_"):
        branch = data[len("confirm_merge_"):]
        from handlers.branches import do_merge
        await do_merge(query.message, telegram_id, branch)
        return

    if data.startswith("delete_branch_"):
        branch = data[len("delete_branch_"):]
        await edit(
            f"🗑️ <b>Delete branch</b> <code>{h(branch)}</code>?\n\nThis cannot be undone.",
            [[InlineKeyboardButton("✅ Yes, delete", callback_data=f"confirm_delete_branch_{branch}"),
              InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    if data.startswith("confirm_delete_branch_"):
        branch = data[len("confirm_delete_branch_"):]
        from handlers.branches import delete_branch
        await delete_branch(query.message, telegram_id, branch)
        return

    if data.startswith("protect_branch_"):
        branch = data[len("protect_branch_"):]
        from handlers.branches import protect_branch
        await protect_branch(query.message, telegram_id, branch)
        return

    if data == "diff_menu":
        session = get_active_session(telegram_id)
        set_state(telegram_id, "awaiting_diff_branches", {})
        current = session.get("active_branch", "main") if session else "main"
        await edit(
            f"🔀 <b>Compare branches</b>\n\nType: <code>branch1 branch2</code>\nCurrent: <code>{h(current)}</code>",
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
        )
        return

    # ── Log, History ──────────────────────────────────────────────────────────

    if data == "log":
        from handlers.history import show_log
        await show_log(query, telegram_id, send_new=False)
        return

    if data == "confirm_undo":
        from handlers.history import cmd_undo
        session = get_active_session(telegram_id)
        if not session or not session.get("active_repo"):
            await edit("❌ No active repo.")
            return
        from utils.github_helper import get_github_client, format_time_ago
        from github import GithubException
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(session["active_repo"])
            branch = session.get("active_branch", "main")
            commits = list(repo.get_commits(sha=branch))
            if not commits:
                await edit("❌ No commits to undo.")
                return
            last = commits[0]
            sha_short = last.sha[:7]
            msg = last.commit.message.split("\n")[0][:40]
            when = format_time_ago(last.commit.author.date)
            set_state(telegram_id, "confirming_undo", {
                "sha": last.sha,
                "parent_sha": commits[1].sha if len(commits) > 1 else None
            })
            await edit(
                f"↩️ <b>Undo last commit?</b>\n\n<code>{h(sha_short)}</code> — \"{h(msg)}\"\n{h(when)}\n\n⚠️ This will reverse the commit.",
                [[InlineKeyboardButton("✅ Yes, undo", callback_data="confirm_undo_action"),
                  InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
            )
        except GithubException as e:
            await edit(get_error_message(e.status))
        return

    if data == "confirm_undo_action":
        from handlers.history import do_undo
        await do_undo(query.message, telegram_id)
        return

    if data.startswith("view_commit_"):
        sha = data[len("view_commit_"):]
        from handlers.history import view_commit
        await view_commit(query.message, telegram_id, sha)
        return

    if data.startswith("confirm_rollback_"):
        rest = data[len("confirm_rollback_"):]
        parts = rest.split("_", 1)
        sha = parts[0]
        sha_short = parts[1] if len(parts) > 1 else sha[:7]
        from handlers.history import confirm_rollback
        await confirm_rollback(query.message, telegram_id, sha, sha_short)
        return

    if data.startswith("do_rollback_"):
        sha = data[len("do_rollback_"):]
        from handlers.history import do_rollback
        await do_rollback(query.message, telegram_id, sha)
        return

    # ── Stats, Issues, Releases ───────────────────────────────────────────────

    if data == "stats":
        from handlers.extras import _send_stats
        await _send_stats(query.message, telegram_id)
        return

    if data == "traffic":
        from handlers.extras import _send_traffic
        await _send_traffic(query.message, telegram_id)
        return

    if data == "stargazers":
        from handlers.extras import _send_stargazers
        await _send_stargazers(query.message, telegram_id)
        return

    if data == "contributors":
        from handlers.extras import _send_contributors
        await _send_contributors(query.message, telegram_id)
        return

    if data == "issues":
        from handlers.extras import _send_issues
        await _send_issues(query.message, telegram_id)
        return

    if data == "releases":
        from handlers.extras import _send_releases
        await _send_releases(query.message, telegram_id)
        return

    if data == "create_issue":
        set_state(telegram_id, "awaiting_issue_title", {})
        await edit("📝 <b>New Issue</b>\n\nType the issue title:",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("close_issue_"):
        issue_num = int(data[len("close_issue_"):])
        session = get_active_session(telegram_id)
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(session["active_repo"])
            repo.get_issue(issue_num).edit(state="closed")
            await edit(f"✅ <b>Issue #{issue_num} closed.</b>",
                       [[InlineKeyboardButton("📝 All Issues", callback_data="issues"),
                         InlineKeyboardButton("🏠 Home", callback_data="home")]])
        except GithubException as e:
            await edit(get_error_message(e.status))
        return

    if data == "create_release":
        set_state(telegram_id, "awaiting_release_tag", {})
        await edit("🚀 <b>New Release</b>\n\nType the version tag:\ne.g. <code>v1.0.0</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("delete_release_"):
        release_id = int(data[len("delete_release_"):])
        session = get_active_session(telegram_id)
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(session["active_repo"])
            repo.get_release(release_id).delete_release()
            await edit("🗑️ <b>Release deleted.</b>",
                       [[InlineKeyboardButton("🚀 Releases", callback_data="releases"),
                         InlineKeyboardButton("🏠 Home", callback_data="home")]])
        except GithubException as e:
            await edit(get_error_message(e.status))
        return

    if data.startswith("delete_gist_"):
        gist_id = data[len("delete_gist_"):]
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        try:
            gh.get_gist(gist_id).delete()
            await edit("🗑️ Gist deleted.", [[InlineKeyboardButton("🏠 Home", callback_data="home")]])
        except GithubException as e:
            await edit(get_error_message(e.status))
        return

    # ── Settings ──────────────────────────────────────────────────────────────

    if data == "settings_back":
        from handlers.settings import show_settings
        await show_settings(query, telegram_id, send_new=False)
        return

    if data == "settings_theme":
        await edit("🎨 <b>Choose theme:</b>",
                   [[InlineKeyboardButton("🌑 Dark", callback_data="set_theme_dark"),
                     InlineKeyboardButton("☀️ Light", callback_data="set_theme_light"),
                     InlineKeyboardButton("🌈 Monokai", callback_data="set_theme_monokai")],
                    [InlineKeyboardButton("💜 Dracula", callback_data="set_theme_dracula"),
                     InlineKeyboardButton("🤍 GitHub", callback_data="set_theme_github"),
                     InlineKeyboardButton("⬅️ Back", callback_data="settings_back")]])
        return

    if data.startswith("set_theme_"):
        theme = data[len("set_theme_"):]
        from database.db import update_settings
        update_settings(telegram_id, theme=theme)
        await edit(f"✅ Theme set to <b>{h(theme.title())}</b>",
                   [[InlineKeyboardButton("⬅️ Settings", callback_data="settings_back")]])
        return

    if data == "settings_time":
        await edit("🕐 <b>Time format:</b>",
                   [[InlineKeyboardButton("🕐 12hr", callback_data="set_time_12hr"),
                     InlineKeyboardButton("🕑 24hr", callback_data="set_time_24hr"),
                     InlineKeyboardButton("⬅️ Back", callback_data="settings_back")]])
        return

    if data.startswith("set_time_"):
        fmt = data[len("set_time_"):]
        from database.db import update_settings
        update_settings(telegram_id, time_format=fmt)
        await edit(f"✅ Time format set to <b>{h(fmt)}</b>",
                   [[InlineKeyboardButton("⬅️ Settings", callback_data="settings_back")]])
        return

    if data == "settings_date":
        await edit("📅 <b>Date format:</b>",
                   [[InlineKeyboardButton("DD/MM/YYYY", callback_data="set_date_DDMMYYYY"),
                     InlineKeyboardButton("MM/DD/YYYY", callback_data="set_date_MMDDYYYY"),
                     InlineKeyboardButton("YYYY-MM-DD", callback_data="set_date_YYYYMMDD")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="settings_back")]])
        return

    if data.startswith("set_date_"):
        fmt_map = {"DDMMYYYY": "DD/MM/YYYY", "MMDDYYYY": "MM/DD/YYYY", "YYYYMMDD": "YYYY-MM-DD"}
        fmt = fmt_map.get(data[len("set_date_"):], "DD/MM/YYYY")
        from database.db import update_settings
        update_settings(telegram_id, date_format=fmt)
        await edit(f"✅ Date format set to <b>{h(fmt)}</b>",
                   [[InlineKeyboardButton("⬅️ Settings", callback_data="settings_back")]])
        return

    if data == "settings_timezone":
        set_state(telegram_id, "awaiting_timezone", {})
        await edit("🌐 <b>Timezone</b>\n\nType your timezone:\ne.g. <code>Africa/Nairobi</code> or <code>UTC+3</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="settings_back")]])
        return

    if data == "settings_reset":
        await edit("↩️ <b>Reset all settings to default?</b>",
                   [[InlineKeyboardButton("✅ Yes, reset", callback_data="confirm_settings_reset"),
                     InlineKeyboardButton("❌ Cancel", callback_data="settings_back")]])
        return

    if data == "confirm_settings_reset":
        from database.db import update_settings
        update_settings(telegram_id, theme="dark", time_format="24hr", date_format="DD/MM/YYYY", timezone="UTC")
        await edit("✅ <b>Settings reset to defaults.</b>",
                   [[InlineKeyboardButton("⚙️ Settings", callback_data="settings_back")]])
        return

    if data == "privatemsg_menu":
        from handlers.settings import show_privatemsg
        await show_privatemsg(query, telegram_id, send_new=False)
        return

    if data == "pm_edit_full":
        set_state(telegram_id, "awaiting_pm_full_message", {})
        await edit("✏️ <b>Send your new private message:</b>\nVariables: <code>{owner}</code> <code>{botname}</code> <code>{date}</code> <code>{link}</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "pm_edit_owner":
        set_state(telegram_id, "awaiting_pm_owner", {})
        await edit("👤 <b>Send new owner username:</b>\ne.g. <code>@yourhandle</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "pm_edit_link":
        set_state(telegram_id, "awaiting_pm_link", {})
        await edit("🔗 <b>Send the URL to include:</b>",
                   [[InlineKeyboardButton("🗑️ Remove link", callback_data="pm_remove_link"),
                     InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "pm_remove_link":
        from database.db import update_settings
        update_settings(telegram_id, private_message_link=None)
        await edit("✅ Link removed.", [[InlineKeyboardButton("⬅️ Back", callback_data="privatemsg_menu")]])
        return

    if data == "pm_preview":
        from database.db import get_settings
        from datetime import datetime
        settings = get_settings(telegram_id)
        custom = settings.get("private_message")
        owner = settings.get("private_message_owner", "@GitroHubBot")
        link = settings.get("private_message_link", "")
        if custom:
            msg = (custom.replace("{owner}", owner or "")
                         .replace("{botname}", "GitroHub")
                         .replace("{date}", datetime.now().strftime("%b %d %Y"))
                         .replace("{link}", link or ""))
        else:
            msg = f"🔒 GitroHub — Private Bot\n\nOwner: {owner}\n\nThis bot is privately owned."
        await edit(f"👁 <b>Preview:</b>\n\n{h(msg)}",
                   [[InlineKeyboardButton("⬅️ Back", callback_data="privatemsg_menu")]])
        return

    if data == "pm_reset":
        from database.db import update_settings
        update_settings(telegram_id, private_message=None, private_message_owner=None, private_message_link=None)
        await edit("✅ Private message reset to default.",
                   [[InlineKeyboardButton("⬅️ Back", callback_data="privatemsg_menu")]])
        return

    if data == "add_alias":
        set_state(telegram_id, "awaiting_alias_shortcut", {})
        await edit("⌨️ <b>New Alias</b>\n\nType the shortcut command:\ne.g. <code>/up</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("remove_alias_"):
        alias = data[len("remove_alias_"):]
        from database.db import remove_alias
        remove_alias(telegram_id, alias)
        from handlers.settings import show_aliases
        await show_aliases(query, telegram_id, send_new=False)
        return

    if data == "add_template":
        set_state(telegram_id, "awaiting_template_text", {})
        await edit("📝 <b>New Commit Template</b>\n\nType your template:\ne.g. <code>feat: {description}</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("remove_template_"):
        tmpl_id = int(data[len("remove_template_"):])
        from database.db import remove_template
        remove_template(tmpl_id, telegram_id)
        from handlers.settings import show_templates
        await show_templates(query, telegram_id, send_new=False)
        return

    if data == "add_saved_path":
        set_state(telegram_id, "awaiting_save_path", {})
        await edit("⭐ <b>Save a path</b>\n\nType the file path:\ne.g. <code>src/app.py</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data.startswith("remove_saved_"):
        path = data[len("remove_saved_"):]
        session = get_active_session(telegram_id)
        if session:
            from database.db import remove_saved_path
            remove_saved_path(telegram_id, session["github_username"], session["active_repo"], path)
        from handlers.settings import show_savedpaths
        await show_savedpaths(query, telegram_id, send_new=False)
        return

    if data.startswith("upload_saved_"):
        path = data[len("upload_saved_"):]
        set_state(telegram_id, "awaiting_single_file", {"path": path})
        await edit(f"📬 <b>Ready — send your file</b>\n\nWill upload to: <code>{h(path)}</code>",
                   [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data == "aliases_back":
        from handlers.settings import show_aliases
        await show_aliases(query, telegram_id, send_new=False)
        return

    if data == "templates_back":
        from handlers.settings import show_templates
        await show_templates(query, telegram_id, send_new=False)
        return

    if data == "savedpaths_back":
        from handlers.settings import show_savedpaths
        await show_savedpaths(query, telegram_id, send_new=False)
        return

    # ── repo vis flow ─────────────────────────────────────────────────────────

    if data in ("repo_vis_public", "repo_vis_private"):
        vis = data.split("_")[-1]
        sd = get_state(telegram_id).get("state_data", {})
        repo_name = sd.get("name", "")
        set_state(telegram_id, "creating_repo", {**sd, "private": (vis == "private"), "step": "readme"})
        await edit(f"📄 <b>Add README to</b> <code>{h(repo_name)}</code>?",
                   [[InlineKeyboardButton("✅ Yes", callback_data="repo_readme_yes"),
                     InlineKeyboardButton("❌ Skip", callback_data="repo_readme_no")],
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        return

    if data in ("repo_readme_yes", "repo_readme_no"):
        want_readme = data == "repo_readme_yes"
        sd = get_state(telegram_id).get("state_data", {})
        set_state(telegram_id, "creating_repo", {**sd, "readme": want_readme, "step": "gitignore"})
        await edit("🙈 <b>Add .gitignore template?</b>",
                   [[InlineKeyboardButton("🐍 Python", callback_data="repo_gi_Python"),
                     InlineKeyboardButton("⚡ Node", callback_data="repo_gi_Node"),
                     InlineKeyboardButton("☕ Java", callback_data="repo_gi_Java")],
                    [InlineKeyboardButton("🦫 Go", callback_data="repo_gi_Go"),
                     InlineKeyboardButton("💎 Ruby", callback_data="repo_gi_Ruby"),
                     InlineKeyboardButton("❌ None", callback_data="repo_gi_None")]])
        return

    if data.startswith("repo_gi_"):
        gi = data[len("repo_gi_"):]
        sd = get_state(telegram_id).get("state_data", {})
        set_state(telegram_id, "creating_repo", {**sd, "gitignore": gi if gi != "None" else None, "step": "license"})
        await edit("⚖️ <b>Add a license?</b>",
                   [[InlineKeyboardButton("MIT", callback_data="repo_lic_mit"),
                     InlineKeyboardButton("Apache 2.0", callback_data="repo_lic_apache-2.0"),
                     InlineKeyboardButton("GPL 3.0", callback_data="repo_lic_gpl-3.0")],
                    [InlineKeyboardButton("BSD", callback_data="repo_lic_bsd-2-clause"),
                     InlineKeyboardButton("❌ None", callback_data="repo_lic_None")]])
        return

    if data.startswith("repo_lic_"):
        lic = data[len("repo_lic_"):]
        sd = get_state(telegram_id).get("state_data", {})
        from utils.github_helper import get_github_client
        from github import GithubException
        gh = get_github_client(telegram_id)
        repo_name = sd.get("name", "new-repo")
        is_private = sd.get("private", True)
        gi = sd.get("gitignore")
        want_readme = sd.get("readme", False)
        try:
            user = gh.get_user()
            kwargs = {"private": is_private, "auto_init": want_readme}
            if gi:
                kwargs["gitignore_template"] = gi
            if lic and lic != "None":
                kwargs["license_template"] = lic
            repo = user.create_repo(repo_name, **kwargs)
            update_session(telegram_id, active_repo=repo.full_name, active_branch=repo.default_branch)
            add_to_recent(telegram_id, repo.full_name)
            clear_state(telegram_id)
            await edit(
                f"✅ <b>{h(repo_name)}</b> created!\n\n"
                f"{'🔒 Private' if is_private else '🌍 Public'}  •  "
                f"README: {'✅' if want_readme else '❌'}  •  .gitignore: {h(gi or 'None')}",
                [[InlineKeyboardButton("📂 Open Project", callback_data="browse"),
                  InlineKeyboardButton("⬆️ Upload Files", callback_data="upload_menu")]]
            )
        except GithubException as e:
            clear_state(telegram_id)
            await edit(get_error_message(e.status))
        return

    # ── Help ──────────────────────────────────────────────────────────────────

    if data == "help_back":
        from handlers.core import _help_keyboard
        await edit("❓ <b>GitroHub — Help</b>\n\nSelect a category:", _help_keyboard().inline_keyboard)
        return

    if data in handlers_core_HELP_SECTIONS:
        from handlers.core import HELP_SECTIONS
        await edit(HELP_SECTIONS[data],
                   [[InlineKeyboardButton("⬅️ Back to Help", callback_data="help_back"),
                     InlineKeyboardButton("🏠 Home", callback_data="home")]])
        return

    # ── Fallthrough ───────────────────────────────────────────────────────────
    logger.info(f"Unhandled callback: {data}")
    await query.answer("This button isn't ready yet.", show_alert=False)


# Known help section keys
handlers_core_HELP_SECTIONS = {
    "help_repos", "help_files", "help_upload", "help_download",
    "help_branches", "help_history", "help_issues", "help_releases",
    "help_stats", "help_accounts", "help_settings", "help_safety",
}


# ── Text message handler ──────────────────────────────────────────────────────

async def handle_text_message(update: Update, context):
    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    if not is_admin(update):
        return

    from database.db import (
        add_alias, add_saved_path, add_template, clear_state,
        get_active_session, get_aliases, get_state, set_state, update_settings,
    )
    from utils.github_helper import h

    state_info = get_state(telegram_id)
    state = state_info.get("state", "idle")
    sd = state_info.get("state_data", {})
    session = get_active_session(telegram_id)

    KB_CANCEL = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])

    # Commit message states
    if state == "awaiting_commit_message":
        if "batch" in state or sd.get("files"):
            from handlers.upload import do_commit_batch
            await do_commit_batch(update.message, telegram_id, text)
        elif "zip" in state or sd.get("file_map"):
            from handlers.upload import do_commit_zip
            await do_commit_zip(update.message, telegram_id, text)
        else:
            from handlers.upload import do_commit_single
            await do_commit_single(update.message, telegram_id, text)
        return

    if state == "confirming_single_commit":
        from handlers.upload import do_commit_single
        await do_commit_single(update.message, telegram_id, text)
        return

    if state == "confirming_batch_commit":
        from handlers.upload import do_commit_batch
        await do_commit_batch(update.message, telegram_id, text)
        return

    if state == "confirming_zip_commit":
        from handlers.upload import do_commit_zip
        await do_commit_zip(update.message, telegram_id, text)
        return

    if state == "awaiting_search":
        from handlers.files import do_search
        clear_state(telegram_id)
        await do_search(update.message, telegram_id, text)
        return

    if state == "creating_repo" and sd.get("step") == "name":
        from handlers.repos import ask_visibility
        set_state(telegram_id, "creating_repo", {"name": text, "step": "visibility"})
        await ask_visibility(update.message, text)
        return

    if state == "deleting_repo_step1":
        repo = sd.get("repo", "")
        if text == repo.split("/")[-1] or text == repo:
            set_state(telegram_id, "deleting_repo_step2", sd)
            await update.message.reply_text(
                f"✅ <b>Step 1 confirmed</b>\n\n<b>Step 2/3</b> — Check your GitHub email\n📧 Enter the 6-digit code:",
                parse_mode="HTML", reply_markup=KB_CANCEL
            )
        else:
            await update.message.reply_text(
                f"❌ Wrong name. Expected: <code>{h(repo.split('/')[-1])}</code>\n\nTry again:",
                parse_mode="HTML", reply_markup=KB_CANCEL
            )
        return

    if state == "deleting_repo_step2":
        set_state(telegram_id, "deleting_repo_step3", sd)
        await update.message.reply_text(
            "✅ <b>Step 2 confirmed</b>\n\n<b>Step 3/3</b> — Open your GitHub mobile app\n📱 Tap <b>Approve</b> on the notification",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ I approved it", callback_data="do_delete_repo"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )
        return

    if state == "awaiting_rename_input":
        if session and session.get("active_repo"):
            set_state(telegram_id, "confirming_rename", {"old": session["active_repo"], "new": text})
            await update.message.reply_text(
                f"✏️ Rename <code>{h(session['active_repo'])}</code> → <code>{h(text)}</code>?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Rename", callback_data=f"confirm_rename_{text}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]])
            )
        return

    if state == "awaiting_topics":
        if session and session.get("active_repo"):
            from utils.github_helper import get_github_client
            from github import GithubException
            gh = get_github_client(telegram_id)
            topics = [t.strip().lower() for t in text.split(",") if t.strip()]
            try:
                repo = gh.get_repo(session["active_repo"])
                repo.replace_topics(topics)
                clear_state(telegram_id)
                await update.message.reply_text(
                    f"✅ <b>Topics updated!</b>\n<code>{h(', '.join(topics))}</code>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="repo_settings")]])
                )
            except GithubException as e:
                from utils.github_helper import get_error_message
                await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")
        return

    if state == "awaiting_transfer_username":
        if session and session.get("active_repo"):
            set_state(telegram_id, "deleting_repo_step1", {"repo": session["active_repo"], "transfer_to": text})
            await update.message.reply_text(
                f"⚠️ <b>Transfer {h(session['active_repo'])} to {h(text)}?</b>\n\nRequires 3-step verification.\n\n<b>Step 1/3</b> — Type the repo name:",
                parse_mode="HTML", reply_markup=KB_CANCEL
            )
        return

    if state == "awaiting_new_branch":
        from handlers.branches import create_branch
        clear_state(telegram_id)
        await create_branch(update.message, telegram_id, text)
        return

    if state == "awaiting_diff_branches":
        parts = text.split()
        if len(parts) >= 2:
            from handlers.branches import cmd_diff
            clear_state(telegram_id)
            context.args = [parts[0], parts[1]]
            await cmd_diff(update, context)
        else:
            await update.message.reply_text("❌ Please type two branch names separated by a space.\ne.g. <code>main dev</code>", parse_mode="HTML")
        return

    if state == "awaiting_download_target":
        from handlers.extras import do_download
        clear_state(telegram_id)
        await do_download(update.message, telegram_id, text, context)
        return

    if state == "awaiting_issue_title":
        if session and session.get("active_repo"):
            from utils.github_helper import get_github_client
            from github import GithubException
            gh = get_github_client(telegram_id)
            try:
                repo = gh.get_repo(session["active_repo"])
                issue = repo.create_issue(title=text)
                clear_state(telegram_id)
                await update.message.reply_text(
                    f"✅ <b>Issue created!</b>\n#{issue.number} {h(text)}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔗 View", url=issue.html_url),
                        InlineKeyboardButton("📝 All Issues", callback_data="issues"),
                    ]])
                )
            except GithubException as e:
                from utils.github_helper import get_error_message
                await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")
        return

    if state == "awaiting_release_tag":
        set_state(telegram_id, "awaiting_release_title", {"tag": text})
        await update.message.reply_text(
            f"📝 <b>Release title for</b> <code>{h(text)}</code>?",
            parse_mode="HTML", reply_markup=KB_CANCEL
        )
        return

    if state == "awaiting_release_title":
        tag = sd.get("tag", "v1.0.0")
        if session and session.get("active_repo"):
            from utils.github_helper import get_github_client
            from github import GithubException
            gh = get_github_client(telegram_id)
            try:
                repo = gh.get_repo(session["active_repo"])
                release = repo.create_git_release(tag=tag, name=text, message=f"Release {tag}", draft=False, prerelease=False)
                clear_state(telegram_id)
                await update.message.reply_text(
                    f"🚀 <b>Release {h(tag)} published!</b>\n{h(text)}",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔗 View", url=release.html_url),
                        InlineKeyboardButton("🚀 Releases", callback_data="releases"),
                    ]])
                )
            except GithubException as e:
                from utils.github_helper import get_error_message
                await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")
        return

    if state == "awaiting_timezone":
        update_settings(telegram_id, timezone=text)
        clear_state(telegram_id)
        await update.message.reply_text(
            f"✅ <b>Timezone set to</b> <code>{h(text)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", callback_data="settings_back")]])
        )
        return

    if state == "awaiting_pm_full_message":
        update_settings(telegram_id, private_message=text)
        clear_state(telegram_id)
        await update.message.reply_text("✅ <b>Private message updated.</b>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("👁 Preview", callback_data="pm_preview"),
                                                InlineKeyboardButton("⬅️ Back", callback_data="privatemsg_menu")]]))
        return

    if state == "awaiting_pm_owner":
        update_settings(telegram_id, private_message_owner=text)
        clear_state(telegram_id)
        await update.message.reply_text(f"✅ <b>Owner set to</b> <code>{h(text)}</code>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="privatemsg_menu")]]))
        return

    if state == "awaiting_pm_link":
        update_settings(telegram_id, private_message_link=text)
        clear_state(telegram_id)
        await update.message.reply_text(f"✅ <b>Link set to</b> <code>{h(text)}</code>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="privatemsg_menu")]]))
        return

    if state == "awaiting_alias_shortcut":
        set_state(telegram_id, "awaiting_alias_command", {"alias": text})
        await update.message.reply_text(
            f"✅ Shortcut: <code>{h(text)}</code>\n\nNow type the full command it maps to:\ne.g. <code>/upload src/app.py</code>",
            parse_mode="HTML", reply_markup=KB_CANCEL
        )
        return

    if state == "awaiting_alias_command":
        alias = sd.get("alias", "")
        add_alias(telegram_id, alias, text)
        clear_state(telegram_id)
        await update.message.reply_text(
            f"✅ <b>Alias saved!</b>\n<code>{h(alias)}</code> → <code>{h(text)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⌨️ All Aliases", callback_data="aliases_back")]])
        )
        return

    if state == "awaiting_template_text":
        if session and session.get("active_repo"):
            add_template(telegram_id, session["github_username"], session["active_repo"], text)
            clear_state(telegram_id)
            await update.message.reply_text(
                f"✅ <b>Template saved!</b>\n<code>{h(text)}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Templates", callback_data="templates_back")]])
            )
        return

    if state == "awaiting_save_path":
        if session and session.get("active_repo"):
            from utils.github_helper import sanitize_path
            clean = sanitize_path(text)
            add_saved_path(telegram_id, session["github_username"], session["active_repo"], clean)
            clear_state(telegram_id)
            await update.message.reply_text(
                f"✅ <b>Path saved!</b>\n<code>{h(clean)}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⭐ Saved Paths", callback_data="savedpaths_back")]])
            )
        return

    # Check aliases
    aliases = get_aliases(telegram_id)
    for alias_row in aliases:
        if text == alias_row["alias"] or text.startswith(alias_row["alias"] + " "):
            await update.message.reply_text(
                f"⚡ Alias: <code>{h(alias_row['alias'])}</code> → <code>{h(alias_row['command'])}</code>",
                parse_mode="HTML"
            )
            return


# ── Webhook & startup ─────────────────────────────────────────────────────────

async def setup_webhook(app):
    await app.bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook",
        allowed_updates=["message", "callback_query"]
    )
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}/webhook")


async def main():
    from database.db import init_db
    from handlers.core import setup_commands
    from handlers.auth import cmd_login, cmd_logout, cmd_accounts, cmd_whoami, cmd_switchaccount
    from handlers.core import cmd_start, cmd_ping, cmd_status, cmd_version, cmd_help, cmd_cancel
    from handlers.repos import cmd_repos, cmd_projects, cmd_create, cmd_use
    from handlers.files import cmd_browse, cmd_read, cmd_edit, cmd_delete_file, cmd_search, cmd_move
    from handlers.upload import cmd_upload, cmd_batch, cmd_mirror, cmd_update, handle_incoming_file
    from handlers.branches import cmd_branch, cmd_switch, cmd_merge, cmd_diff
    from handlers.history import cmd_log, cmd_undo, cmd_rollback
    from handlers.extras import (
        cmd_stats, cmd_profile, cmd_download, cmd_clone,
        cmd_star, cmd_unstar, cmd_stars, cmd_issues,
        cmd_releases, cmd_traffic, cmd_contributors, cmd_gists,
    )
    from handlers.settings import (
        cmd_settings, cmd_privatemsg, cmd_savedpaths, cmd_aliases, cmd_templates,
    )

    init_db()
    app = Application.builder().token(TOKEN).build()

    # Register global error handler
    app.add_error_handler(error_handler)

    commands = [
        ("start", cmd_start, False),
        ("login", cmd_login, True),
        ("logout", cmd_logout, True),
        ("accounts", cmd_accounts, True),
        ("switchaccount", cmd_switchaccount, True),
        ("whoami", cmd_whoami, True),
        ("status", cmd_status, True),
        ("ping", cmd_ping, True),
        ("version", cmd_version, True),
        ("help", cmd_help, True),
        ("cancel", cmd_cancel, True),
        ("repos", cmd_repos, True),
        ("projects", cmd_projects, True),
        ("create", cmd_create, True),
        ("use", cmd_use, True),
        ("browse", cmd_browse, True),
        ("read", cmd_read, True),
        ("edit", cmd_edit, True),
        ("delete", cmd_delete_file, True),
        ("search", cmd_search, True),
        ("move", cmd_move, True),
        ("upload", cmd_upload, True),
        ("batch", cmd_batch, True),
        ("mirror", cmd_mirror, True),
        ("update", cmd_update, True),
        ("branch", cmd_branch, True),
        ("switch", cmd_switch, True),
        ("merge", cmd_merge, True),
        ("diff", cmd_diff, True),
        ("log", cmd_log, True),
        ("undo", cmd_undo, True),
        ("rollback", cmd_rollback, True),
        ("stats", cmd_stats, True),
        ("profile", cmd_profile, True),
        ("download", cmd_download, True),
        ("clone", cmd_clone, True),
        ("star", cmd_star, True),
        ("unstar", cmd_unstar, True),
        ("stars", cmd_stars, True),
        ("issues", cmd_issues, True),
        ("releases", cmd_releases, True),
        ("traffic", cmd_traffic, True),
        ("contributors", cmd_contributors, True),
        ("gists", cmd_gists, True),
        ("settings", cmd_settings, True),
        ("privatemsg", cmd_privatemsg, True),
        ("savedpaths", cmd_savedpaths, True),
        ("aliases", cmd_aliases, True),
        ("templates", cmd_templates, True),
    ]

    for cmd_name, handler, protect in commands:
        h_func = admin_only(handler) if protect else handler
        app.add_handler(CommandHandler(cmd_name, h_func))

    app.add_handler(MessageHandler(filters.Document.ALL, admin_only(handle_incoming_file)))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    await app.initialize()
    await setup_commands(app.bot)

    if WEBHOOK_URL:
        await setup_webhook(app)

        async def webhook_handler(request):
            data = await request.json()
            update = Update.de_json(data, app.bot)
            await app.process_update(update)
            return web.Response(text="OK")

        async def oauth_callback(request):
            from handlers.auth import handle_oauth_callback
            code = request.rel_url.query.get("code")
            state = request.rel_url.query.get("state")
            error = request.rel_url.query.get("error")
            html = lambda msg, ok=True: web.Response(content_type="text/html", text=f"""
            <html><body style="background:#1a1a2e;color:#e0e0e0;font-family:sans-serif;text-align:center;padding:60px">
            <h2>{'✅' if ok else '❌'} {msg}</h2>
            {'<p>Go back to Telegram to continue. 🚀</p><script>setTimeout(()=>window.close(),3000)</script>' if ok else '<p>Go back to Telegram and try /login again.</p>'}
            </body></html>""")
            if error or not code or not state:
                return html("Authorization Failed", ok=False)
            success = await handle_oauth_callback(code, state, app.bot)
            return html("Connected!" if success else "Connection Failed", ok=success)

        web_app = web.Application()
        web_app.router.add_post("/webhook", webhook_handler)
        web_app.router.add_get("/auth/github/callback", oauth_callback)
        web_app.router.add_get("/callback", oauth_callback)  # legacy fallback
        web_app.router.add_get("/", lambda r: web.Response(
            content_type="text/html",
            text="<html><body style='background:#1a1a2e;color:#e0e0e0;font-family:sans-serif;text-align:center;padding:60px'><h2>🤖 GitroHub v1.3</h2><p>Running ✅</p></body></html>"
        ))

        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()
        logger.info(f"🚀 GitroHub v1.3 running on port {PORT}")
        logger.info(f"✅ OAuth callback: {WEBHOOK_URL}/auth/github/callback")
        await asyncio.Event().wait()
    else:
        logger.info("🔄 Running in polling mode (local)")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
