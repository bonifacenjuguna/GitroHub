import os
import secrets
import logging
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    create_session, get_active_session, get_all_sessions,
    switch_session, delete_session, get_state, set_state, clear_state
)
from utils.encryption import encrypt, decrypt

logger = logging.getLogger(__name__)

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
GITHUB_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "")

# Store pending OAuth states in memory (short-lived)
pending_oauth: dict[str, dict] = {}


def generate_oauth_url(telegram_id: int) -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    pending_oauth[state] = {"telegram_id": telegram_id}
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_REDIRECT_URI}"
        f"&scope=repo,user,delete_repo"
        f"&state={state}"
    )
    return url, state


async def handle_oauth_callback(code: str, state: str,
                                 bot) -> bool:
    """Called by webhook when GitHub redirects back."""
    if state not in pending_oauth:
        logger.warning(f"Unknown OAuth state: {state}")
        return False

    telegram_id = pending_oauth.pop(state)["telegram_id"]

    async with aiohttp.ClientSession() as session:
        resp = await session.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"}
        )
        data = await resp.json()

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    if not access_token:
        await bot.send_message(
            telegram_id,
            "❌ GitHub authorization failed\n"
            "Reason: GitHub didn't return an access token. "
            "This can happen if the authorization was cancelled "
            "or the code expired.\n\n"
            "Fix: Try /login again and complete it promptly.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Try again", callback_data="login_start"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return False

    # Get GitHub user info
    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        user_data = await resp.json()

    username = user_data.get("login")
    email = user_data.get("email")

    if not username:
        await bot.send_message(telegram_id,
            "❌ Couldn't fetch your GitHub profile.\n"
            "Fix: Try /login again.")
        return False

    # Encrypt and store
    enc_token = encrypt(access_token)
    enc_refresh = encrypt(refresh_token) if refresh_token else None
    create_session(telegram_id, username, enc_token, enc_refresh, email)
    clear_state(telegram_id)

    # Check if this is first time or returning
    all_sessions = get_all_sessions(telegram_id)

    keyboard = [
        [
            InlineKeyboardButton("📂 Projects", callback_data="projects"),
            InlineKeyboardButton("📦 All Repos", callback_data="repos"),
        ],
        [
            InlineKeyboardButton("➕ New Repo", callback_data="create_repo"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ]
    ]

    await bot.send_message(
        telegram_id,
        f"✅ *{username}* connected successfully\\!\n"
        f"🔒 Session saved permanently\\.\n\n"
        f"Welcome to GitroHub 🚀",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return True


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    url, state = generate_oauth_url(telegram_id)
    set_state(telegram_id, "awaiting_oauth", {"state": state})

    keyboard = [[
        InlineKeyboardButton("🔗 Connect GitHub Account", url=url),
    ], [
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]

    await update.message.reply_text(
        "🔐 *Connect your GitHub account*\n\n"
        "Tap the button below to authorize GitroHub on GitHub\\.\n"
        "GitHub will ask for your confirmation — complete it there\\.\n\n"
        "⏳ Waiting for GitHub approval\\.\\.\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)

    if not session:
        await update.message.reply_text(
            "❌ No active session found.\nYou're not logged in.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Login", callback_data="login_start")
            ]])
        )
        return

    username = session["github_username"]
    keyboard = [[
        InlineKeyboardButton(f"✅ Yes, remove {username}", callback_data=f"confirm_logout_{username}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]

    await update.message.reply_text(
        f"⚠️ *Remove {username}?*\n\n"
        f"This disconnects the account from this bot\\.\n"
        f"Your GitHub data is completely untouched\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_accounts(update.message, telegram_id)


async def show_accounts(message, telegram_id: int):
    sessions = get_all_sessions(telegram_id)
    oauth_url, state = generate_oauth_url(telegram_id)

    if not sessions:
        await message.reply_text(
            "👤 *No accounts connected*\n\nConnect your GitHub to get started\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Connect GitHub", url=oauth_url)
            ]])
        )
        return

    text = "👤 *Connected Accounts*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []

    for s in sessions:
        username = s["github_username"]
        status = "✅ " if s["is_active"] else "   "
        last = f"(active)" if s["is_active"] else f"({_time_ago(s['last_seen'])})"
        text += f"{status}*{username}* {last}\n"
        keyboard.append([
            InlineKeyboardButton(
                f"🔄 Switch" if not s["is_active"] else "✅ Active",
                callback_data=f"switch_account_{username}"
            ),
            InlineKeyboardButton(
                "🗑️ Remove",
                callback_data=f"remove_account_{username}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("🔗 Connect New Account", url=oauth_url)
    ])
    keyboard.append([
        InlineKeyboardButton("⬅️ Back", callback_data="home"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ])

    await message.reply_text(
        text,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)

    if not session:
        await update.message.reply_text(
            "❌ No active session.\nUse /login to connect GitHub."
        )
        return

    from utils.github_helper import get_github_client
    gh = get_github_client(telegram_id)
    user = gh.get_user()

    # Check API rate limit
    rate = gh.get_rate_limit()
    remaining = rate.core.remaining
    limit = rate.core.limit
    reset_in = int((rate.core.reset.timestamp() -
                    __import__('time').time()) / 60)

    plan = "Pro" if user.plan and user.plan.name != "free" else "Free"

    text = (
        f"👤 *Current Account*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"GitHub:    `{session['github_username']}`\n"
        f"Email:     `{session['github_email'] or 'Hidden'}`\n"
        f"Plan:      {plan}\n"
        f"Joined:    {user.created_at.strftime('%b %Y')}\n\n"
        f"🔐 *Session Status:*\n"
        f"Token:     ✅ Active & valid\n"
        f"Encrypted: ✅ AES\\-256\n"
        f"Last auth: {_time_ago(session['last_seen'])}\n\n"
        f"📊 *API Usage:*\n"
        f"Calls used:  {limit - remaining:,} / {limit:,}\n"
        f"Resets in:   {reset_in} mins"
    )

    keyboard = [[
        InlineKeyboardButton("🔄 Switch Account", callback_data="accounts"),
        InlineKeyboardButton("🗑️ Remove Account",
                             callback_data=f"remove_account_{session['github_username']}")
    ], [
        InlineKeyboardButton("🏠 Home", callback_data="home")
    ]]

    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_switchaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_accounts(update.message, telegram_id)


def _time_ago(dt) -> str:
    if dt is None:
        return "never"
    from datetime import datetime, timezone
    if hasattr(dt, 'tzinfo') and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    days = diff.days
    if days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            mins = diff.seconds // 60
            return f"{mins}m ago"
        return f"{hours}h ago"
    elif days == 1:
        return "1 day ago"
    elif days < 7:
        return f"{days} days ago"
    elif days < 30:
        return f"{days // 7}w ago"
    else:
        return f"{days // 30}mo ago"
