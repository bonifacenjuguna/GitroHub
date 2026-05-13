from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram import Router

import secrets
from datetime import datetime, timedelta, timezone
from config import settings
from database.pool import cancel_invite, create_invite as db_create_invite, get_all_users, get_bot_stats, get_pending_invites, revoke_user
from utils.formatters import h, panel, time_ago

async def show_users(msg_or_query, telegram_id):
    users = await get_all_users()
    pending = await get_pending_invites(telegram_id)
    lines = ["---", f"  {len(users)} users  ·  {len(pending)} pending invites", "---"]
    kb = []
    for u in users:
        if u["role"] == "admin":
            lines += [f"  👑  Admin (you)", "···"]
            continue
        tg_id = u["telegram_id"]
        active = "✅" if u["is_active"] else "❌"
        last = time_ago(u["last_active"]) if u.get("last_active") else "never"
        lines += [f"  {active}  TG:{tg_id}", f"       Last: {h(last)}","···"]
        kb.append([InlineKeyboardButton(text=f"🔕 Revoke {tg_id}",callback_data=f"user_revoke:{tg_id}")])
    if pending:
        lines += ["---","  PENDING INVITES","···"]
        for inv in pending:
            lines.append(f"  🔗  ...{inv['token'][-8:]}  expires {time_ago(inv['expires_at'])}")
            kb.append([InlineKeyboardButton(text=f"🗑️ Cancel invite",callback_data=f"invite_cancel:{inv['token']}")])
    kb.append([InlineKeyboardButton(text="➕ New Invite",callback_data="user_invite"), InlineKeyboardButton(text="📊 Stats",callback_data="user_stats")])
    kb.append([InlineKeyboardButton(text="🏠 Home",callback_data="home")])
    text = panel("👥  Users", lines)
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def handle_create_invite(query, telegram_id):
    token = f"inv_{secrets.token_urlsafe(20)}"
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.invite_expiry_hours)
    invite = await db_create_invite(token, telegram_id, expires)
    invite_url = f"https://t.me/{settings.bot_username}?start={token}"
    text = panel("🔗  New Invite Link", [
        "---","  Share this link with the person:","---",
        f"  {h(invite_url)}","---",
        f"  ⏳  Expires in {settings.invite_expiry_hours}h","  Single use: Yes",
    ])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="👥 Users",callback_data="users"),
                                       InlineKeyboardButton(text="🗑️ Cancel invite",callback_data=f"invite_cancel:{token}"),
                                   ]]))

async def revoke_user_access(query, admin_id, target_id):
    await revoke_user(target_id)
    await query.answer(f"✅ User {target_id} revoked.", show_alert=True)
    await show_users(query, admin_id)

async def show_usage_stats(query, telegram_id):
    stats = await get_bot_stats()
    lines = ["---",
             f"  👥  Active users    {stats.get('active_users',0)}",
             f"  📁  Total sessions  {stats.get('total_sessions',0)}",
             f"  📝  Commits stored  {stats.get('total_commits',0)}",
             f"  🔔  Notifications   {stats.get('total_notifications',0)}",
    ]
    text = panel("📊  Bot Usage Stats", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👥 Users",callback_data="users"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))

router = Router()
