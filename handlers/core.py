"""Core handlers — GitroHub v1.3"""
import logging
import os
import time

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import get_active_session, get_settings
from utils.github_helper import h

logger = logging.getLogger(__name__)

ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", 0))
BOT_VERSION = "1.3.0"

ALL_COMMANDS = [
    BotCommand("start", "Welcome & quick start"),
    BotCommand("projects", "Your active working repos"),
    BotCommand("repos", "All repos on your GitHub account"),
    BotCommand("create", "Create a new repo"),
    BotCommand("use", "Switch active repo"),
    BotCommand("upload", "Upload a single file"),
    BotCommand("batch", "Upload multiple files"),
    BotCommand("mirror", "ZIP upload — full mirror mode"),
    BotCommand("update", "ZIP upload — add and modify mode"),
    BotCommand("browse", "Browse repo files interactively"),
    BotCommand("search", "Search inside active repo"),
    BotCommand("read", "Read a file from repo"),
    BotCommand("edit", "Edit a file directly in chat"),
    BotCommand("move", "Move a file to a new path"),
    BotCommand("rename", "Rename a file"),
    BotCommand("delete", "Delete a file or folder"),
    BotCommand("download", "Download repo as ZIP"),
    BotCommand("clone", "Clone any repo into your GitHub"),
    BotCommand("branch", "Manage branches"),
    BotCommand("switch", "Switch active branch"),
    BotCommand("merge", "Merge a branch"),
    BotCommand("diff", "Compare two branches"),
    BotCommand("log", "View commit history"),
    BotCommand("undo", "Reverse last commit"),
    BotCommand("rollback", "Rollback to specific commit"),
    BotCommand("issues", "Manage repo issues"),
    BotCommand("releases", "Manage repo releases"),
    BotCommand("gists", "Manage your gists"),
    BotCommand("star", "Star any GitHub repo"),
    BotCommand("unstar", "Unstar a repo"),
    BotCommand("stars", "View your starred repos"),
    BotCommand("contributors", "View repo contributors"),
    BotCommand("traffic", "View repo traffic"),
    BotCommand("stats", "Repo statistics"),
    BotCommand("profile", "Your GitHub profile summary"),
    BotCommand("whoami", "Current account and session info"),
    BotCommand("status", "Current bot status"),
    BotCommand("accounts", "Manage connected GitHub accounts"),
    BotCommand("switchaccount", "Switch between GitHub accounts"),
    BotCommand("privatemsg", "Customize unauthorized access message"),
    BotCommand("savedpaths", "Manage favourite upload paths"),
    BotCommand("aliases", "Manage command shortcuts"),
    BotCommand("templates", "Manage commit message templates"),
    BotCommand("settings", "Bot personalization settings"),
    BotCommand("ping", "Check bot is alive"),
    BotCommand("version", "Bot version and changelog"),
    BotCommand("help", "Full command list by category"),
    BotCommand("cancel", "Cancel any current action"),
    BotCommand("login", "Connect a GitHub account"),
    BotCommand("logout", "Disconnect current GitHub account"),
]


