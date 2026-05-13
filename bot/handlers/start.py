from typing import Optional, Any
"""
Start & Home Handlers — GitroHub v2.0
/start, /home, menu button routing, onboarding flow.
"""
import asyncio
import logging
import secrets
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup, Message,
)

from bot.services.cache import (
    get_panel, set_panel, set_state, store_oauth_state, wipe_user,
)
from bot.services.github import (
    build_oauth_url, get_profile, get_rate_limit_info,
)
from bot.ui.keyboards import (
    auth_menu, dashboard_kb, main_menu,
    repos_submenu, account_submenu, settings_submenu,
    notifs_submenu, more_submenu, explore_submenu,
    cancel_kb,
)
from bot.ui.panel import PanelManager, CTX_DASHBOARD
from config import settings
from database.pool import (
    count_unread, get_active_session, get_all_sessions,
    get_commits as db_get_commits,
)
from utils.formatters import h, panel, time_ago, vis_label

logger = logging.getLogger(__name__)
router = Router()


# ── /start ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext,
                    session: Optional[dict], telegram_id: int,
                    is_admin: bool):
    pm = PanelManager(message.bot)

    # Check for invite token in deep link
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and args[1].startswith("inv_"):
        await _handle_invite_link(message, args[1], telegram_id)
        return

    if not session:
        await _show_connect_screen(message, telegram_id)
        return

    await _show_dashboard(message, session, telegram_id, pm, is_new_session=False)


async def _show_connect_screen(message: Message, telegram_id: int):
    """First-time or logged-out start screen."""
    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    oauth_url = build_oauth_url(oauth_state, force_reauth=False)

    text = panel("🤖  GitroHub", [
        "---",
        "Your GitHub lives here now.",
        "Manage repos, commit code,",
        "upload files, handle branches",
        "— all without leaving Telegram.",
        "---",
        "  Secure  ·  Fast  ·  Always in sync",
        "---",
        "Tap below to connect your",
        "GitHub account 👇",
    ])

    await message.answer(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔗 Connect GitHub Account",
                url=oauth_url,
            )
        ]]),
    )
    # Show locked bottom menu hint
    await message.answer(
        "🔒 Connect GitHub to unlock the full menu.",
        reply_markup=auth_menu(),
    )


async def _show_dashboard(message_or_event, session: dict,
                           telegram_id: int, pm: PanelManager,
                           is_new_session: bool = False):
    """Main dashboard — shown on /start for returning users."""
    username = session["github_username"]
    repo = session.get("active_repo") or ""
    branch = session.get("active_branch") or "main"
    recent = session.get("recent_repos") or []
    pinned = session.get("pinned_repos") or []

    # Fetch unread count + last activity in parallel
    unread, rate = await asyncio.gather(
        count_unread(telegram_id),
        get_rate_limit_info(session, telegram_id),
    )

    # Last activity — most recent commit across active repo
    last_commit_line = ""
    if repo:
        try:
            from database.pool import pool
            row = await pool().fetchrow("""
                SELECT message FROM commit_messages
                WHERE telegram_id = $1
                ORDER BY created_at DESC LIMIT 1
            """, telegram_id)
            if row:
                msg = row["message"][:45]
                last_commit_line = f'  💬  "{h(msg)}"'
        except Exception:
            pass

    lines = ["---"]

    if is_new_session:
        lines += [f"  Welcome, {h(username)}! 🎉", "---"]
    else:
        lines += [f"  Hey {h(username)} 👋", "---"]

    if last_commit_line:
        lines += [
            "  LAST ACTIVITY",
            "···",
            f"  📁  {h(repo.split('/')[-1]) if repo else 'No repo yet'}",
            last_commit_line,
            "---",
        ]

    if repo:
        lines += [
            "  CURRENT REPOSITORY",
            "···",
            f"  📁  {h(repo.split('/')[-1])}",
            f"  🌿  {h(branch)}",
            "---",
        ]

    # At a glance
    glance_lines = []
    if unread > 0:
        glance_lines.append(f"  🔔  {unread} unread notifications")
    if rate:
        remaining = rate.get("remaining", "?")
        limit = rate.get("limit", 5000)
        glance_lines.append(f"  🛡️  API  {remaining} / {limit}")

    if glance_lines:
        lines += ["  AT A GLANCE", "···"] + glance_lines

    if pinned:
        lines += ["---", "  📌  PINNED"]
        lines += ["···"]
        for r in pinned[:4]:
            lines.append(f"  ⭐  {h(r.split('/')[-1])}")

    if recent:
        lines += ["---", "  ⏱️  RECENT"]
        lines += ["···"]
        for i, r in enumerate(recent[:3], 1):
            lines.append(f"  {i}.  {h(r.split('/')[-1])}")

    text = panel(f"🤖  GitroHub", lines)

    kb = dashboard_kb(has_repo=bool(repo), unread_notifs=unread)

    chat_id = (message_or_event.chat.id
               if isinstance(message_or_event, Message)
               else message_or_event.message.chat.id)

    await pm.update(
        telegram_id, chat_id, CTX_DASHBOARD,
        f"<pre>{text}</pre>", kb,
    )

    # Set persistent bottom menu
    if isinstance(message_or_event, Message):
        await message_or_event.answer(
            "✅ Ready.", reply_markup=main_menu()
        )


