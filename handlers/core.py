import os
import time
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes
from database.db import get_active_session, get_all_sessions, get_settings
from utils.github_helper import get_github_client, format_time_ago

logger = logging.getLogger(__name__)

ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", 0))
BOT_VERSION = "1.2.0"
BOT_RELEASE_DATE = "Apr 2026"

ALL_COMMANDS = [
    BotCommand("start", "Welcome & quick start"),
    BotCommand("projects", "Your active working repos"),
    BotCommand("repos", "All repos on your GitHub account"),
    BotCommand("create", "Create a new repo"),
    BotCommand("use", "Switch active repo"),
    BotCommand("upload", "Upload a single file"),
    BotCommand("batch", "Upload multiple files"),
    BotCommand("mirror", "ZIP upload full mirror mode"),
    BotCommand("update", "ZIP upload add and modify mode"),
    BotCommand("browse", "Browse repo files interactively"),
    BotCommand("search", "Search inside active repo"),
    BotCommand("read", "Read a file from repo"),
    BotCommand("edit", "Edit a file directly in chat"),
    BotCommand("move", "Move a file to new path"),
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
    BotCommand("stars", "View your starred repos"),
    BotCommand("contributors", "View repo contributors"),
    BotCommand("traffic", "View repo traffic"),
    BotCommand("stats", "Repo statistics"),
    BotCommand("profile", "Your GitHub profile summary"),
    BotCommand("whoami", "Current account and session info"),
    BotCommand("status", "Current bot status"),
    BotCommand("accounts", "Manage connected GitHub accounts"),
    BotCommand("switchaccount", "Switch between accounts"),
    BotCommand("privatemsg", "Customize unauthorized message"),
    BotCommand("savedpaths", "Manage favourite paths"),
    BotCommand("aliases", "Manage command shortcuts"),
    BotCommand("templates", "Commit message templates"),
    BotCommand("settings", "Bot personalization settings"),
    BotCommand("ping", "Check bot is alive"),
    BotCommand("version", "Bot version and changelog"),
    BotCommand("help", "Full command list"),
    BotCommand("cancel", "Cancel any current action"),
    BotCommand("login", "Connect a GitHub account"),
    BotCommand("logout", "Disconnect current GitHub account"),
]


