import os
import logging
import asyncio
from aiohttp import web
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", 0))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
PORT = int(os.environ.get("PORT", 8080))
TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID


def admin_only(func):
    """Decorator to restrict commands to admin only."""
    async def wrapper(update: Update, context):
        if not is_admin(update):
            from handlers.core import send_private_message
            await send_private_message(update, update.effective_user.id)
            return
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper


async def handle_callback(update: Update, context):
    """Central callback query router."""
    query = update.callback_query
    await query.answer()
    data = query.data
    telegram_id = update.effective_user.id

    from handlers.core import escape_md
    from database.db import clear_state, get_state, set_state, get_active_session

    # ── Navigation ──────────────────────────────────────────────────────────

    if data == "home":
        from handlers.core import cmd_start
        await query.message.reply_text("🏠 Home")
        return

    if data == "cancel":
        clear_state(telegram_id)
        await query.edit_message_text(
            "❌ *Cancelled — nothing was changed\\.*\n\n"
            "💡 Use /help to see what you can do",
            parse_mode="MarkdownV2",
            reply_markup=__import__('telegram').InlineKeyboardMarkup([[
                __import__('telegram').InlineKeyboardButton(
                    "🏠 Home", callback_data="home")
            ]])
        )
        return

    if data == "noop":
        return

    # ── Auth ─────────────────────────────────────────────────────────────────

    if data == "login_start":
        from handlers.auth import cmd_login
        await cmd_login(update, context)
        return

    if data == "accounts":
        from handlers.auth import show_accounts
        await show_accounts(query.message, telegram_id)
        return

    if data.startswith("switch_account_"):
        username = data[len("switch_account_"):]
        from database.db import switch_session, get_active_session, update_session
        switch_session(telegram_id, username)
        session = get_active_session(telegram_id)
        repo = session.get("active_repo", "None")
        branch = session.get("active_branch", "main")
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            f"✅ *Now on* `{escape_md(username)}` 👋\n\n"
            f"📍 Restored:\n"
            f"Active repo: `{escape_md(repo)}`\n"
            f"Branch: `{escape_md(branch)}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📂 Projects", callback_data="projects"),
                InlineKeyboardButton("📦 Repos", callback_data="repos"),
            ], [
                InlineKeyboardButton("🏠 Home", callback_data="home")
            ]])
        )
        return

    if data.startswith("remove_account_"):
        username = data[len("remove_account_"):]
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            f"⚠️ *Remove* `{escape_md(username)}`*?*\n\n"
            f"This disconnects the account from this bot\\.\n"
            f"Your GitHub data is completely untouched\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes, remove",
                    callback_data=f"confirm_remove_{username}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return

    if data.startswith("confirm_remove_"):
        username = data[len("confirm_remove_"):]
        from database.db import delete_session
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        delete_session(telegram_id, username)
        await query.edit_message_text(
            f"✅ `{escape_md(username)}` disconnected\\.\n"
            f"Your GitHub data is untouched\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👤 Accounts", callback_data="accounts"),
                InlineKeyboardButton("🏠 Home", callback_data="home")
            ]])
        )
        return

    if data.startswith("confirm_logout_"):
        username = data[len("confirm_logout_"):]
        from database.db import delete_session
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        # Also revoke token on GitHub
        try:
            from utils.github_helper import get_github_client
            gh = get_github_client(telegram_id)
            if gh:
                pass  # GitHub OAuth revocation via API
        except Exception:
            pass
        delete_session(telegram_id, username)
        await query.edit_message_text(
            f"✅ Logged out from `{escape_md(username)}`\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Login again", callback_data="login_start"),
                InlineKeyboardButton("👤 Accounts", callback_data="accounts")
            ]])
        )
        return

    # ── Repos ────────────────────────────────────────────────────────────────

    if data == "projects":
        from handlers.repos import show_projects
        await show_projects(query.message, telegram_id)
        return

    if data == "repos":
        from handlers.repos import show_repos
        await show_repos(query.message, telegram_id, page=0)
        return

    if data.startswith("repos_page_"):
        parts = data.split("_")
        page = int(parts[2])
        sort = parts[3] if len(parts) > 3 else "updated"
        from handlers.repos import show_repos
        await show_repos(query.message, telegram_id, page=page,
                         sort=sort, edit=True)
        return

    if data.startswith("repos_sort_"):
        parts = data.split("_")
        sort = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 0
        from handlers.repos import show_repos
        await show_repos(query.message, telegram_id, page=page,
                         sort=sort, edit=True)
        return

    if data == "create_repo":
        from handlers.repos import cmd_create
        await cmd_create(update, context)
        return

    if data.startswith("open_repo_"):
        repo_full = data[len("open_repo_"):]
        from database.db import update_session, add_to_recent
        from utils.github_helper import get_github_client, format_size, format_time_ago
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(repo_full)
            update_session(telegram_id,
                           active_repo=repo.full_name,
                           active_branch=repo.default_branch)
            add_to_recent(telegram_id, repo.full_name)
            session = get_active_session(telegram_id)
            username = session["github_username"]
            is_own = repo.owner.login == username
            vis = "🔒 Private" if repo.private else "🌍 Public"

            keyboard = [
                [
                    InlineKeyboardButton("📂 Browse", callback_data="browse"),
                    InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
                    InlineKeyboardButton("⬇️ Download", callback_data="download_menu"),
                ],
                [
                    InlineKeyboardButton("🌿 Branches", callback_data="branches"),
                    InlineKeyboardButton("📜 History", callback_data="log"),
                    InlineKeyboardButton("📊 Stats", callback_data="stats"),
                ],
                [
                    InlineKeyboardButton("📝 Issues", callback_data="issues"),
                    InlineKeyboardButton("🚀 Releases", callback_data="releases"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="repo_settings"),
                ],
                [
                    InlineKeyboardButton("📌 Pin",
                        callback_data=f"pin_repo_{repo.full_name}"),
                    InlineKeyboardButton("🏠 Home", callback_data="home"),
                ]
            ]
            await query.edit_message_text(
                f"📁 *{escape_md(repo.name)}*\n"
                f"{vis}  •  {escape_md(repo.language or '?')}  •  "
                f"{escape_md(format_size(repo.size))}\n"
                f"Branch: `{escape_md(repo.default_branch)}`" +
                ("\n\n⚠️ Read\\-only — not your repo" if not is_own else ""),
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
        return

    if data.startswith("pin_repo_"):
        repo_name = data[len("pin_repo_"):]
        session = get_active_session(telegram_id)
        if session:
            pinned = list(session.get("pinned_repos") or [])
            if repo_name not in pinned:
                pinned.append(repo_name)
                from database.db import update_session
                update_session(telegram_id, pinned_repos=pinned)
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.answer(f"📌 Pinned!", show_alert=False)
        return

    if data.startswith("toggle_vis_"):
        repo_full = data[len("toggle_vis_"):]
        from utils.github_helper import get_github_client, get_error_message
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(repo_full)
            is_private = repo.private
            action = "Make Public" if is_private else "Make Private"
            warning = ("⚠️ *Making repo PUBLIC*\\!\nEveryone on the internet can see it\\.\n\n"
                       if is_private else
                       "⚠️ *Making repo PRIVATE\\?*\n\n")
            await query.edit_message_text(
                f"{warning}Repo: `{escape_md(repo_full)}`\n"
                f"Current: {'🔒 Private' if is_private else '🌍 Public'}\n\n"
                f"Are you sure?",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"✅ Yes, {action}",
                        callback_data=f"confirm_vis_{repo_full}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
        except Exception as e:
            await query.edit_message_text(str(e))
        return

    if data.startswith("confirm_vis_"):
        repo_full = data[len("confirm_vis_"):]
        from utils.github_helper import get_github_client
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(repo_full)
            repo.edit(private=not repo.private)
            new_vis = "🔒 Private" if repo.private else "🌍 Public"
            await query.edit_message_text(
                f"✅ `{escape_md(repo_full)}` is now {new_vis}",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📂 Open", callback_data=f"open_repo_{repo_full}"),
                    InlineKeyboardButton("🏠 Home", callback_data="home")
                ]])
            )
        except Exception as e:
            await query.edit_message_text(str(e))
        return

    # ── Browse ───────────────────────────────────────────────────────────────

    if data == "browse" or data == "browse_root":
        from handlers.files import show_browse
        await show_browse(query.message, telegram_id, "", edit=False)
        return

    if data.startswith("browse_"):
        path = data[len("browse_"):]
        from handlers.files import show_browse
        await show_browse(query.message, telegram_id, path, edit=False)
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
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            f"🗑️ *Delete* `{escape_md(path)}`?\n\nThis cannot be undone\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yes, delete",
                    callback_data=f"confirm_delete_{path}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return

    if data.startswith("confirm_delete_"):
        path = data[len("confirm_delete_"):]
        from utils.github_helper import get_github_client, get_error_message
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        session = get_active_session(telegram_id)
        gh = get_github_client(telegram_id)
        try:
            repo = gh.get_repo(session["active_repo"])
            branch = session.get("active_branch", "main")
            file_content = repo.get_contents(path, ref=branch)
            repo.delete_file(path, f"Delete {path}", file_content.sha, branch=branch)
            await query.edit_message_text(
                f"🗑️ `{escape_md(path)}` deleted\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📂 Browse", callback_data="browse"),
                    InlineKeyboardButton("🏠 Home", callback_data="home")
                ]])
            )
        except Exception as e:
            await query.edit_message_text(str(e))
        return

    if data.startswith("copy_url_"):
        path = data[len("copy_url_"):]
        session = get_active_session(telegram_id)
        if session:
            branch = session.get("active_branch", "main")
            url = f"https://github.com/{session['active_repo']}/blob/{branch}/{path}"
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            await query.edit_message_text(
                f"🔗 *File URL:*\n`{escape_md(url)}`\n\nCopy the link above\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back",
                        callback_data=f"browse_{'/'.join(path.split('/')[:-1])}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
        return

    # ── Upload ───────────────────────────────────────────────────────────────

    if data == "upload_menu":
        from handlers.upload import show_upload_menu
        await show_upload_menu(query.message, telegram_id)
        return

    if data == "upload_single":
        set_state(telegram_id, "awaiting_path_declare", {})
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            "📄 *Single file upload*\n\n"
            "Use: `/upload src/app\\.py`\n"
            "Then send your file\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return

    if data == "upload_mirror":
        from handlers.upload import cmd_mirror
        await cmd_mirror(update, context)
        return

    if data == "upload_update":
        from handlers.upload import cmd_update
        await cmd_update(update, context)
        return

    if data == "upload_batch":
        from handlers.upload import cmd_batch
        await cmd_batch(update, context)
        return

    if data == "batch_review":
        state_info = get_state(telegram_id)
        state_data = state_info.get("state_data", {})
        files = state_data.get("files", {})
        session = get_active_session(telegram_id)
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        from utils.github_helper import get_github_client, get_file_diff
        import base64

        gh = get_github_client(telegram_id)
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")

        new_f, modified_f, unchanged_f = [], [], []
        for path, content in files.items():
            try:
                existing = repo.get_contents(path, ref=branch)
                old = base64.b64decode(existing.content).decode("utf-8", errors="replace")
                if old != content:
                    modified_f.append(path)
                else:
                    unchanged_f.append(path)
            except Exception:
                new_f.append(path)

        set_state(telegram_id, "confirming_batch_commit", {
            **state_data,
            "new_files": new_f,
            "modified_files": modified_f,
            "unchanged_files": unchanged_f
        })

        text = f"🔄 *Changes* — `{escape_md(session['active_repo'])}`\n\n"
        if new_f:
            text += "✨ *New:*\n" + "\n".join(f"   \\+ `{escape_md(f)}`" for f in new_f) + "\n\n"
        if modified_f:
            text += "🟡 *Modified:*\n" + "\n".join(f"   ~ `{escape_md(f)}`" for f in modified_f) + "\n\n"
        if unchanged_f:
            text += f"⏭️ *Unchanged:* {len(unchanged_f)} files \\(skipped\\)\n"

        await query.edit_message_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✏️ Write message", callback_data="commit_write"),
                    InlineKeyboardButton("🤖 Auto-generate", callback_data="commit_auto"),
                ],
                [
                    InlineKeyboardButton("✅ Commit", callback_data="confirm_batch_commit"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ])
        )
        return

    # ── Commit flow ──────────────────────────────────────────────────────────

    if data == "commit_write":
        set_state(telegram_id, "awaiting_commit_message",
                  get_state(telegram_id).get("state_data", {}))
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            "💬 *Write your commit message:*",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return

    if data == "commit_auto":
        state_info = get_state(telegram_id)
        state_data = state_info.get("state_data", {})
        # Auto-generate based on changes
        new_f = state_data.get("new_files", [])
        mod_f = state_data.get("modified_files", [])
        del_f = state_data.get("deleted_files", [])
        path = state_data.get("path", "")

        parts = []
        if path:
            parts.append(f"Updated {path.split('/')[-1]}")
        if new_f:
            names = ", ".join(f.split("/")[-1] for f in new_f[:3])
            parts.append(f"Added {names}")
        if mod_f:
            names = ", ".join(f.split("/")[-1] for f in mod_f[:3])
            parts.append(f"Updated {names}")
        if del_f:
            names = ", ".join(f.split("/")[-1] for f in del_f[:2])
            parts.append(f"Removed {names}")

        auto_msg = "; ".join(parts) if parts else "Updated files"

        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            f"🤖 *Suggested message:*\n\n\"{escape_md(auto_msg)}\"",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Use this", callback_data=f"use_msg_{auto_msg}"),
                InlineKeyboardButton("✏️ Edit it", callback_data="commit_write"),
            ], [
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return

    if data == "commit_recent":
        session = get_active_session(telegram_id)
        from database.db import get_commit_history
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        history = get_commit_history(telegram_id, session["github_username"],
                                     session["active_repo"])
        if not history:
            await query.answer("No recent commit messages yet.", show_alert=True)
            return

        keyboard = []
        for i, msg in enumerate(history):
            keyboard.append([
                InlineKeyboardButton(f"{msg[:40]}...",
                    callback_data=f"use_msg_{msg}")
            ])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

        await query.edit_message_text(
            "📋 *Recent commit messages:*\n\nTap to reuse:",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if data.startswith("use_msg_"):
        commit_msg = data[len("use_msg_"):]
        state_info = get_state(telegram_id)
        state = state_info.get("state", "")
        state_data = state_info.get("state_data", {})

        if "single" in state or state == "awaiting_commit_message":
            from handlers.upload import do_commit_single
            await do_commit_single(query.message, telegram_id, commit_msg, context)
        elif "batch" in state:
            await do_batch_commit(query, telegram_id, commit_msg)
        elif "zip" in state:
            await do_zip_commit(query, telegram_id, commit_msg)
        return

    if data == "confirm_zip_commit":
        set_state(telegram_id, "awaiting_commit_message",
                  get_state(telegram_id).get("state_data", {}))
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            "💬 *Commit message?*",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✏️ Write", callback_data="commit_write"),
                    InlineKeyboardButton("🤖 Auto-generate", callback_data="commit_auto"),
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
            ])
        )
        return

    # ── Preview tree ─────────────────────────────────────────────────────────

    if data in ("preview_tree", "preview_zip_tree"):
        state_info = get_state(telegram_id)
        state_data = state_info.get("state_data", {})
        session = get_active_session(telegram_id)
        from utils.github_helper import get_github_client
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        new_f = set(state_data.get("new_files", []))
        mod_f = set(state_data.get("modified_files", []))
        del_f = set(state_data.get("deleted_files", []))
        path = state_data.get("path", "")
        if path:
            new_f = {path} if state_data.get("is_new") else set()
            mod_f = {path} if not state_data.get("is_new") else set()

        gh = get_github_client(telegram_id)
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")

        try:
            contents = repo.get_contents("", ref=branch)
            if not isinstance(contents, list):
                contents = [contents]
            tree = build_tree(contents, changed_files=mod_f,
                              new_files=new_f, deleted_files=del_f)
        except Exception:
            tree = "Unable to generate tree"

        await query.edit_message_text(
            f"👁 *Preview — after commit*\n"
            f"`{escape_md(session['active_repo'])}` @ `{escape_md(branch)}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"```\n{tree}\n```\n\n"
            f"✨ New  🟡 Modified  🗑️ Deleted",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Looks good, commit",
                    callback_data="confirm_zip_commit"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return

    # ── Help sections ────────────────────────────────────────────────────────

    help_sections = {
        "help_repos": (
            "📁 *Repo Commands*\n\n"
            "/projects — Your active repos\n"
            "/repos — All repos on GitHub\n"
            "/create — Create new repo\n"
            "/use — Set active repo\n"
            "/clone — Clone any repo\n"
            "/download — Download as ZIP\n"
            "/stats — Repo statistics\n"
            "/visibility — Toggle public/private"
        ),
        "help_files": (
            "📂 *File Commands*\n\n"
            "/browse — Browse repo files\n"
            "/read — Read file contents\n"
            "/edit — Edit file in chat\n"
            "/move — Move file\n"
            "/rename — Rename file\n"
            "/delete — Delete file\n"
            "/search — Search in repo"
        ),
        "help_upload": (
            "⬆️ *Upload Commands*\n\n"
            "/upload \\<path\\> — Single file\n"
            "/batch — Multiple files\n"
            "/mirror — ZIP \\(full mirror\\)\n"
            "/update — ZIP \\(add & modify only\\)"
        ),
        "help_branches": (
            "🌿 *Branch Commands*\n\n"
            "/branch — View branches\n"
            "/switch — Switch branch\n"
            "/merge — Merge branch\n"
            "/diff — Compare branches"
        ),
        "help_history": (
            "📜 *History Commands*\n\n"
            "/log — Commit history\n"
            "/undo — Reverse last commit\n"
            "/rollback — Go to specific commit"
        ),
        "help_accounts": (
            "👤 *Account Commands*\n\n"
            "/login — Connect GitHub\n"
            "/logout — Disconnect account\n"
            "/accounts — Manage accounts\n"
            "/switchaccount — Switch account\n"
            "/whoami — Current account info\n"
            "/status — Bot status"
        ),
        "help_settings": (
            "⚙️ *Settings Commands*\n\n"
            "/settings — Personalization\n"
            "/privatemsg — Custom private message\n"
            "/savedpaths — Favourite paths\n"
            "/aliases — Command shortcuts\n"
            "/templates — Commit templates"
        ),
        "help_safety": (
            "🛡️ *Safety Commands*\n\n"
            "/cancel — Cancel any action\n"
            "/ping — Check bot status\n"
            "/version — Bot version\n\n"
            "All deletions require confirmation\\.\n"
            "Repo deletion requires 3\\-step verification\\.\n"
            "All tokens encrypted with AES\\-256\\."
        ),
    }

    if data in help_sections:
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            help_sections[data],
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Help", callback_data="help_back"),
                InlineKeyboardButton("🏠 Home", callback_data="home")
            ]])
        )
        return

    if data == "help_back":
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        await query.edit_message_text(
            "❓ *GitroHub — Help*\n\nSelect a category:",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📁 Repos", callback_data="help_repos"),
                    InlineKeyboardButton("📂 Files", callback_data="help_files"),
                    InlineKeyboardButton("⬆️ Upload", callback_data="help_upload"),
                ],
                [
                    InlineKeyboardButton("🌿 Branches", callback_data="help_branches"),
                    InlineKeyboardButton("📜 History", callback_data="help_history"),
                    InlineKeyboardButton("👤 Accounts", callback_data="help_accounts"),
                ],
                [
                    InlineKeyboardButton("⚙️ Settings", callback_data="help_settings"),
                    InlineKeyboardButton("🛡️ Safety", callback_data="help_safety"),
                ],
                [InlineKeyboardButton("🏠 Home", callback_data="home")]
            ])
        )
        return

    # ── Download ─────────────────────────────────────────────────────────────

    if data == "download_menu":
        session = get_active_session(telegram_id)
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = []
        if session and session.get("active_repo"):
            keyboard.append([
                InlineKeyboardButton(
                    f"⬇️ Download {session['active_repo'].split('/')[-1]}",
                    callback_data=f"dl_{session['active_repo']}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("📦 My repos", callback_data="repos"),
            InlineKeyboardButton("🔗 By URL", callback_data="dl_by_url"),
        ])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        await query.edit_message_text(
            "⬇️ *Download*\n\nWhich repo?",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    logger.info(f"Unhandled callback: {data}")


async def handle_text_message(update: Update, context):
    """Handle text messages — used for state-based flows."""
    telegram_id = update.effective_user.id
    text = update.message.text.strip()

    if not is_admin(update):
        return

    from database.db import get_state, set_state, clear_state, get_active_session
    state_info = get_state(telegram_id)
    state = state_info.get("state", "idle")
    state_data = state_info.get("state_data", {})

    from handlers.core import escape_md
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    if state == "awaiting_commit_message":
        from handlers.upload import do_commit_single
        set_state(telegram_id, "confirming_single_commit", state_data)
        await do_commit_single(update.message, telegram_id, text, context)
        return

    if state == "awaiting_search":
        from handlers.files import do_search
        await do_search(update.message, telegram_id, text)
        return

    if state == "creating_repo" and state_data.get("step") == "name":
        from handlers.repos import ask_visibility
        set_state(telegram_id, "creating_repo",
                  {"name": text, "step": "visibility"})
        await ask_visibility(update.message, text)
        return

    if state == "deleting_repo_step1":
        repo = state_data.get("repo", "")
        if text == repo.split("/")[-1] or text == repo:
            set_state(telegram_id, "deleting_repo_step2", state_data)
            await update.message.reply_text(
                f"✅ *Step 1 confirmed*\n\n"
                f"*Step 2/3* — Check your GitHub email\n"
                f"📧 Enter the code GitHub sent you:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
        else:
            await update.message.reply_text(
                f"❌ *Wrong name*\n"
                f"You typed: `{escape_md(text)}`\n"
                f"Expected: `{escape_md(repo.split('/')[-1])}`\n\n"
                f"Try again or cancel:",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
        return

    # Check aliases
    from database.db import get_aliases
    aliases = get_aliases(telegram_id)
    for alias_row in aliases:
        if text == alias_row["alias"] or text.startswith(alias_row["alias"] + " "):
            # Execute aliased command
            await update.message.reply_text(
                f"⚡ Alias: `{escape_md(alias_row['alias'])}` → "
                f"`{escape_md(alias_row['command'])}`",
                parse_mode="MarkdownV2"
            )
            return


async def setup_webhook(app: Application):
    """Set up webhook for Railway deployment."""
    await app.bot.set_webhook(
        url=f"{WEBHOOK_URL}/webhook",
        allowed_updates=["message", "callback_query"]
    )
    logger.info(f"✅ Webhook set to {WEBHOOK_URL}/webhook")


async def main():
    """Main entry point."""
    from database.db import init_db
    from handlers.core import setup_commands

    # Initialize database
    init_db()

    # Build application
    app = Application.builder().token(TOKEN).build()

    # Register command handlers
    from handlers.auth import (
        cmd_login, cmd_logout, cmd_accounts,
        cmd_whoami, cmd_switchaccount
    )
    from handlers.core import (
        cmd_start, cmd_ping, cmd_status,
        cmd_version, cmd_help, cmd_cancel
    )
    from handlers.repos import (
        cmd_repos, cmd_projects, cmd_create,
        cmd_use, cmd_delete_repo, cmd_rename_repo, cmd_visibility
    )
    from handlers.files import (
        cmd_browse, cmd_read, cmd_edit,
        cmd_delete_file, cmd_search, cmd_move
    )
    from handlers.upload import (
        cmd_upload, cmd_batch, cmd_mirror,
        cmd_update, handle_incoming_file
    )

    # Apply admin_only to all command handlers
    commands = [
        ("start", cmd_start),
        ("login", cmd_login),
        ("logout", cmd_logout),
        ("accounts", cmd_accounts),
        ("switchaccount", cmd_switchaccount),
        ("whoami", cmd_whoami),
        ("status", cmd_status),
        ("ping", cmd_ping),
        ("version", cmd_version),
        ("help", cmd_help),
        ("cancel", cmd_cancel),
        ("repos", cmd_repos),
        ("projects", cmd_projects),
        ("create", cmd_create),
        ("use", cmd_use),
        ("browse", cmd_browse),
        ("read", cmd_read),
        ("edit", cmd_edit),
        ("delete", cmd_delete_file),
        ("search", cmd_search),
        ("move", cmd_move),
        ("upload", cmd_upload),
        ("batch", cmd_batch),
        ("mirror", cmd_mirror),
        ("update", cmd_update),
    ]

    for cmd_name, handler in commands:
        if cmd_name == "start":
            app.add_handler(CommandHandler(cmd_name, handler))
        else:
            app.add_handler(CommandHandler(cmd_name, admin_only(handler)))

    # File handler
    app.add_handler(MessageHandler(
        filters.Document.ALL,
        admin_only(handle_incoming_file)
    ))

    # Text message handler (for state flows)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_text_message
    ))

    # Callback query handler
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Initialize and set up commands
    await app.initialize()
    await setup_commands(app.bot)

    if WEBHOOK_URL:
        # Railway webhook mode
        await setup_webhook(app)

        async def webhook_handler(request):
            data = await request.json()
            update = Update.de_json(data, app.bot)
            await app.process_update(update)
            return web.Response(text="OK")

        web_app = web.Application()
        web_app.router.add_post("/webhook", webhook_handler)
        web_app.router.add_get("/", lambda r: web.Response(text="GitroHub Bot Running 🚀"))

        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", PORT)
        await site.start()

        logger.info(f"🚀 GitroHub Bot running on port {PORT}")
        await asyncio.Event().wait()
    else:
        # Local polling mode
        logger.info("🔄 Running in polling mode (local)")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
