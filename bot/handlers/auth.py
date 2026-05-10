"""
Auth Handlers — GitroHub v2.0
OAuth login flow, logout, account switching, disconnect.
All account management callbacks.
"""
import logging
import secrets

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

from bot.services.cache import (
    consume_oauth_state, store_oauth_state,
    wipe_user, delete_all_panels,
)
from bot.services.github import (
    build_oauth_url, exchange_oauth_code,
    get_github_user_info,
)
from bot.ui.keyboards import (
    accounts_kb, auth_menu, main_menu,
)
from bot.ui.panel import CTX_ACCOUNT, PanelManager
from config import settings
from database.pool import (
    create_session, create_user, delete_session,
    get_active_session, get_all_sessions,
    get_user, is_authorized, switch_session,
    update_session,
)
from utils.crypto import encrypt
from utils.formatters import h, panel, time_ago, vis_label

logger = logging.getLogger(__name__)
router = Router()


# ── OAuth callback (called from aiohttp webhook server) ───────────────────────

async def handle_oauth_callback(code: str, state: str, bot) -> tuple[bool, str]:
    """
    Called when GitHub redirects back with OAuth code.
    Returns (success, username_or_error).
    """
    telegram_id = await consume_oauth_state(state)
    if not telegram_id:
        logger.warning(f"OAuth state not found or expired: {state}")
        return False, "Invalid or expired authorization link"

    # Exchange code for token
    token_data = await exchange_oauth_code(code)
    if not token_data:
        await bot.send_message(
            telegram_id,
            "<pre>" + panel("❌  Connection Failed", [
                "---",
                "GitHub did not return an access token.",
                "---",
                "Reason:",
                "The authorization code may have",
                "expired or already been used.",
                "---",
                "Fix:",
                "Tap below to try again.",
            ]) + "</pre>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔄 Try Again",
                    callback_data="account_add_retry",
                )
            ]]),
        )
        return False, "No access token"

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")

    # Fetch GitHub user info
    user_info = await get_github_user_info(access_token)
    if not user_info:
        return False, "Could not fetch GitHub profile"

    username = user_info.get("login")
    email = user_info.get("email")
    plan = user_info.get("plan", {}).get("name", "free") if user_info.get("plan") else "free"

    # Ensure user exists in DB
    if not await is_authorized(telegram_id):
        # First time — could be admin
        role = "admin" if telegram_id == settings.admin_id else "member"
        await create_user(telegram_id, role=role)

    # Store encrypted session
    enc_token = encrypt(access_token)
    enc_refresh = encrypt(refresh_token) if refresh_token else None
    await create_session(
        telegram_id, username, enc_token, enc_refresh, email, plan
    )

    # Send success message to Telegram
    text = panel("✅  Connected!", [
        "---",
        f"  👤  {h(username)}",
        f"  📧  {h(email or 'Hidden')}",
        f"  📋  Plan: {h(plan.title())}",
        "---",
        "  🔒  Session saved  ·  AES-256 encrypted",
        "  ✅  Permissions: repo · user · gist",
        "---",
        "Go back to Telegram to continue 🚀",
    ])

    await bot.send_message(
        telegram_id,
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📁 View Repos",
                                  callback_data="repos:0:pushed"),
            InlineKeyboardButton(text="🏠 Dashboard",
                                  callback_data="home"),
        ]]),
    )

    # Unlock the bottom menu
    await bot.send_message(
        telegram_id,
        "✅ GitHub connected! Your menu is now unlocked.",
        reply_markup=main_menu(),
    )

    logger.info(f"✅ OAuth success: {username} ({telegram_id})")
    return True, username


# ── Show accounts ─────────────────────────────────────────────────────────────

async def show_accounts(message: Message, telegram_id: int):
    """Show all connected accounts — callable from menu."""
    sessions = await get_all_sessions(telegram_id)

    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    oauth_url = build_oauth_url(oauth_state, force_reauth=True)

    lines = ["---"]
    if sessions:
        for s in sessions:
            uname = s["github_username"]
            active_mark = "✅" if s["is_active"] else "   "
            status = "(active)" if s["is_active"] else f"({_last_seen(s['last_seen'])})"
            lines.append(f"  {active_mark}  {h(uname)}  {status}")
            if not s["is_active"]:
                lines.append(f"       Plan: {s.get('github_plan', 'free').title()}")
        lines.append("---")
    else:
        lines += ["No accounts connected.", "---"]

    text = panel("👤  GitHub Accounts", lines)

    pm = PanelManager(message.bot)
    await pm.update(
        telegram_id, message.chat.id, CTX_ACCOUNT,
        f"<pre>{text}</pre>",
        accounts_kb(sessions, oauth_url),
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("account_switch:"))
async def cb_switch_account(query: CallbackQuery, telegram_id: int):
    username = query.data.split(":", 1)[1]
    await query.answer(f"Switching to {username}...")

    await switch_session(telegram_id, username)
    session = await get_active_session(telegram_id)

    # Wipe panel cache — new account = fresh panels
    await delete_all_panels(telegram_id)

    repo = session.get("active_repo") or "None"
    branch = session.get("active_branch") or "main"

    text = panel(f"✅  Switched to {h(username)}", [
        "---",
        f"  📁  Repo:    {h(repo.split('/')[-1] if repo != 'None' else 'None')}",
        f"  🌿  Branch:  {h(branch)}",
        "---",
        "  Session restored.",
    ])

    await query.message.edit_text(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📁 My Repos",
                                  callback_data="repos:0:pushed"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home"),
        ]]),
    )


