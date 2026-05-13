from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram import Router

from bot.services.github import get_dependabot_alerts, get_repo_webhooks, create_repo_webhook, delete_repo_webhook
from bot.ui.keyboards import security_kb
from bot.ui.panel import PanelManager
from utils.formatters import h, panel

async def show_security(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    text = panel(f"🛡️  Security  ·  {h(repo_name.split('/')[-1])}", ["---","  Choose a security feature:","---"])
    await pm.update(telegram_id, chat_id, "security", f"<pre>{text}</pre>", security_kb(repo_name))

async def show_dependabot_alerts(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    alerts = await get_dependabot_alerts(session, telegram_id, repo_name)
    severity_icons = {"critical":"🔴","high":"🔴","medium":"🟡","low":"🟢","info":"⚪"}
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  {len(alerts)} alerts", "---"]
    if not alerts: lines.append("  ✅  No Dependabot alerts. All clear!")
    for a in alerts:
        icon = severity_icons.get(a["severity"].lower(),"⚪")
        lines += [f"  {icon}  {a['severity'].upper()}", f"       {h(a['package'])}", f"       {h(a['summary'][:50])}", f"       CVE: {h(a.get('cve_id','N/A'))}","···"]
    text = panel("🛡️  Dependabot Alerts", lines)
    await pm.update(telegram_id, chat_id, "security", f"<pre>{text}</pre>",
                    InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🌐 View on GitHub",url=f"https://github.com/{repo_name}/security/dependabot"),
                        InlineKeyboardButton(text="⬅️ Back",callback_data=f"security:{repo_name}"),
                    ]]))

async def show_webhooks(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    hooks = await get_repo_webhooks(session, telegram_id, repo_name)
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  {len(hooks)} webhooks", "---"]
    kb = []
    for hook in hooks:
        active = "🟢" if hook["active"] else "🔴"
        url_short = hook["url"][:40] if hook["url"] else "?"
        lines += [f"  {active}  {h(url_short)}", f"       Events: {h(', '.join(hook['events'][:3]))}","···"]
        kb.append([InlineKeyboardButton(text=f"🗑️ Delete #{hook['id']}",callback_data=f"webhook_delete:{repo_name}:{hook['id']}")])
    if not hooks: lines.append("  No webhooks configured.")
    kb.append([InlineKeyboardButton(text="➕ Add webhook",callback_data=f"webhook_add:{repo_name}")])
    kb.append([InlineKeyboardButton(text="⬅️ Back",callback_data=f"security:{repo_name}"), InlineKeyboardButton(text="🏠 Home",callback_data="home")])
    text = panel("🔗  Webhooks", lines)
    await pm.update(telegram_id, chat_id, "security", f"<pre>{text}</pre>", InlineKeyboardMarkup(inline_keyboard=kb))

router = Router()
