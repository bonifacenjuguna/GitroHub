
from bot.services.cache import cache_get, cache_set
from bot.states.flow import SettingsFlow
from bot.ui.keyboards import notifs_kb, notifs_settings_kb
from bot.ui.panel import CTX_NOTIFICATIONS, PanelManager
from database.pool import (count_unread, get_notifications, get_settings, mark_notifications_read, update_settings)
from utils.formatters import notif_icon, time_ago

def _dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_notifications(msg_or_query, session, telegram_id, unread_only=False, page=0):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    per_page = 8
    notifs = await get_notifications(telegram_id, unread_only, per_page, page*per_page)
    total_unread = await count_unread(telegram_id)
    total = await count_total(telegram_id)
    lines = ["---", f"  {total} total  ·  {total_unread} unread", "---"]
    kb_rows = []
    prev_day = None
    for n in notifs:
        dt = _dt(str(n["created_at"]))
        day_label = dt.strftime("%A") if dt else "Unknown"
        if day_label != prev_day:
            lines += [f"  {day_label.upper()}","···"]
            prev_day = day_label
        icon = notif_icon(n["event_type"])
        read_marker = "🔵 " if not n["is_read"] else "   "
        repo = n.get("repo_name","").split("/")[-1] if n.get("repo_name") else ""
        lines += [f"  {read_marker}{icon}  {h(repo)}", f"       {h(n['title'][:45])}", f"       {h(time_ago(dt))}","···"]
        kb_rows.append([InlineKeyboardButton(text=f"{icon} {n['title'][:40]}", callback_data=f"notif_view:{n['id']}")])
    if not notifs: lines.append("  No notifications yet.")
    text = panel("🔔  Notifications", lines)
    full_kb = InlineKeyboardMarkup(inline_keyboard=kb_rows + notifs_kb(page, total, per_page, total_unread > 0).inline_keyboard)
    await pm.update(telegram_id, chat_id, CTX_NOTIFICATIONS, f"<pre>{text}</pre>", full_kb)

async def count_total(telegram_id):
    from database.pool import pool
    return await pool().fetchval("SELECT COUNT(*) FROM notifications WHERE telegram_id=$1", telegram_id) or 0

async def show_notif_settings(msg_or_query, telegram_id):
    s = await get_settings(telegram_id)
    text = panel("⚙️  Notification Settings", ["---", "  Toggle each event type:", "---"])
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    quiet_status = f"{'✅ Enabled' if s.get('quiet_hours_enabled') else '🔕 Disabled'}  {s.get('quiet_from','22:00')} — {s.get('quiet_until','08:00')}"
    lines = ["---"]
    events = [("⭐ Stars","notif_stars"),("🔀 Pull requests","notif_pulls"),("📝 Issues","notif_issues"),
              ("❌ Workflow fail","notif_workflow_fail"),("✅ Workflow pass","notif_workflow_pass"),
              ("🚀 Releases","notif_releases"),("🍴 Forks","notif_forks"),("👤 Followers","notif_followers"),
              ("🛡️ Security","notif_security"),("💬 Comments","notif_comments")]
    for label, key in events:
        status = "✅  On" if s.get(key,False) else "🔕  Off"
        lines.append(f"  {status}  {label}")
    lines += ["---",f"  ⏰  Quiet hours: {quiet_status}"]
    text = panel("⚙️  Notification Settings", lines)
    await pm.update(telegram_id, chat_id, CTX_NOTIFICATIONS, f"<pre>{text}</pre>", notifs_settings_kb(s))

async def setup_quiet_hours(query, state, telegram_id):
    await state.set_state(SettingsFlow.setting_quiet_from)
    text = panel("⏰  Quiet Hours", ["---","  Type start time (24hr format):","  e.g.  22:00"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="notifs_settings")]]))

@router.message(SettingsFlow.setting_quiet_from)
async def quiet_from_received(message, state, telegram_id):
    await state.update_data(quiet_from=message.text.strip())
    await state.set_state(SettingsFlow.setting_quiet_until)
    await message.answer("<pre>" + panel("⏰  Quiet Until",["---","  Type end time:","  e.g.  08:00"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="notifs_settings")]]))

@router.message(SettingsFlow.setting_quiet_until)
async def quiet_until_received(message, state, telegram_id):
    data = await state.get_data()
    await state.clear()
    await update_settings(telegram_id, quiet_from=data["quiet_from"], quiet_until=message.text.strip(), quiet_hours_enabled=True)
    await message.answer(f"✅ Quiet hours set: {data['quiet_from']} — {message.text.strip()}",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data="notifs_settings")]]))

async def start_mute_repo(msg_or_query, state, session):
    await state.set_state(SettingsFlow.setting_quiet_from)  # reuse state
    repo = session.get("active_repo","") if session else ""
    text = panel("🔕  Mute Repository", ["---", f"  Current: {h(repo)}", "---", "  Type repo name to mute:","  e.g.  myproject"])
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                      reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="notifs_settings")]]))
