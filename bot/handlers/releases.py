from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram import Router

from bot.services.github import get_releases, create_release, delete_release
from bot.states.flow import ReleaseFlow
from bot.ui.keyboards import releases_kb, release_detail_kb
from bot.ui.panel import CTX_RELEASES, PanelManager
from utils.formatters import time_ago

def _dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_releases(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    releases = await get_releases(session, telegram_id, repo_name)
    lines = ["---", f"  {h(repo_name.split('/')[-1])}", "---"]
    if not releases: lines.append("  No releases yet.")
    for r in releases:
        icon = "🔖" if r["prerelease"] else "🚀"
        lines += [f"  {icon}  {h(r['tag_name'])}  {'Latest' if releases.index(r)==0 else ''}", f"       {h(r['name'][:40])}", f"       {h(time_ago(_dt(r['created_at'])))}  ·  📦 {r['assets_count']} assets","···"]
    text = panel("🚀  Releases", lines)
    await pm.update(telegram_id, chat_id, CTX_RELEASES, f"<pre>{text}</pre>", releases_kb(repo_name, releases))

async def show_release_detail(msg_or_query, session, telegram_id, repo_name, release_id):
    releases = await get_releases(session, telegram_id, repo_name)
    r = next((x for x in releases if x["id"]==release_id), None)
    if not r:
        await msg_or_query.message.answer("❌ Release not found.")
        return
    lines = ["---", f"  {h(r['tag_name'])}  {'🔖 Pre-release' if r['prerelease'] else '🚀 Release'}", f"  {h(r['name'])}", "---",
             f"  📦  {r['assets_count']} assets", f"  🕐  {h(time_ago(_dt(r['created_at'])))}", f"  👤  {h(r['author'])}"]
    if r["body"]: lines += ["---", h(r["body"][:200])]
    text = panel(f"🚀  Release  {h(r['tag_name'])}", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_RELEASES,
                    f"<pre>{text}</pre>",
                    InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🔗 View on GitHub",url=r["html_url"]), InlineKeyboardButton(text="🗑️ Delete",callback_data=f"release_delete:{repo_name}:{release_id}")],
                        [InlineKeyboardButton(text="⬅️ Back to Releases",callback_data=f"releases:{repo_name}"), InlineKeyboardButton(text="📁 Repo",callback_data=f"repo_open:{repo_name}"), InlineKeyboardButton(text="🏠 Home",callback_data="home")],
                    ]))

async def start_create_release(query, state, repo_name):
    await state.set_state(ReleaseFlow.creating_tag)
    await state.update_data(repo_name=repo_name)
    text = panel("🚀  New Release", ["---", f"  {h(repo_name.split('/')[-1])}", "---", "  Type the version tag:", "  e.g.  v1.0.0"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"releases:{repo_name}")]]))

@router.message(ReleaseFlow.creating_tag)
async def release_tag_received(message: Message, state: FSMContext):
    await state.update_data(tag=message.text.strip())
    await state.set_state(ReleaseFlow.creating_title)
    await message.answer("<pre>" + panel("📝  Release Title",["---","  Type the release title:","  e.g.  Initial stable release"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(ReleaseFlow.creating_title)
async def release_title_received(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(ReleaseFlow.creating_notes)
    await message.answer("<pre>" + panel("📋  Release Notes",["---","  Type release notes (or /skip):"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip",callback_data="release_skip_notes"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(ReleaseFlow.creating_notes)
async def release_notes_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    result = await create_release(session, telegram_id, data["repo_name"], data["tag"], data["title"], message.text.strip())
    ok = "error" not in result
    text = panel("✅  Release Published!" if ok else "❌  Failed", ["---", f"  🚀  {h(data['tag'])}  {h(data['title'])}" if ok else f"  Error {result.get('error','')}"])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                              InlineKeyboardButton(text="🔗 View",url=result["url"]) if ok else InlineKeyboardButton(text="🔄 Retry",callback_data=f"release_create:{data['repo_name']}"),
                              InlineKeyboardButton(text="⬅️ Back",callback_data=f"releases:{data['repo_name']}"),
                          ]]))

async def do_delete_release(query, session, telegram_id, repo_name, release_id):
    text = panel("🗑️  Delete Release?", ["---","  This removes the release tag.","  Source code is NOT deleted."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Yes, delete",callback_data=f"release_delete_confirm:{repo_name}:{release_id}"),
                                       InlineKeyboardButton(text="❌ Cancel",callback_data=f"release_view:{repo_name}:{release_id}"),
                                   ]]))

router = Router()
