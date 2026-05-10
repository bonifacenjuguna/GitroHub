"""Commit history handlers — GitroHub v2.0"""
import logging
from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from bot.services.github import get_commits, get_commit_detail, revert_commit, reset_to_commit
from bot.ui.keyboards import commits_kb, commit_detail_kb
from bot.ui.panel import CTX_HISTORY, PanelManager
from utils.formatters import h, panel, time_ago

logger = logging.getLogger(__name__)
router = Router()

def _dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_commits(msg_or_query, session, telegram_id, repo_name, branch, page=0):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    try: await msg_or_query.message.edit_text("<pre>⏳  Loading commits...</pre>", parse_mode="HTML")
    except: pass
    data = await get_commits(session, telegram_id, repo_name, branch, page)
    if "error" in data:
        await pm.update(telegram_id, chat_id, CTX_HISTORY, f"<pre>" + panel("❌  Error",["---","Failed to load commits."]) + "</pre>",
                        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"repo_open:{repo_name}")]]))
        return
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  🌿  {h(branch)}", "---"]
    for i, c in enumerate(data["commits"], 1+page*8):
        lines += [f"  {i}.  {h(c['sha_short'])}", f"       💬  \"{h(c['message'][:40])}\"", f"       👤  {h(c['author'])}  ·  {h(time_ago(_dt(c['date'])))}","···"]
    lines += ["---", f"  Page {page+1} / {data['total_pages']}  ·  {data['total']} total"]
    text = panel("📜  Commits", lines)
    await pm.update(telegram_id, chat_id, CTX_HISTORY, f"<pre>{text}</pre>", commits_kb(repo_name, branch, page, data["total_pages"], data["commits"]))

async def show_commit_detail(msg_or_query, session, telegram_id, repo_name, sha):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    data = await get_commit_detail(session, telegram_id, repo_name, sha)
    if "error" in data:
        await msg_or_query.message.answer("❌ Could not load commit detail.")
        return
    branch = session.get("active_branch","main") if session else "main"
    lines = ["---", f"  {h(data['sha_short'])}", f"  💬  \"{h(data['message'])}\"", f"  👤  {h(data['author'])}", f"  🕐  {h(time_ago(_dt(data['date'])))}",
             "---", f"  📊  +{data['stats']['additions']} -{data['stats']['deletions']}  ({data['stats']['total']} total)", "---", "  CHANGED FILES","···"]
    for f in data["files"]:
        icon = {"added":"✨","modified":"🟡","removed":"🗑️","renamed":"📝"}.get(f["status"],"📄")
        lines.append(f"  {icon}  {h(f['filename'])}  +{f['additions']} -{f['deletions']}")
    text = panel(f"👁  Commit  {h(data['sha_short'])}", lines)
    await pm.update(telegram_id, chat_id, CTX_HISTORY, f"<pre>{text}</pre>", commit_detail_kb(repo_name, sha, branch))

async def confirm_revert_last(query, session, telegram_id, repo_name, branch):
    data = await get_commits(session, telegram_id, repo_name, branch, 0)
    if "error" in data or not data.get("commits"):
        await query.answer("No commits to revert.", show_alert=True)
        return
    last = data["commits"][0]
    parent_sha = data["commits"][1]["sha"] if len(data["commits"]) > 1 else None
    text = panel("↩️  Revert Last Commit?", ["---", f"  {h(last['sha_short'])}  \"{h(last['message'][:40])}\"", f"  {h(time_ago(_dt(last['date'])))}","---","  ⚠️  This will reverse the commit."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Yes, revert", callback_data=f"commit_revert:{repo_name}:{branch}:{last['sha']}"),
                                       InlineKeyboardButton(text="❌ Cancel", callback_data=f"commits:{repo_name}"),
                                   ]]))

async def do_revert_commit(query, session, telegram_id, repo_name, branch, sha):
    data = await get_commits(session, telegram_id, repo_name, branch, 0)
    commits = data.get("commits",[])
    idx = next((i for i,c in enumerate(commits) if c["sha"]==sha),None)
    parent_sha = commits[idx+1]["sha"] if idx is not None and idx+1 < len(commits) else None
    if not parent_sha:
        await query.answer("❌ No parent commit found.", show_alert=True)
        return
    try: await query.message.edit_text("<pre>↩️  Reverting commit...</pre>", parse_mode="HTML")
    except: pass
    result = await revert_commit(session, telegram_id, repo_name, branch, sha, parent_sha)
    if "error" in result:
        await query.message.edit_text(f"❌ Revert failed (error {result['error']}).",
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"commits:{repo_name}")]]))
        return
    text = panel("✅  Commit Reverted", ["---", f"  🌿  {h(branch)}  restored to previous state.", "---"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="📜 Commits",callback_data=f"commits:{repo_name}"),
                                       InlineKeyboardButton(text="⬆️ Upload Again",callback_data="upload_menu"),
                                       InlineKeyboardButton(text="🏠 Home",callback_data="home"),
                                   ]]))

async def confirm_reset_to_commit(query, session, telegram_id, repo_name, branch, sha):
    data = await get_commit_detail(session, telegram_id, repo_name, sha)
    msg = data.get("message","?")[:40] if "error" not in data else "?"
    when = time_ago(_dt(data.get("date"))) if "error" not in data else "?"
    text = panel("🔄  Reset to Commit?", ["---", f"  {h(sha[:7])}  \"{h(msg)}\"", f"  {h(when)}", "---", "  ⚠️  ALL commits after this will be lost."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Yes, reset", callback_data=f"commit_reset_confirm:{repo_name}:{branch}:{sha}"),
                                       InlineKeyboardButton(text="❌ Cancel", callback_data=f"commits:{repo_name}"),
                                   ]]))

async def do_reset_to_commit(query, session, telegram_id, repo_name, branch, sha):
    try: await query.message.edit_text("<pre>🔄  Resetting...</pre>", parse_mode="HTML")
    except: pass
    result = await reset_to_commit(session, telegram_id, repo_name, branch, sha)
    if "error" in result:
        await query.message.edit_text(f"❌ Reset failed (error {result['error']}).")
        return
    text = panel("✅  Reset Complete", ["---", f"  🌿  {h(branch)}  →  {h(sha[:7])}", "---"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📜 Commits",callback_data=f"commits:{repo_name}"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))
