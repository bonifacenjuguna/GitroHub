"""Branch handlers — GitroHub v2.0"""
import logging
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from bot.services.github import get_branches, create_branch, delete_branch, merge_branch, protect_branch, compare_branches, rename_branch
from bot.states.flow import BranchFlow
from bot.ui.keyboards import branches_kb
from bot.ui.panel import CTX_BRANCHES, PanelManager
from database.pool import update_session
from utils.formatters import h, panel

logger = logging.getLogger(__name__)
router = Router()

async def show_branches(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    try: await msg_or_query.message.edit_text("<pre>⏳  Loading branches...</pre>", parse_mode="HTML")
    except: pass
    branches = await get_branches(session, telegram_id, repo_name)
    active = session.get("active_branch","main") if session else "main"
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  {len(branches)} branches", "---"]
    for b in branches:
        marker = "●" if b["name"]==active else " "
        prot = "  🔒" if b["protected"] else ""
        lines.append(f"  {marker}  {h(b['name'])}{prot}")
        lines.append(f"       {h(b['sha'])}")
        lines.append("···")
    text = panel("🌿  Branches", lines)
    await pm.update(telegram_id, chat_id, CTX_BRANCHES, f"<pre>{text}</pre>", branches_kb(repo_name, branches, active))

async def checkout_branch(query, session, telegram_id, repo_name, branch_name):
    await update_session(telegram_id, active_branch=branch_name)
    warning = "\n  ⚠️  You're on main — commits go directly here." if branch_name in ("main","master") else ""
    text = panel("✅  Branch Checked Out", ["---", f"  🌿  {h(branch_name)}", f"  📁  {h(repo_name.split('/')[-1])}", f"{warning}","---","  All commits go to this branch now."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬆️ Upload Files", callback_data="upload_menu"),
                                       InlineKeyboardButton(text="📂 Browse", callback_data=f"browse:{repo_name}:"),
                                   ],[
                                       InlineKeyboardButton(text="⬅️ Back to Branches", callback_data=f"branches:{repo_name}"),
                                       InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                                   ]]))

async def start_create_branch(query, state, repo_name):
    await state.set_state(BranchFlow.creating)
    await state.update_data(repo_name=repo_name)
    text = panel("🌿  New Branch", ["---", f"  Repository: {h(repo_name.split('/')[-1])}", "---", "  Type the branch name:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"branches:{repo_name}")]]))

@router.message(BranchFlow.creating)
async def branch_name_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    repo_name = data.get("repo_name","")
    branch_name = message.text.strip().replace(" ","-")
    await state.clear()
    current = session.get("active_branch","main") if session else "main"
    result = await create_branch(session, telegram_id, repo_name, branch_name, current)
    if "error" in result:
        err = "Branch name already exists." if result["error"]==422 else f"Error {result['error']}"
        await message.answer(f"<pre>" + panel("❌  Branch Creation Failed",["---",f"  {err}"]) + "</pre>", parse_mode="HTML",
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data=f"branches:{repo_name}")]]))
        return
    text = panel("✅  Branch Created", ["---", f"  🌿  {h(branch_name)}", f"  From: {h(current)}", "---"])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                              InlineKeyboardButton(text="🔄 Checkout", callback_data=f"branch_checkout:{repo_name}:{branch_name}"),
                              InlineKeyboardButton(text="⬅️ All Branches", callback_data=f"branches:{repo_name}"),
                          ]]))

async def confirm_delete_branch(query, session, telegram_id, repo_name, branch_name):
    active = session.get("active_branch","main") if session else "main"
    if branch_name == active:
        await query.answer("❌ Cannot delete your active branch. Checkout another branch first.", show_alert=True)
        return
    text = panel("🗑️  Delete Branch", ["---", f"  🌿  {h(branch_name)}", "---", "  ⚠️  This cannot be undone."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"branch_delete_confirm:{repo_name}:{branch_name}"),
                                       InlineKeyboardButton(text="❌ Cancel", callback_data=f"branches:{repo_name}"),
                                   ]]))

async def do_delete_branch(query, session, telegram_id, repo_name, branch_name):
    result = await delete_branch(session, telegram_id, repo_name, branch_name)
    if "error" in result:
        err = "Protected branch — remove protection first." if result["error"]==422 else f"Error {result['error']}"
        await query.answer(f"❌ {err}", show_alert=True)
        return
    text = panel("🗑️  Branch Deleted", ["---", f"  🌿  {h(branch_name)} deleted.", "---"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Branches", callback_data=f"branches:{repo_name}"), InlineKeyboardButton(text="🏠 Home", callback_data="home")]]))

async def confirm_merge_branch(query, session, telegram_id, repo_name, branch_name):
    base = session.get("active_branch","main") if session else "main"
    text = panel("🔀  Merge Branch", ["---", f"  From: {h(branch_name)}", f"  Into: {h(base)}", "---"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Merge", callback_data=f"branch_merge_confirm:{repo_name}:{branch_name}"),
                                       InlineKeyboardButton(text="❌ Cancel", callback_data=f"branches:{repo_name}"),
                                   ]]))

