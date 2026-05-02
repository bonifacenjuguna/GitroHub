"""Auth handler — GitroHub v1.2"""
import logging
import os
import secrets

import aiohttp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import (
    clear_state, create_session, delete_session,
    get_active_session, get_all_sessions, get_state,
    set_state, switch_session, update_session,
)
from utils.encryption import decrypt, encrypt
from utils.github_helper import h

logger = logging.getLogger(__name__)

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
_WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
GITHUB_REDIRECT_URI = os.environ.get(
    "GITHUB_REDIRECT_URI",
    f"{_WEBHOOK_URL}/auth/github/callback" if _WEBHOOK_URL else ""
)

pending_oauth: dict = {}


def generate_oauth_url(telegram_id: int) -> tuple:
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


async def handle_oauth_callback(code: str, state: str, bot) -> bool:
    if state not in pending_oauth:
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
            "❌ <b>GitHub authorization failed</b>\nGitHub didn't return a token. Try /login again.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 Try again", callback_data="login_start"),
            ]])
        )
        return False

    async with aiohttp.ClientSession() as session:
        resp = await session.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}", "Accept": "application/vnd.github.v3+json"}
        )
        user_data = await resp.json()

    username = user_data.get("login")
    email = user_data.get("email")

    if not username:
        await bot.send_message(telegram_id, "❌ Couldn't fetch GitHub profile. Try /login again.", parse_mode="HTML")
        return False

    enc_token = encrypt(access_token)
    enc_refresh = encrypt(refresh_token) if refresh_token else None
    create_session(telegram_id, username, enc_token, enc_refresh, email)
    clear_state(telegram_id)

    keyboard = [
        [InlineKeyboardButton("📂 Projects", callback_data="projects"),
         InlineKeyboardButton("📦 All Repos", callback_data="repos")],
        [InlineKeyboardButton("➕ New Repo", callback_data="create_repo"),
         InlineKeyboardButton("❓ Help", callback_data="help_back")],
    ]
    await bot.send_message(
        telegram_id,
        f"✅ <b>{h(username)}</b> connected!\n🔒 Session saved permanently.\n\nWelcome to GitroHub 🚀",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return True


async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    url, state = generate_oauth_url(telegram_id)
    set_state(telegram_id, "awaiting_oauth", {"state": state})
    await update.message.reply_text(
        "🔐 <b>Connect your GitHub account</b>\n\n"
        "Tap the button below to authorize GitroHub on GitHub.\n"
        "GitHub will ask for your confirmation — complete it there.\n\n"
        "⏳ Waiting for GitHub approval...",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔗 Connect GitHub Account", url=url),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]])
    )


async def cmd_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session:
        await update.message.reply_text("❌ No active session. Use /login first.", parse_mode="HTML")
        return
    username = session["github_username"]
    await update.message.reply_text(
        f"⚠️ <b>Remove {h(username)}?</b>\n\nThis disconnects the account. Your GitHub data is untouched.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Yes, remove", callback_data=f"confirm_logout_{username}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]])
    )


async def cmd_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_accounts_msg(update.message, telegram_id)


async def cmd_switchaccount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_accounts_msg(update.message, telegram_id)


async def cmd_whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session:
        await update.message.reply_text("❌ Not logged in. Use /login.", parse_mode="HTML")
        return
    from utils.github_helper import get_github_client
    gh = get_github_client(telegram_id)
    try:
        rate = gh.get_rate_limit()
        remaining = rate.core.remaining
        limit = rate.core.limit
        reset_mins = int((rate.core.reset.timestamp() - __import__('time').time()) / 60)
        user = gh.get_user()
        plan = "Pro" if user.plan and user.plan.name != "free" else "Free"
    except Exception:
        remaining, limit, reset_mins, plan = "?", 5000, "?", "?"

    text = (
        f"👤 <b>Current Account</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"GitHub: <code>{h(session['github_username'])}</code>\n"
        f"Email: <code>{h(session.get('github_email') or 'Hidden')}</code>\n"
        f"Plan: {plan}\n\n"
        f"🔐 <b>Session</b>\n"
        f"Token: ✅ Active\n"
        f"Encrypted: ✅ AES-256\n\n"
        f"📊 <b>API Usage</b>\n"
        f"Used: {limit - remaining if isinstance(remaining, int) else '?'} / {limit}\n"
        f"Resets in: {reset_mins} mins"
    )
    await update.message.reply_text(
        text, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Switch Account", callback_data="show_accounts"),
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ]])
    )


# ── Shared display functions (work in both command and callback context) ──────

async def show_accounts_msg(message, telegram_id: int):
    """Send accounts list as a NEW message."""
    sessions = get_all_sessions(telegram_id)
    oauth_url, _ = generate_oauth_url(telegram_id)
    text, keyboard = _build_accounts_content(sessions, oauth_url)
    await message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def show_accounts_edit(query, telegram_id: int):
    """Edit existing message with accounts list."""
    sessions = get_all_sessions(telegram_id)
    oauth_url, _ = generate_oauth_url(telegram_id)
    text, keyboard = _build_accounts_content(sessions, oauth_url)
    await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


def _build_accounts_content(sessions, oauth_url: str):
    if not sessions:
        text = "👤 <b>No accounts connected</b>\n\nConnect your GitHub to get started."
        keyboard = [[InlineKeyboardButton("🔗 Connect GitHub", url=oauth_url)]]
        return text, keyboard

    text = "👤 <b>Connected Accounts</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []
    for s in sessions:
        username = s["github_username"]
        status = "✅ " if s["is_active"] else "   "
        last = "(active)" if s["is_active"] else f"({_time_ago(s['last_seen'])})"
        text += f"{status}<b>{h(username)}</b> {last}\n"
        row = []
        if not s["is_active"]:
            row.append(InlineKeyboardButton("🔄 Switch", callback_data=f"switch_account_{username}"))
        else:
            row.append(InlineKeyboardButton("✅ Active", callback_data="noop"))
        row.append(InlineKeyboardButton("🗑️ Remove", callback_data=f"remove_account_{username}"))
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("🔗 Connect New Account", url=oauth_url)])
    keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data="home")])
    return text, keyboard


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
            return f"{diff.seconds // 60}m ago"
        return f"{hours}h ago"
    elif days == 1:
        return "1 day ago"
    elif days < 7:
        return f"{days} days ago"
    elif days < 30:
        return f"{days // 7}w ago"
    return f"{days // 30}mo ago"
