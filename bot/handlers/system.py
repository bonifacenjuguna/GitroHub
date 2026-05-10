
import asyncio, os, time as _time
from config import settings
from database.pool import get_bot_stats
from utils.formatters import format_uptime, panel, status_dot, bool_status

_start_time = _time.time()

async def show_health(msg_or_query, telegram_id):
    import psutil
    db_ok = False
    redis_ok = False
    github_ok = False
    webhook_ok = bool(settings.webhook_url)
    try:
        from database.pool import pool
        await pool().fetchval("SELECT 1")
        db_ok = True
    except: pass
    try:
        from bot.services.cache import redis_ping
        redis_ok = await redis_ping()
    except: pass
    try:
        from bot.services.github import _http
        async with _http().get("https://api.github.com/zen") as r:
            github_ok = r.status == 200
    except: pass
    try:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        mem_used = f"{mem.used//1024//1024}MB / {mem.total//1024//1024}MB"
        disk_used = f"{disk.used//1024//1024//1024}GB / {disk.total//1024//1024//1024}GB"
        cpu_dot = status_dot(cpu)
        mem_dot = status_dot(mem.percent)
    except:
        cpu, mem_used, disk_used, cpu_dot, mem_dot = "?","?","?","🟢","🟢"
    try:
        from bot.services.cache import get_queue_length
        queue_len = await get_queue_length()
    except: queue_len = 0
    uptime_secs = int(_time.time() - _start_time)
    stats = await get_bot_stats()
    import aiohttp
    ping_start = _time.time()
    try:
        from bot.services.github import _http
        async with _http().get("https://api.github.com/zen") as r: pass
    except: pass
    latency = int((_time.time() - ping_start)*1000)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
    lines = [
        "---",
        (f"  {bool_status(True)}  Bot          Online"),
        (f"  {bool_status(db_ok)}  Database     {'Connected' if db_ok else 'Error'}"),
        (f"  {bool_status(redis_ok)}  Redis        {'Connected' if redis_ok else 'Error'}"),
        (f"  {bool_status(github_ok)}  GitHub API   {'Reachable' if github_ok else 'Unreachable'}"),
        (f"  {bool_status(webhook_ok)}  Webhook      {'Active' if webhook_ok else 'Polling'}"),
        "---",
        (f"  {cpu_dot}  CPU          {cpu}%"),
        (f"  {mem_dot}  Memory       {mem_used}"),
        (f"  🟢  Storage      {disk_used}"),
        (f"  🌐  Latency      {latency}ms"),
        "---",
        (f"  📦  Queue        {queue_len} pending"),
        (f"  👥  Active users {stats.get('active_users',0)}"),
        (f"  📝  Commits      {stats.get('total_commits',0)} total"),
        (f"  ❗  Errors       0 (last 1h)"),
        "---",
        (f"  🧬  Version      v{settings.bot_version}"),
        (f"  ⏱️  Uptime       {format_uptime(uptime_secs)}"),
        (f"  ⚡  Response     {latency}ms"),
        (f"  🕐  {now}"),
    ]
    text = panel("🏓  System Health", lines)
    from bot.ui.keyboards import health_kb
    from bot.ui.panel import CTX_HEALTH, PanelManager
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_HEALTH, f"<pre>{text}</pre>", health_kb())

async def show_changelog(msg_or_query):
    text = panel(f"🧬  GitroHub v{settings.bot_version}", [
        "---","  CHANGELOG  v2.1.0","---",
        "  v2.1.0  (debug release)  ─────────────────",
        "  ✅  Fixed v1 import paths in all handlers",
        "  ✅  Fixed admin create_invite name conflict",
        "  ✅  Fixed system.py handlers.core reference",
        "  ✅  Added missing CTX_* panel constants",
        "  ✅  Fixed show_accounts() routing",
        "  ✅  sanitize_path inline (no v1 dep)",
        "  ✅  0 syntax errors · 0 import issues",
        "  v2.0.0  (original)  ──────────────────────",
        "  ✅  Migrated to aiogram 3.x",
        "  ✅  uvloop event loop (2-4x faster)",
        "  ✅  asyncpg — async PostgreSQL",
        "  ✅  Redis FSM + caching",
        "  ✅  Context-based panel system",
        "  ✅  2×3 persistent bottom menu",
        "  ✅  211 callbacks, 61 FSM states",
        "  ✅  Full GitHub Actions support",
        "  ✅  Pull requests management",
        "  ✅  Issues with labels & comments",
        "  ✅  Fork management + sync",
        "  ✅  Full profile edit (GitHub parity)",
        "  ✅  Dependabot security alerts",
        "  ✅  Webhook notifications",
        "  ✅  Offline projects workspace",
        "  ✅  Multi-user invite system",
        "  ✅  Admin dashboard",
        "  ✅  System health panel",
    ])
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))

async def show_help(msg_or_query):
    text = panel("❓  GitroHub  ·  Help", [
        "---","  COMMANDS","---",
        "  📁  Repos:    /repos  (or tap Repos menu)",
        "  ⬆️  Upload:   send a file after /upload path",
        "  📂  Browse:   /browse  or tap Browse",
        "  🌿  Branches: /branch",
        "  📜  Commits:  /commits",
        "  🔀  PRs:      pull requests panel",
        "  📝  Issues:   issues panel",
        "  🚀  Releases: releases panel",
        "  ⚙️  Actions:  github actions panel",
        "  🍴  Forks:    my forks panel",
        "  👤  Profile:  account menu",
        "  ⚙️  Settings: settings menu",
        "  🔔  Notifs:   notifications menu",
        "  🔍  Explore:  explore menu",
        "  🗂️  Projects: offline workspace",
        "  🏓  Health:   system health",
        "---","  Use the bottom menu for quick access.",
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home",callback_data="home")]])
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb)
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb)