# ── Invite link handler ───────────────────────────────────────────────────────

async def _handle_invite_link(message: Message, token: str, telegram_id: int):
    from database.pool import get_invite, use_invite, create_user
    from datetime import datetime, timezone

    invite = await get_invite(token)
    if not invite:
        await message.answer(
            "❌ This invite link is invalid or has already been used.",
            reply_markup=auth_menu(),
        )
        return

    if invite["is_used"]:
        await message.answer(
            "❌ This invite link has already been used.",
            reply_markup=auth_menu(),
        )
        return

    expires = invite["expires_at"]
    if hasattr(expires, "tzinfo") and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        await message.answer(
            "❌ This invite link has expired.",
            reply_markup=auth_menu(),
        )
        return

    # Valid invite — register user and show connect screen
    await create_user(telegram_id, role="member",
                       invited_by=invite["created_by"],
                       invite_token=token)
    await use_invite(token, telegram_id)

    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    oauth_url = build_oauth_url(oauth_state, force_reauth=False)

    from database.pool import get_user as db_get_user
    inviter = await db_get_user(invite["created_by"])
    inviter_label = "the bot owner"

    text = panel("🤖  GitroHub  —  You're Invited!", [
        "---",
        f"  Invited by {inviter_label}",
        "---",
        "Connect your GitHub account",
        "to get started 👇",
    ])

    await message.answer(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔗 Connect GitHub Account",
                url=oauth_url,
            )
        ]]),
    )
    await message.answer("🔒 Connect GitHub to unlock the menu.",
                          reply_markup=auth_menu())


# ── Home callback ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "home")
async def cb_home(query: CallbackQuery, session: Optional[dict],
                   telegram_id: int, is_admin: bool):
    pm = PanelManager(query.bot)
    await query.answer()

    if not session:
        await _show_connect_screen(query.message, telegram_id)
        return

    await _show_dashboard(query, session, telegram_id, pm)


# ── Cancel ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "cancel")
async def cb_cancel(query: CallbackQuery, state: FSMContext,
                     session: Optional[dict], telegram_id: int):
    await state.clear()
    await query.answer("Cancelled.")

    text = panel("❌  Cancelled", [
        "---",
        "Nothing was changed.",
        "---",
        "Use the menu below to continue.",
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
        InlineKeyboardButton(text="📁 Repos", callback_data="repos:0:pushed"),
    ]])

    try:
        await query.message.edit_text(
            f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb
        )
    except Exception:
        await query.message.answer(
            f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb
        )


@router.callback_query(F.data == "noop")
async def cb_noop(query: CallbackQuery):
    await query.answer()


# ── Bottom menu routing ───────────────────────────────────────────────────────

@router.message(F.text == "📁 Repos")
async def menu_repos(message: Message, session: Optional[dict], telegram_id: int):
    if not session:
        await message.answer("Connect your GitHub account first.",
                              reply_markup=auth_menu())
        return
    await message.answer("📁 Repos", reply_markup=repos_submenu())


@router.message(F.text == "👤 Account")
async def menu_account(message: Message, session: Optional[dict], telegram_id: int):
    if not session:
        await message.answer("Connect your GitHub account first.",
                              reply_markup=auth_menu())
        return
    await message.answer("👤 Account", reply_markup=account_submenu())


@router.message(F.text == "🔍 Explore")
async def menu_explore(message: Message, session: Optional[dict], telegram_id: int):
    if not session:
        await message.answer("Connect your GitHub account first.",
                              reply_markup=auth_menu())
        return
    await message.answer("🔍 Explore", reply_markup=explore_submenu())


@router.message(F.text == "⚙️ Settings")
async def menu_settings(message: Message, session: Optional[dict], telegram_id: int):
    if not session:
        await message.answer("Connect your GitHub account first.",
                              reply_markup=auth_menu())
        return
    await message.answer("⚙️ Settings", reply_markup=settings_submenu())


@router.message(F.text == "🔔 Notifs")
async def menu_notifs(message: Message, session: Optional[dict], telegram_id: int):
    if not session:
        await message.answer("Connect your GitHub account first.",
                              reply_markup=auth_menu())
        return
    await message.answer("🔔 Notifications", reply_markup=notifs_submenu())