async def setup_commands(bot):
    """Register all commands with Telegram — called on startup."""
    await bot.set_my_commands(ALL_COMMANDS)
    logger.info("✅ Bot commands registered with Telegram")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id

    if telegram_id != ADMIN_ID:
        await send_private_message(update, telegram_id)
        return

    session = get_active_session(telegram_id)

    if not session:
        # First time — onboarding
        from handlers.auth import generate_oauth_url
        oauth_url, state = generate_oauth_url(telegram_id)
        from database.db import set_state as _set_state
        _set_state(telegram_id, "awaiting_oauth", {"state": state})
        keyboard = [[
            InlineKeyboardButton("🔗 Connect GitHub Account", url=oauth_url)
        ]]
        await update.message.reply_text(
            "👋 *Welcome to GitroHub\\!*\n\n"
            "Your GitHub lives here now\\. Manage repos,\n"
            "commit code, upload files, handle branches\n"
            "\\& PRs — all without leaving Telegram\\.\n\n"
            "Secure · Fast · Always in sync with GitHub\n\n"
            "Tap below to connect your GitHub account 👇",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Returning user
    username = session["github_username"]
    active_repo = session.get("active_repo", "No active repo")
    active_branch = session.get("active_branch", "main")

    keyboard = [
        [
            InlineKeyboardButton("📂 Projects", callback_data="projects"),
            InlineKeyboardButton("📦 All Repos", callback_data="repos"),
            InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
        ],
        [
            InlineKeyboardButton("⬇️ Download", callback_data="download_menu"),
            InlineKeyboardButton("🌿 Branches", callback_data="branches"),
            InlineKeyboardButton("📜 History", callback_data="log"),
        ],
        [
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
            InlineKeyboardButton("👤 Accounts", callback_data="accounts"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ]
    ]

    await update.message.reply_text(
        f"👋 *Welcome back, {escape_md(username)}\\!*\n\n"
        f"📁 `{escape_md(active_repo)}` @ `{escape_md(active_branch)}`",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()

    # Test DB
    db_ok = False
    try:
        from database.db import db_cursor
        with db_cursor() as cur:
            cur.execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    # Test GitHub API
    gh_ok = False
    try:
        import aiohttp
        async with aiohttp.ClientSession() as s:
            r = await s.get("https://api.github.com/zen",
                            timeout=aiohttp.ClientTimeout(total=5))
            gh_ok = r.status == 200
    except Exception:
        pass

    elapsed = int((time.time() - start) * 1000)
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    db_icon = "🟢" if db_ok else "🔴"
    gh_icon = "🟢" if gh_ok else "🔴"

    await update.message.reply_text(
        f"🏓 *Pong\\!*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Response time: `{elapsed}ms`\n"
        f"🟢 Bot: Online\n"
        f"{db_icon} Database: {'Connected' if db_ok else 'Error'}\n"
        f"{gh_icon} GitHub API: {'Reachable' if gh_ok else 'Unreachable'}\n"
        f"🕐 Server time: `{now}`",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ]])
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)

    # System checks
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
            r = await s.get("https://api.github.com/zen",
                            timeout=aiohttp.ClientTimeout(total=5))
            gh_ok = r.status == 200
    except Exception:
        pass

    from database.db import get_state
    state_info = get_state(telegram_id)
    current_state = state_info.get("state", "idle")
    pending = "None — bot is idle" if current_state == "idle" else f"⏳ {current_state}"

    db_icon = "🟢" if db_ok else "🔴"
    gh_icon = "🟢" if gh_ok else "🔴"

    if session:
        username = session["github_username"]
        repo = session.get("active_repo") or "None"
        branch = session.get("active_branch") or "main"
        text = (
            f"📍 *Current Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Account:   `{escape_md(username)}`\n"
            f"📁 Repo:      `{escape_md(repo)}`\n"
            f"🌿 Branch:    `{escape_md(branch)}`\n\n"
            f"⚡ *Pending Actions:*\n"
            f"{escape_md(pending)}\n\n"
            f"🟢 *All systems:*\n"
            f"Bot:      🟢 Online\n"
            f"Database: {db_icon} {'Connected' if db_ok else 'Error'}\n"
            f"GitHub:   {gh_icon} {'Reachable' if gh_ok else 'Unreachable'}"
        )
    else:
        text = (
            f"📍 *Status*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Account:   Not logged in\n\n"
            f"🟢 *Systems:*\n"
            f"Bot:      🟢 Online\n"
            f"Database: {db_icon} {'Connected' if db_ok else 'Error'}\n"
            f"GitHub:   {gh_icon} {'Reachable' if gh_ok else 'Unreachable'}"
        )

    keyboard = []
    if session:
        keyboard.append([
            InlineKeyboardButton("📂 Open Repo", callback_data="browse"),
            InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
        ])
    keyboard.append([
        InlineKeyboardButton("🏠 Home", callback_data="home")
    ])

    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 *GitroHub*\n"
        f"Version: `{BOT_VERSION}`\n"
        f"Released: {BOT_RELEASE_DATE}\n\n"
        f"📋 *Changelog:*\n"
        f"v1\\.2\\.0 — Bug\\-fix & polish release\n"
        f"• Connect GitHub button is now a proper link\n"
        f"• Home button now shows full dashboard\n"
        f"• All inline buttons now respond correctly\n"
        f"• Stats, log, branches, issues, releases\n"
        f"  all respond from inline buttons\n"
        f"• Help sections fully wired up\n"
        f"• Download by URL added\n"
        f"• Batch commit flow fully fixed\n\n"
        f"v1\\.1\\.0 — Multi\\-account support\n"
        f"v1\\.0\\.0 — Initial release\n"
        f"• Full GitHub management\n"
        f"• ZIP mirror \\& update modes\n"
        f"• Single \\& batch file upload\n"
        f"• Interactive browse with breadcrumbs\n"
        f"• Persistent encrypted sessions\n"
        f"• Commit history \\& rollback\n"
        f"• Branch management",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ]])
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("📁 Repos", callback_data="help_repos"),
            InlineKeyboardButton("📂 Files", callback_data="help_files"),
            InlineKeyboardButton("⬆️ Upload", callback_data="help_upload"),
        ],
        [
            InlineKeyboardButton("⬇️ Download", callback_data="help_download"),
            InlineKeyboardButton("🌿 Branches", callback_data="help_branches"),
            InlineKeyboardButton("📜 History", callback_data="help_history"),
        ],
        [
            InlineKeyboardButton("📝 Issues", callback_data="help_issues"),
            InlineKeyboardButton("🚀 Releases", callback_data="help_releases"),
            InlineKeyboardButton("📊 Stats", callback_data="help_stats"),
        ],
        [
            InlineKeyboardButton("👤 Accounts", callback_data="help_accounts"),
            InlineKeyboardButton("⚙️ Settings", callback_data="help_settings"),
            InlineKeyboardButton("🛡️ Safety", callback_data="help_safety"),
        ],
        [
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ]
    ]

    await update.message.reply_text(
        "❓ *GitroHub — Help*\n\n"
        "Select a category to see commands:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    from database.db import clear_state
    clear_state(telegram_id)

    await update.message.reply_text(
        "❌ *Cancelled — nothing was changed\\.*\n\n"
        "💡 Use /help to see what you can do",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ]])
    )


async def send_private_message(update: Update, telegram_id: int):
    from database.db import get_settings
    settings = get_settings(ADMIN_ID) if ADMIN_ID else {}
    custom_msg = settings.get("private_message")
    owner = settings.get("private_message_owner", "@GitroHubBot")
    link = settings.get("private_message_link")

    if custom_msg:
        # Replace variables
        import time
        from datetime import datetime
        msg = custom_msg
        msg = msg.replace("{owner}", owner or "")
        msg = msg.replace("{botname}", "GitroHub")
        msg = msg.replace("{date}", datetime.now().strftime("%b %d %Y"))
        msg = msg.replace("{link}", link or "")
        await update.message.reply_text(msg)
        return

    text = (
        "🔒 *GitroHub — Private Bot*\n\n"
        "This bot is privately owned and is\n"
        "not open for public access\\.\n\n"
        f"👤 Owner: {escape_md(owner or 'the owner')}\n\n"
        "📖 *About:*\n"
        "GitroHub is a personal GitHub management\n"
        "bot — commit code, manage repos, upload\n"
        "files \\& handle branches directly from\n"
        "Telegram\\."
    )

    if link:
        text += f"\n\n🔗 {escape_md(link)}"

    text += "\n\n──────────────────────\n⚙️ Powered by @GitroHubBot"

    await update.message.reply_text(text, parse_mode="MarkdownV2")


def escape_md(text: str) -> str:
    """Escape special characters for MarkdownV2."""
    if not text:
        return ""
    special = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))
