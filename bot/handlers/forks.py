
from bot.services.github import get_my_forks, get_repo_forks, fork_repo, sync_fork, create_pull
from bot.states.flow import PullFlow
from bot.ui.keyboards import forks_kb, fork_detail_kb
from bot.ui.panel import CTX_FORKS, PanelManager
from utils.formatters import time_ago

def _dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_forks(msg_or_query, session, telegram_id):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    forks = await get_my_forks(session, telegram_id)
    lines = ["---", f"  {len(forks)} forks", "---"]
    for fork in forks:
        pushed = time_ago(_dt(fork["pushed_at"]))
        lines += [f"  🍴  {h(fork['full_name'])}", f"       From: {h(fork['parent_full_name'])}", f"       {h(pushed)}", "···"]
    if not forks: lines.append("  No forks yet.")
    text = panel("🍴  My Forks", lines)
    await pm.update(telegram_id, chat_id, CTX_FORKS, f"<pre>{text}</pre>", forks_kb(forks))

async def show_fork_detail(msg_or_query, session, telegram_id, fork_name):
    forks = await get_my_forks(session, telegram_id)
    fork = next((f for f in forks if f["full_name"]==fork_name), None)
    if not fork:
        await msg_or_query.message.answer("❌ Fork not found.")
        return
    parent = fork.get("parent_full_name","")
    lines = ["---", f"  {h(fork_name)}", "---", f"  🍴  Forked from: {h(parent)}", f"  🕐  {h(time_ago(_dt(fork['pushed_at'])))}"]
    text = panel("🍴  Fork Detail", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_FORKS, f"<pre>{text}</pre>", fork_detail_kb(fork_name, parent))

async def show_fork_options(query, session, telegram_id, repo_name):
    from bot.services.github import get_orgs
    orgs = await get_orgs(session, telegram_id)
    lines = ["---", f"  Fork: {h(repo_name)}", "---", "  Where should I fork it?"]
    kb = [[InlineKeyboardButton(text="👤 My personal account", callback_data=f"fork_to_personal:{repo_name}")]]
    for org in orgs[:5]:
        kb.append([InlineKeyboardButton(text=f"🏢 {org['login']}", callback_data=f"fork_to_org:{repo_name}:{org['login']}")])
    kb.append([InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])
    text = panel("🍴  Fork Repository", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def do_fork_repo(query, session, telegram_id, repo_name, org=None):
    try: await query.message.edit_text("<pre>⏳  Forking...</pre>", parse_mode="HTML")
    except: pass
    result = await fork_repo(session, telegram_id, repo_name, organization=org)
    if "error" in result:
        await query.message.edit_text(f"❌ Fork failed (error {result['error']}).")
        return
    fork_name = result["full_name"]
    text = panel("✅  Fork Created!", ["---", f"  📁  {h(fork_name)}", f"  🍴  From: {h(repo_name)}", "---", "  🟢  In sync with upstream"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="📂 Open Fork",callback_data=f"repo_open:{fork_name}"),
                                       InlineKeyboardButton(text="🔄 Sync Fork",callback_data=f"fork_sync:{fork_name}"),
                                   ],[InlineKeyboardButton(text="🍴 My Forks",callback_data="forks"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))

async def do_sync_fork(query, session, telegram_id, repo_name):
    try: await query.message.edit_text("<pre>🔄  Syncing with upstream...</pre>", parse_mode="HTML")
    except: pass
    forks = await get_my_forks(session, telegram_id)
    fork = next((f for f in forks if f["full_name"]==repo_name), None)
    branch = fork.get("default_branch","main") if fork else "main"
    result = await sync_fork(session, telegram_id, repo_name, branch)
    if "error" in result:
        await query.message.edit_text(f"❌ Sync failed. {h(result.get('message',''))}")
        return
    text = panel("✅  Fork Synced", ["---", f"  {h(repo_name)}", "---", "  🟢  Now in sync with upstream"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Browse",callback_data=f"browse:{repo_name}:"), InlineKeyboardButton(text="🍴 My Forks",callback_data="forks")]]))

async def start_contribute_pr(query, state, session, telegram_id, fork_name, parent_name):
    await state.set_state(PullFlow.creating_title)
    await state.update_data(repo_name=parent_name, fork_name=fork_name, contributing=True)
    branch = session.get("active_branch","main") if session else "main"
    text = panel("🔀  Contribute to Upstream", ["---", f"  From: {h(fork_name)}", f"  Into: {h(parent_name)}", "---", "  Type the pull request title:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"fork_view:{fork_name}")]]))