@router.message(F.text == "🗂️ More")
async def menu_more(message: Message, session: Optional[dict],
                     telegram_id: int, is_admin: bool):
    if not session:
        await message.answer("Connect your GitHub account first.",
                              reply_markup=auth_menu())
        return
    await message.answer("🗂️ More", reply_markup=more_submenu())


@router.message(F.text == "⬅️ Back")
async def menu_back(message: Message):
    await message.answer("↩️", reply_markup=main_menu())


@router.message(F.text == "🏠 Home")
async def menu_home(message: Message, session: Optional[dict],
                     telegram_id: int, is_admin: bool):
    pm = PanelManager(message.bot)
    if not session:
        await _show_connect_screen(message, telegram_id)
        return
    await _show_dashboard(message, session, telegram_id, pm)


# ── Connect GitHub (bottom menu) ──────────────────────────────────────────────

@router.message(F.text == "🔗 Connect GitHub")
async def menu_connect(message: Message, telegram_id: int):
    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    oauth_url = build_oauth_url(oauth_state, force_reauth=False)

    await message.answer(
        "🔗 Tap below to connect your GitHub account:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔗 Connect GitHub Account", url=oauth_url)
        ]]),
    )


# ── Submenu routing ───────────────────────────────────────────────────────────

@router.message(F.text == "📋 My Repos")
async def submenu_my_repos(message: Message, session: Optional[dict],
                            telegram_id: int):
    if not session:
        return
    from bot.handlers.repos import show_repos_panel
    await show_repos_panel(message, session, telegram_id, page=0, sort="pushed")


@router.message(F.text == "➕ New Repository")
async def submenu_new_repo(message: Message, state: FSMContext,
                            session: Optional[dict], telegram_id: int):
    if not session:
        return
    from bot.handlers.repos import start_create_repo
    await start_create_repo(message, state)


@router.message(F.text == "🍴 My Forks")
async def submenu_my_forks(message: Message, session: Optional[dict],
                            telegram_id: int):
    if not session:
        return
    from bot.handlers.forks import show_forks
    await show_forks(message, session, telegram_id)


@router.message(F.text == "⭐ Starred")
async def submenu_starred(message: Message, session: Optional[dict],
                           telegram_id: int):
    if not session:
        return
    from bot.handlers.explore import show_starred
    await show_starred(message, session, telegram_id)


@router.message(F.text == "👤 My Profile")
async def submenu_profile(message: Message, session: Optional[dict],
                           telegram_id: int):
    if not session:
        return
    from bot.handlers.account import show_profile
    await show_profile(message, session, telegram_id)


@router.message(F.text == "🔄 Switch Account")
async def submenu_switch(message: Message, session: Optional[dict],
                          telegram_id: int):
    if not session:
        return
    from bot.handlers.account import show_accounts
    await show_accounts(message, telegram_id)


@router.message(F.text == "➕ Add Account")
async def submenu_add_account(message: Message, telegram_id: int):
    oauth_state = secrets.token_urlsafe(32)
    await store_oauth_state(oauth_state, telegram_id)
    # force_reauth=True forces GitHub account picker
    oauth_url = build_oauth_url(oauth_state, force_reauth=True)

    text = panel("➕  Add GitHub Account", [
        "---",
        "You will be asked to sign into",
        "GitHub — use a DIFFERENT account",
        "from your current one.",
        "---",
        "GitHub will show you an account",
        "picker to choose which account",
        "to authorize.",
    ])

    await message.answer(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔗 Add GitHub Account",
                url=oauth_url,
            )
        ]]),
    )


@router.message(F.text == "🚪 Disconnect")
async def submenu_disconnect(message: Message, session: Optional[dict],
                              telegram_id: int):
    if not session:
        return
    uname = session["github_username"]
    text = panel("🚪  Disconnect Account", [
        "---",
        f"  Disconnect  {h(uname)}?",
        "---",
        "This removes the account from",
        "GitroHub. Your GitHub data is",
        "completely untouched.",
    ])
    await message.answer(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"✅ Yes, disconnect {uname}",
                callback_data=f"account_disconnect:{uname}",
            ),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
        ]]),
    )


@router.message(F.text == "👥 Organizations")
async def submenu_orgs(message: Message, session: Optional[dict],
                        telegram_id: int):
    if not session:
        return
    from bot.handlers.account import show_orgs
    await show_orgs(message, session, telegram_id)


@router.message(F.text == "📋 All Notifications")
async def submenu_all_notifs(message: Message, session: Optional[dict],
                              telegram_id: int):
    if not session:
        return
    from bot.handlers.notifications import show_notifications
    await show_notifications(message, session, telegram_id, unread_only=False)