async def setup_commands(bot):
    await bot.set_my_commands(ALL_COMMANDS)
    logger.info("✅ Bot commands registered with Telegram")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if telegram_id != ADMIN_ID:
        await send_private_message(update, telegram_id)
        return

    session = get_active_session(telegram_id)
    if not session:
        from handlers.auth import generate_oauth_url
        from database.db import set_state
        oauth_url, state = generate_oauth_url(telegram_id)
        set_state(telegram_id, "awaiting_oauth", {"state": state})
        await update.message.reply_text(
            "👋 <b>Welcome to GitroHub!</b>\n\n"
            "Your GitHub lives here now. Manage repos, commit code, "
            "upload files, handle branches — all without leaving Telegram.\n\n"
            "<b>Secure · Fast · Always in sync with GitHub</b>\n\n"
            "Tap below to connect your GitHub account 👇",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Connect GitHub Account", url=oauth_url)
            ]])
        )
        return

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
    await update.message.reply_text(
        f"👋 <b>Welcome back, {h(username)}!</b>\n\n"
        f"📁 <code>{h(repo)}</code> @ <code>{h(branch)}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    db_ok = False
    try:
        from database.db import db_cursor
        with db_cursor() as cur:
            cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    gh_ok = False
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            r = await s.get("https://api.github.com/zen", timeout=aiohttp.ClientTimeout(total=5))
            gh_ok = r.status == 200
    except Exception:
        pass

    elapsed = int((time.time() - start) * 1000)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    await update.message.reply_text(
        f"🏓 <b>Pong!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Response: <code>{elapsed}ms</code>\n"
        f"🟢 Bot: Online\n"
        f"{'🟢' if db_ok else '🔴'} Database: {'Connected' if db_ok else 'Error'}\n"
        f"{'🟢' if gh_ok else '🔴'} GitHub API: {'Reachable' if gh_ok else 'Unreachable'}\n"
        f"🕐 Server time: <code>{now}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)

    db_ok = False
    try:
        from database.db import db_cursor
        with db_cursor() as cur:
            cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    gh_ok = False
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            r = await s.get("https://api.github.com/zen", timeout=aiohttp.ClientTimeout(total=5))
            gh_ok = r.status == 200
    except Exception:
        pass

    from database.db import get_state
    state_info = get_state(telegram_id)
    current_state = state_info.get("state", "idle")

    if session:
        text = (
            f"📍 <b>Current Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Account: <code>{h(session['github_username'])}</code>\n"
            f"📁 Repo: <code>{h(session.get('active_repo') or 'None')}</code>\n"
            f"🌿 Branch: <code>{h(session.get('active_branch') or 'main')}</code>\n"
            f"⚡ State: <code>{h(current_state)}</code>\n\n"
            f"🟢 Bot: Online\n"
            f"{'🟢' if db_ok else '🔴'} Database: {'Connected' if db_ok else 'Error'}\n"
            f"{'🟢' if gh_ok else '🔴'} GitHub: {'Reachable' if gh_ok else 'Unreachable'}"
        )
    else:
        text = (
            f"📍 <b>Status</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Account: Not logged in\n\n"
            f"🟢 Bot: Online\n"
            f"{'🟢' if db_ok else '🔴'} Database: {'Connected' if db_ok else 'Error'}\n"
            f"{'🟢' if gh_ok else '🔴'} GitHub: {'Reachable' if gh_ok else 'Unreachable'}"
        )
    keyboard = [[InlineKeyboardButton("🏠 Home", callback_data="home")]]
    if session:
        keyboard.insert(0, [InlineKeyboardButton("📂 Browse", callback_data="browse"),
                             InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu")])
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 <b>GitroHub v{BOT_VERSION}</b>\n\n"
        f"📋 <b>Changelog v1.3.0:</b>\n"
        f"• Migrated to HTML parse mode (fixes all button crashes)\n"
        f"• Fixed /auth/github/callback OAuth route\n"
        f"• Fixed show_accounts in callback context\n"
        f"• Added global error handler (no more silent crashes)\n"
        f"• Fixed all protect_branch, new_branch callbacks\n"
        f"• Fixed cmd_stats/issues/releases from callback context\n"
        f"• Registered all 50 commands correctly\n"
        f"• Full batch/ZIP commit flows working\n"
        f"• Bot now stable and crash-resistant",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ <b>GitroHub — Help</b>\n\nSelect a category:",
        parse_mode="HTML",
        reply_markup=_help_keyboard()
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db import clear_state
    clear_state(update.effective_user.id)
    await update.message.reply_text(
        "❌ <b>Cancelled — nothing was changed.</b>\n\n💡 Use /help to see what you can do",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
    )


def _help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Repos", callback_data="help_repos"),
         InlineKeyboardButton("📂 Files", callback_data="help_files"),
         InlineKeyboardButton("⬆️ Upload", callback_data="help_upload")],
        [InlineKeyboardButton("⬇️ Download", callback_data="help_download"),
         InlineKeyboardButton("🌿 Branches", callback_data="help_branches"),
         InlineKeyboardButton("📜 History", callback_data="help_history")],
        [InlineKeyboardButton("📝 Issues", callback_data="help_issues"),
         InlineKeyboardButton("🚀 Releases", callback_data="help_releases"),
         InlineKeyboardButton("📊 Stats", callback_data="help_stats")],
        [InlineKeyboardButton("👤 Accounts", callback_data="help_accounts"),
         InlineKeyboardButton("⚙️ Settings", callback_data="help_settings"),
         InlineKeyboardButton("🛡️ Safety", callback_data="help_safety")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ])


HELP_SECTIONS = {
    "help_repos": (
        "📁 <b>Repo Commands</b>\n\n"
        "/projects — Your active repos\n/repos — All repos on GitHub\n"
        "/create — Create new repo\n/use &lt;repo&gt; — Set active repo\n"
        "/clone &lt;url&gt; — Clone any repo\n/download — Download as ZIP\n"
        "/stats — Repo statistics"
    ),
    "help_files": (
        "📂 <b>File Commands</b>\n\n"
        "/browse — Browse repo files\n/read &lt;file&gt; — Read file contents\n"
        "/edit &lt;file&gt; — Edit file in chat\n/move — Move file\n"
        "/rename — Rename file\n/delete — Delete file\n/search — Search in repo"
    ),
    "help_upload": (
        "⬆️ <b>Upload Commands</b>\n\n"
        "/upload &lt;path&gt; — Single file\n/batch — Multiple files\n"
        "/mirror — ZIP (full mirror)\n/update — ZIP (add and modify only)"
    ),
    "help_download": (
        "⬇️ <b>Download Commands</b>\n\n"
        "/download — Active repo as ZIP\n/download &lt;name&gt; — Your repo\n"
        "/download &lt;user/repo&gt; — Any public repo\n/clone &lt;url&gt; — Clone into your account"
    ),
    "help_branches": (
        "🌿 <b>Branch Commands</b>\n\n"
        "/branch — View all branches\n/switch &lt;name&gt; — Switch branch\n"
        "/merge &lt;name&gt; — Merge branch\n/diff &lt;b1&gt; &lt;b2&gt; — Compare branches"
    ),
    "help_history": (
        "📜 <b>History Commands</b>\n\n"
        "/log — Commit history\n/undo — Reverse last commit\n"
        "/rollback &lt;sha&gt; — Go to specific commit"
    ),
    "help_issues": (
        "📝 <b>Issues and Stars</b>\n\n"
        "/issues — View open issues\n/star &lt;repo&gt; — Star a repo\n"
        "/unstar &lt;repo&gt; — Unstar a repo\n/stars — Your starred repos\n/gists — Manage gists"
    ),
    "help_releases": (
        "🚀 <b>Releases</b>\n\n"
        "/releases — List releases\n"
        "Tap ➕ New Release in the releases menu to create one"
    ),
    "help_stats": (
        "📊 <b>Stats Commands</b>\n\n"
        "/stats — Repo statistics\n/profile — GitHub profile\n"
        "/traffic — Repo traffic\n/contributors — Contributors\n"
        "/whoami — Session info\n/status — Bot status"
    ),
    "help_accounts": (
        "👤 <b>Account Commands</b>\n\n"
        "/login — Connect GitHub\n/logout — Disconnect account\n"
        "/accounts — Manage accounts\n/switchaccount — Switch account\n"
        "/whoami — Current account info\n/status — Bot status"
    ),
    "help_settings": (
        "⚙️ <b>Settings Commands</b>\n\n"
        "/settings — Personalization\n/privatemsg — Custom private message\n"
        "/savedpaths — Favourite paths\n/aliases — Command shortcuts\n"
        "/templates — Commit templates"
    ),
    "help_safety": (
        "🛡️ <b>Safety</b>\n\n"
        "/cancel — Cancel any action\n/ping — Check bot status\n/version — Bot version\n\n"
        "All deletions require confirmation.\n"
        "Repo deletion: 3-step verification.\n"
        "Tokens: AES-256-GCM encrypted."
    ),
}


async def send_private_message(update: Update, telegram_id: int):
    settings = get_settings(ADMIN_ID) if ADMIN_ID else {}
    custom_msg = settings.get("private_message")
    owner = settings.get("private_message_owner", "@GitroHubBot")
    link = settings.get("private_message_link")

    if custom_msg:
        from datetime import datetime
        msg = (custom_msg
               .replace("{owner}", owner or "")
               .replace("{botname}", "GitroHub")
               .replace("{date}", datetime.now().strftime("%b %d %Y"))
               .replace("{link}", link or ""))
        await update.message.reply_text(msg)
        return

    text = (
        f"🔒 <b>GitroHub — Private Bot</b>\n\n"
        f"This bot is privately owned and is not open for public access.\n\n"
        f"👤 Owner: {h(owner)}\n\n"
        f"📖 <b>About:</b>\n"
        f"GitroHub is a personal GitHub management bot — commit code, manage repos, "
        f"upload files and handle branches directly from Telegram."
    )
    if link:
        text += f"\n\n🔗 {h(link)}"
    text += "\n\n──────────────────────\n⚙️ Powered by @GitroHubBot"
    await update.message.reply_text(text, parse_mode="HTML")