@router.callback_query(F.data.startswith("account_disconnect:"))
async def cb_disconnect(query: CallbackQuery, telegram_id: int):
    username = query.data.split(":", 1)[1]

    text = panel(f"⚠️  Disconnect {h(username)}?", [
        "---",
        "This removes the account from",
        "GitroHub. Your GitHub data is",
        "completely untouched.",
        "---",
        "You can reconnect at any time.",
    ])

    await query.message.edit_text(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"✅ Yes, disconnect",
                callback_data=f"account_disconnect_confirm:{username}",
            ),
            InlineKeyboardButton(text="❌ Cancel",
                                  callback_data="account_back"),
        ]]),
    )
    await query.answer()


@router.callback_query(F.data.startswith("account_disconnect_confirm:"))
async def cb_disconnect_confirm(query: CallbackQuery, telegram_id: int,
                                 session: dict | None):
    username = query.data.split(":", 1)[1]
    await query.answer(f"Disconnecting {username}...")

    await delete_session(telegram_id, username)

    # Wipe all Redis data for this user
    await wipe_user(telegram_id)

    # Check if there are remaining sessions
    remaining = await get_all_sessions(telegram_id)
    active = next((s for s in remaining if s["is_active"]), None)

    if active:
        # Still have other accounts
        text = panel(f"✅  {h(username)} Disconnected", [
            "---",
            f"  Now using: {h(active['github_username'])}",
            "---",
            "  Other accounts are still active.",
        ])
        await query.message.edit_text(
            f"<pre>{text}</pre>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👤 Accounts",
                                      callback_data="account_back"),
                InlineKeyboardButton(text="🏠 Home", callback_data="home"),
            ]]),
        )
    else:
        # No accounts left — full wipe, show connect screen
        text = panel("✅  Disconnected", [
            "---",
            f"  {h(username)} removed.",
            "---",
            "  Connect a GitHub account",
            "  to use GitroHub.",
        ])
        await query.message.edit_text(
            f"<pre>{text}</pre>",
            parse_mode="HTML",
        )
        # Show auth menu
        await query.message.answer(
            "🔒 Connect GitHub to unlock the menu.",
            reply_markup=auth_menu(),
        )


@router.callback_query(F.data == "account_back")
async def cb_account_back(query: CallbackQuery, telegram_id: int):
    await query.answer()
    sessions = await get_all_sessions(telegram_id)

    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    oauth_url = build_oauth_url(oauth_state, force_reauth=True)

    lines = ["---"]
    for s in sessions:
        uname = s["github_username"]
        mark = "✅" if s["is_active"] else "   "
        status = "(active)" if s["is_active"] else f"({_last_seen(s['last_seen'])})"
        lines.append(f"  {mark}  {h(uname)}  {status}")
    lines.append("---")

    text = panel("👤  GitHub Accounts", lines)

    pm = PanelManager(query.bot)
    await pm.from_callback(
        query, CTX_ACCOUNT,
        f"<pre>{text}</pre>",
        accounts_kb(sessions, oauth_url),
    )


@router.callback_query(F.data == "account_add_retry")
async def cb_add_retry(query: CallbackQuery, telegram_id: int):
    await query.answer()
    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    oauth_url = build_oauth_url(oauth_state, force_reauth=True)

    text = panel("➕  Add GitHub Account", [
        "---",
        "GitHub will show you an account",
        "picker — choose a DIFFERENT",
        "account from your current one.",
    ])

    await query.message.edit_text(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔗 Add GitHub Account", url=oauth_url),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
        ]]),
    )


# ── /login command ────────────────────────────────────────────────────────────

@router.message(F.text.in_({"add account", "/login"}))
async def cmd_login(message: Message, telegram_id: int):
    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    oauth_url = build_oauth_url(oauth_state, force_reauth=False)

    text = panel("🔐  Connect GitHub", [
        "---",
        "Tap below to authorize GitroHub",
        "on GitHub.",
        "---",
        "⏳  Waiting for GitHub approval...",
    ])

    await message.answer(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔗 Connect GitHub Account",
                url=oauth_url,
            ),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
        ]]),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _last_seen(dt) -> str:
    if not dt:
        return "never"
    return time_ago(dt)