async def do_merge_branch(query, session, telegram_id, repo_name, branch_name):
    base = session.get("active_branch","main") if session else "main"
    try: await query.message.edit_text("<pre>🔀  Merging...</pre>", parse_mode="HTML")
    except: pass
    result = await merge_branch(session, telegram_id, repo_name, base, branch_name)
    if "error" in result:
        err = "Merge conflict detected. Resolve on GitHub first." if result["error"]==409 else f"Error {result['error']}"
        await query.message.edit_text(f"<pre>" + panel("❌  Merge Failed",["---",f"  {err}"]) + "</pre>", parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                           InlineKeyboardButton(text="🌐 Resolve on GitHub", url=f"https://github.com/{repo_name}/compare/{branch_name}"),
                                           InlineKeyboardButton(text="⬅️ Back", callback_data=f"branches:{repo_name}"),
                                       ]]))
        return
    if result.get("nothing"):
        await query.message.edit_text("<pre>" + panel("⏭️  Already Up to Date",["---","Nothing to merge."]) + "</pre>", parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data=f"branches:{repo_name}")]]))
        return
    text = panel("✅  Merged!", ["---", f"  {h(branch_name)} → {h(base)}", f"  Commit: {h(result.get('sha','?'))}", "---"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="📜 Commits", callback_data=f"commits:{repo_name}"),
                                       InlineKeyboardButton(text="⬅️ Branches", callback_data=f"branches:{repo_name}"),
                                       InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                                   ]]))

async def start_rename_branch(query, state, repo_name, branch_name):
    await state.set_state(BranchFlow.renaming)
    await state.update_data(repo_name=repo_name, old_name=branch_name)
    text = panel("✏️  Rename Branch", ["---", f"  Current: {h(branch_name)}", "---", "  Type the new name:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"branches:{repo_name}")]]))

@router.message(BranchFlow.renaming)
async def branch_rename_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    result = await rename_branch(session, telegram_id, data["repo_name"], data["old_name"], message.text.strip())
    ok = "error" not in result
    text = panel("✅  Branch Renamed" if ok else "❌  Failed", ["---", f"  {h(data['old_name'])} → {h(message.text.strip())}" if ok else f"  Error {result.get('error','')}"])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Branches", callback_data=f"branches:{data['repo_name']}"), InlineKeyboardButton(text="🏠 Home", callback_data="home")]]))

async def do_protect_branch(query, session, telegram_id, repo_name, branch_name):
    result = await protect_branch(session, telegram_id, repo_name, branch_name)
    await query.answer("✅ Branch protection enabled." if "error" not in result else f"❌ Error {result.get('error','')}", show_alert=True)
    await show_branches(query, session, telegram_id, repo_name)

async def start_compare_branches(query, state, repo_name):
    await state.set_state(BranchFlow.comparing)
    await state.update_data(repo_name=repo_name)
    text = panel("🔀  Compare Branches", ["---", f"  {h(repo_name.split('/')[-1])}", "---", "  Type: <base_branch> <compare_branch>", "  e.g.  main dev"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"branches:{repo_name}")]]))

@router.message(BranchFlow.comparing)
async def branch_compare_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Type two branch names separated by a space.")
        return
    base, head = parts[0], parts[1]
    repo_name = data.get("repo_name","")
    result = await compare_branches(session, telegram_id, repo_name, base, head)
    if "error" in result:
        await message.answer(f"❌ Compare failed (error {result['error']}).")
        return
    lines = ["---", f"  {h(head)} vs {h(base)}", "---",
             f"  ⬆️  {result['ahead_by']} commits ahead", f"  ⬇️  {result['behind_by']} commits behind", "---",
             f"  Changed files ({len(result['files'])}):", "···"]
    for f in result["files"]:
        icon = {"added":"✨","modified":"🟡","removed":"🗑️","renamed":"📝"}.get(f["status"],"📄")
        lines.append(f"  {icon}  {h(f['filename'])}  +{f['additions']} -{f['deletions']}")
    text = panel("🔀  Compare", lines)
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                              InlineKeyboardButton(text=f"🔀 Merge {head}→{base}", callback_data=f"branch_merge_confirm:{repo_name}:{head}"),
                              InlineKeyboardButton(text="⬅️ Branches", callback_data=f"branches:{repo_name}"),
                          ]]))