@router.message(F.text == "🔵 Unread")
async def submenu_unread(message: Message, session: Optional[dict],
                          telegram_id: int):
    if not session:
        return
    from bot.handlers.notifications import show_notifications
    await show_notifications(message, session, telegram_id, unread_only=True)


@router.message(F.text == "⚙️ Notif Settings")
async def submenu_notif_settings(message: Message, session: Optional[dict],
                                  telegram_id: int):
    if not session:
        return
    from bot.handlers.notifications import show_notif_settings
    await show_notif_settings(message, telegram_id)


@router.message(F.text == "✅ Mark All Read")
async def submenu_mark_read(message: Message, session: Optional[dict],
                             telegram_id: int):
    if not session:
        return
    from database.pool import mark_notifications_read
    await mark_notifications_read(telegram_id)
    await message.answer("✅ All notifications marked as read.",
                          reply_markup=notifs_submenu())


@router.message(F.text == "🔕 Mute Repo")
async def submenu_mute_repo(message: Message, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    if not session:
        return
    from bot.handlers.notifications import start_mute_repo
    await start_mute_repo(message, state, session)


@router.message(F.text == "🗂️ Projects")
async def submenu_projects(message: Message, session: Optional[dict],
                            telegram_id: int):
    if not session:
        return
    from bot.handlers.projects import show_projects
    await show_projects(message, telegram_id)


@router.message(F.text == "🏓 Health")
async def submenu_health(message: Message, telegram_id: int,
                          is_admin: bool):
    from bot.handlers.system import show_health
    await show_health(message, telegram_id)


@router.message(F.text == "🧬 What's New")
async def submenu_whatsnew(message: Message):
    from bot.handlers.system import show_changelog
    await show_changelog(message)


@router.message(F.text == "❓ Help")
async def submenu_help(message: Message):
    from bot.handlers.system import show_help
    await show_help(message)


@router.message(F.text == "👥 Users")
async def submenu_users(message: Message, telegram_id: int, is_admin: bool):
    if not is_admin:
        await message.answer("❌ Admin only.")
        return
    from bot.handlers.admin import show_users
    await show_users(message, telegram_id)


@router.message(F.text == "🔍 Search Repos")
async def submenu_search(message: Message, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    if not session:
        return
    from bot.handlers.explore import start_search
    await start_search(message, state)


@router.message(F.text == "⬇️ Download by URL")
async def submenu_download_url(message: Message, state: FSMContext,
                                session: Optional[dict], telegram_id: int):
    if not session:
        return
    from bot.handlers.explore import start_download_url
    await start_download_url(message, state)


@router.message(F.text == "👤 Find User")
async def submenu_find_user(message: Message, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    if not session:
        return
    from bot.handlers.explore import start_find_user
    await start_find_user(message, state)


@router.message(F.text == "📈 Trending")
async def submenu_trending(message: Message, session: Optional[dict],
                            telegram_id: int):
    if not session:
        return
    from bot.handlers.explore import show_trending
    await show_trending(message, session, telegram_id)


@router.message(F.text == "🔎 Search Code")
async def submenu_search_code(message: Message, state: FSMContext,
                               session: Optional[dict], telegram_id: int):
    if not session:
        return
    from bot.handlers.explore import start_search_code
    await start_search_code(message, state, session)


@router.message(F.text == "🔔 Notifications")
async def submenu_notif_settings_menu(message: Message, session: Optional[dict],
                                       telegram_id: int):
    if not session:
        return
    from bot.handlers.notifications import show_notif_settings
    await show_notif_settings(message, telegram_id)


@router.message(F.text == "🎨 Display")
async def submenu_display(message: Message, session: Optional[dict],
                           telegram_id: int):
    if not session:
        return
    from bot.handlers.settings import show_display_settings
    await show_display_settings(message, telegram_id)


@router.message(F.text == "⌨️ Shortcuts")
async def submenu_shortcuts(message: Message, session: Optional[dict],
                             telegram_id: int):
    if not session:
        return
    from bot.handlers.settings import show_aliases
    await show_aliases(message, session, telegram_id)


@router.message(F.text == "💬 Private Msg")
async def submenu_private_msg(message: Message, session: Optional[dict],
                               telegram_id: int):
    if not session:
        return
    from bot.handlers.settings import show_private_msg
    await show_private_msg(message, telegram_id)


@router.message(F.text == "↩️ Reset All")
async def submenu_reset(message: Message, telegram_id: int):
    text = panel("↩️  Reset All Settings", [
        "---",
        "This will reset all settings",
        "to their defaults.",
        "---",
        "Your GitHub data and sessions",
        "will NOT be affected.",
    ])
    await message.answer(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yes, reset all",
                                  callback_data="settings_reset_confirm"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
        ]]),
    )
