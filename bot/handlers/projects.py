from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext
from aiogram import Router

from database.pool import create_project, delete_project, get_project, get_projects, update_project_files
from bot.states.flow import ProjectFlow
from bot.ui.keyboards import projects_kb, project_detail_kb
from bot.ui.panel import CTX_PROJECTS, PanelManager

async def show_projects(msg_or_query, telegram_id):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    projects = await get_projects(telegram_id)
    lines = ["---","  Local offline workspaces","  Create → edit → push to GitHub","---"]
    for p in projects:
        fc = len(p.get("files") or {})
        lines += [f"  🗂️  {h(p['name'])}", f"       {fc} files  ·  {h(str(p['updated_at'])[:10])}","···"]
    if not projects: lines.append("  No projects yet. Create one!")
    text = panel("🗂️  Projects", lines)
    await pm.update(telegram_id, chat_id, CTX_PROJECTS, f"<pre>{text}</pre>", projects_kb(projects))

async def start_create_project(query, state):
    await state.set_state(ProjectFlow.creating_name)
    text = panel("➕  New Project", ["---","  Type the project name:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="projects")]]))

@router.message(ProjectFlow.creating_name)
async def project_name_received(message: Message, state: FSMContext, telegram_id: int):
    name = message.text.strip()
    await state.update_data(name=name)
    await state.set_state(ProjectFlow.creating_description)
    await message.answer(f"<pre>" + panel("📝  Description",["---","  Type description (or /skip):"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip",callback_data="project_skip_desc"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(ProjectFlow.creating_description)
async def project_desc_received(message: Message, state: FSMContext, telegram_id: int):
    data = await state.get_data()
    await state.clear()
    project = await create_project(telegram_id, data["name"], message.text.strip())
    text = panel("✅  Project Created", ["---", f"  🗂️  {h(data['name'])}", "---","  Add files and push to GitHub when ready."])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Open Project",callback_data=f"project_open:{data['name']}"), InlineKeyboardButton(text="🗂️ All Projects",callback_data="projects")]]))

async def show_project_detail(msg_or_query, telegram_id, name):
    project = await get_project(telegram_id, name)
    if not project:
        await msg_or_query.message.answer("❌ Project not found.")
        return
    files = project.get("files") or {}
    has_files = bool(files)
    lines = ["---", f"  🗂️  {h(name)}", f"  {h(project.get('description','') or 'No description')}", "---",
             f"  {len(files)} files", "···"]
    for fname in list(files.keys())[:8]:
        lines.append(f"  📄  {h(fname)}")
    if len(files) > 8: lines.append(f"  ... and {len(files)-8} more")
    text = panel("🗂️  Project", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_PROJECTS, f"<pre>{text}</pre>", project_detail_kb(name, has_files))

async def start_add_project_file(query, state, name):
    await state.set_state(ProjectFlow.adding_file_name)
    await state.update_data(project_name=name)
    text = panel("➕  Add File", ["---", f"  Project: {h(name)}", "---","  Type the filename:", "  e.g.  main.py  or  src/app.py"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"project_open:{name}")]]))

@router.message(ProjectFlow.adding_file_name)
async def project_file_name_received(message: Message, state: FSMContext):
    await state.update_data(file_name=message.text.strip())
    await state.set_state(ProjectFlow.adding_file_content)
    await message.answer(f"<pre>" + panel("📄  File Content",["---","  Type or paste the content:","  Then send it."]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📄 Empty file",callback_data="project_empty_file"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(ProjectFlow.adding_file_content)
async def project_file_content_received(message: Message, state: FSMContext, telegram_id: int):
    data = await state.get_data()
    await state.clear()
    project = await get_project(telegram_id, data["project_name"])
    files = dict(project.get("files") or {})
    files[data["file_name"]] = message.text or ""
    await update_project_files(telegram_id, data["project_name"], files)
    await message.answer(f"✅ <code>{h(data['file_name'])}</code> added to project.", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"project_open:{data['project_name']}")  ]]))

async def show_project_files(query, telegram_id, name):
    project = await get_project(telegram_id, name)
    files = dict(project.get("files") or {})
    lines = ["---"]
    for fname, content in files.items():
        lines += [f"  📄  {h(fname)}", f"       {len(content)} chars","···"]
    if not files: lines.append("  No files yet.")
    text = panel(f"📂  Files  ·  {h(name)}", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="➕ Add File",callback_data=f"project_add_file:{name}"), InlineKeyboardButton(text="⬅️ Back",callback_data=f"project_open:{name}")]]))

async def start_push_project(query, state, session, telegram_id, name):
    project = await get_project(telegram_id, name)
    files = dict(project.get("files") or {})
    if not files:
        await query.answer("No files to push!", show_alert=True)
        return
    if session and session.get("active_repo"):
        from bot.services.github import commit_multiple_files
        from utils.formatters import auto_commit_message
        commit_msg = auto_commit_message(new_files=list(files.keys()))
        result = await commit_multiple_files(session, telegram_id, session["active_repo"], files, commit_msg)
        text = panel("✅  Project Pushed!", ["---", "  📁  " + h(session["active_repo"].split("/")[-1]), "  📝  " + str(result.get("committed",0)) + " files committed", "---", "  💬  " + h(commit_msg)])
        await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📜 Commits",callback_data=f"commits:{session['active_repo']}"), InlineKeyboardButton(text="🗂️ Projects",callback_data="projects")]]))
    else:
        await query.answer("Set an active repository first (/repos)", show_alert=True)

async def confirm_delete_project(query, telegram_id, name):
    text = panel("🗑️  Delete Project?", ["---", f"  🗂️  {h(name)}", "---","  This only deletes the local workspace.","  GitHub is NOT affected."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Yes, delete",callback_data=f"project_delete_confirm:{name}"),
                                       InlineKeyboardButton(text="❌ Cancel",callback_data=f"project_open:{name}"),
                                   ]]))

async def do_delete_project(query, telegram_id, name):
    await delete_project(telegram_id, name)
    await query.answer("🗑️ Project deleted.", show_alert=False)
    await show_projects(query, telegram_id)
router = Router()
