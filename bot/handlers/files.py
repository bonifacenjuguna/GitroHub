"""File handlers — GitroHub v2.0"""
import base64, io, logging
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from bot.services.github import browse_files, read_file, commit_file, delete_file, move_file, get_file_history, search_code
from bot.states.flow import FileFlow
from bot.ui.keyboards import browse_kb, file_view_kb
from bot.ui.panel import CTX_FILES, PanelManager
from utils.formatters import h, panel, format_size, breadcrumb, time_ago

logger = logging.getLogger(__name__)
router = Router()

def _parse_dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_browse(msg_or_query, session, telegram_id, repo_name, path=""):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    branch = session.get("active_branch","main") if session else "main"
    try:
        await msg_or_query.message.edit_text("<pre>⏳  Loading files...</pre>", parse_mode="HTML")
    except: pass
    data = await browse_files(session, telegram_id, repo_name, path, branch)
    if "error" in data:
        await pm.update(telegram_id, chat_id, CTX_FILES, f"<pre>" + panel("❌  Error",["---",f"  Cannot browse: {repo_name}","---",f"  Error {data['error']}"]) + "</pre>",
                        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"repo_open:{repo_name}")]]))
        return
    crumb = breadcrumb(repo_name, path, branch)
    dirs = [i for i in data["items"] if i["type"]=="dir"]
    files = [i for i in data["items"] if i["type"]=="file"]
    lines = ["---", f"  {h(crumb)}", "---"]
    for d in dirs: lines.append(f"  📁  {h(d['name'])}/")
    for f in files: lines.append(f"  📄  {h(f['name'])}  {format_size(f['size']//1024) if f['size']>1024 else str(f['size'])+' B'}")
    lines += ["---", f"  {len(data['items'])} items  ·  {format_size(data['total_size']//1024)}"]
    text = panel("📂  Files", lines)
    await pm.update(telegram_id, chat_id, CTX_FILES, f"<pre>{text}</pre>", browse_kb(repo_name, path, branch, data["items"]))

async def show_file(msg_or_query, session, telegram_id, repo_name, path):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    branch = session.get("active_branch","main") if session else "main"
    data = await read_file(session, telegram_id, repo_name, path, branch)
    if "error" in data:
        await msg_or_query.message.answer(f"<pre>" + panel("❌  Error",["---","File not found or access denied.","---",f"  {h(path)}"]) + "</pre>", parse_mode="HTML")
        return
    content = data["content"]
    truncated = len(content) > 3000
    display = content[:3000] + ("\n\n... truncated" if truncated else "")
    fname = path.split("/")[-1]
    lines = ["---", f"  {h(path)}", f"  {format_size(data['size']//1024 if data['size']>1024 else 0)}", "---", display[:2500]]
    if truncated: lines.append("  ... content truncated")
    text = panel(f"📄  {h(fname)}", lines)
    await pm.update(telegram_id, chat_id, CTX_FILES, f"<pre>{text}</pre>", file_view_kb(repo_name, path, branch))

async def start_file_edit(query, state, session, telegram_id, repo_name, path):
    branch = session.get("active_branch","main") if session else "main"
    data = await read_file(session, telegram_id, repo_name, path, branch)
    if "error" in data:
        await query.message.answer("❌ Cannot read file for editing.")
        return
    await state.set_state(FileFlow.editing)
    await state.update_data(repo_name=repo_name, path=path, sha=data["sha"], original=data["content"])
    file_bytes = io.BytesIO(data["content"].encode("utf-8"))
    file_bytes.name = path.split("/")[-1]
    caption = panel(f"✏️  Edit Mode", ["---", f"  {h(path)}", "---", "Edit this file and send it back ↩️", "---", "Send the edited file as a document."])
    await query.message.answer_document(document=file_bytes, caption=f"<pre>{caption}</pre>", parse_mode="HTML",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel edit",callback_data="cancel")]]))

async def confirm_delete_file(query, session, telegram_id, repo_name, path):
    text = panel(f"🗑️  Delete File", ["---", f"  {h(path)}", "---", "  ⚠️  This cannot be undone.", "  The file will be permanently deleted."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Yes, delete", callback_data=f"file_delete_confirm:{repo_name}:{path}"),
                                       InlineKeyboardButton(text="❌ Cancel", callback_data=f"browse:{repo_name}:{'/'.join(path.split('/')[:-1])}"),
                                   ]]))

async def do_delete_file(query, session, telegram_id, repo_name, path):
    try: await query.message.edit_text("<pre>⏳  Deleting file...</pre>", parse_mode="HTML")
    except: pass
    result = await delete_file(session, telegram_id, repo_name, path, session.get("active_branch","main"))
    parent = "/".join(path.split("/")[:-1])
    if "error" in result:
        await query.message.edit_text(f"❌ Delete failed (error {result['error']}).",
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"browse:{repo_name}:{parent}")]]))
        return
    text = panel("🗑️  File Deleted", ["---", f"  {h(path)}", "---", "  File permanently deleted."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="📂 Browse",callback_data=f"browse:{repo_name}:{parent}"),
                                       InlineKeyboardButton(text="📁 Repo",callback_data=f"repo_open:{repo_name}"),
                                       InlineKeyboardButton(text="🏠 Home",callback_data="home"),
                                   ]]))

async def start_move_file(query, state, repo_name, path):
    await state.set_state(FileFlow.moving_destination)
    await state.update_data(repo_name=repo_name, src_path=path)
    text = panel("📦  Move File", ["---", f"  From: {h(path)}", "---", "  Type the destination path:","  e.g.  src/utils/helper.py"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"file_read:{repo_name}:{path}")]]))

@router.message(FileFlow.moving_destination)
async def file_move_dest_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    result = await move_file(session, telegram_id, data["repo_name"], data["src_path"], message.text.strip())
    ok = "error" not in result
    text = panel("✅  File Moved" if ok else "❌  Move Failed", ["---", f"  From: {h(data['src_path'])}", f"  To: {h(message.text.strip())}" if ok else "  Check the destination path."])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Browse",callback_data=f"browse:{data['repo_name']}:"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))

async def start_rename_file(query, state, repo_name, path):
    await state.set_state(FileFlow.renaming)
    await state.update_data(repo_name=repo_name, path=path)
    parent = "/".join(path.split("/")[:-1])
    text = panel("✏️  Rename File", ["---", f"  {h(path)}", "---", "  Type the new filename:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"file_read:{repo_name}:{path}")]]))

@router.message(FileFlow.renaming)
async def file_rename_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    old_path = data["path"]
    parent = "/".join(old_path.split("/")[:-1])
    new_path = f"{parent}/{message.text.strip()}" if parent else message.text.strip()
    result = await move_file(session, telegram_id, data["repo_name"], old_path, new_path)
    ok = "error" not in result
    text = panel("✅  File Renamed" if ok else "❌  Failed", ["---", f"  {h(old_path.split('/')[-1])} → {h(message.text.strip())}"])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Browse",callback_data=f"browse:{data['repo_name']}:{parent}"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))

async def start_create_file(query, state, repo_name, base_path):
    await state.set_state(FileFlow.creating_name)
    await state.update_data(repo_name=repo_name, base_path=base_path)
    text = panel("➕  New File", ["---", f"  In: {h(base_path or 'root')}", "---", "  Type the filename:", "  e.g.  README.md  or  src/app.py"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"browse:{repo_name}:{base_path}")]]))

@router.message(FileFlow.creating_name)
async def file_create_name_received(message: Message, state: FSMContext):
    data = await state.get_data()
    fname = message.text.strip()
    base = data.get("base_path","")
    full_path = f"{base}/{fname}" if base else fname
    await state.update_data(path=full_path)
    await state.set_state(FileFlow.creating_content)
    text = panel(f"📄  {h(fname)}", ["---", "  Type or paste the file content:", "---", "  Send as text message."])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📄 Empty file",callback_data="file_create_empty"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(FileFlow.creating_content)
async def file_create_content_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    from utils.formatters import auto_commit_message
    commit_msg = auto_commit_message(new_files=[data["path"]])
    result = await commit_file(session, telegram_id, data["repo_name"], data["path"], message.text or "", commit_msg)
    ok = "error" not in result
    text = panel("✅  File Created" if ok else "❌  Failed", ["---", f"  {h(data['path'])}", f"  Commit: {h(result.get('sha','?'))}" if ok else f"  Error {result.get('error','')}"])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📂 Browse",callback_data=f"browse:{data['repo_name']}:"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))

async def download_single_file(query, session, telegram_id, repo_name, path):
    branch = session.get("active_branch","main") if session else "main"
    data = await read_file(session, telegram_id, repo_name, path, branch)
    if "error" in data:
        await query.message.answer("❌ Cannot download this file.")
        return
    fname = path.split("/")[-1]
    file_bytes = io.BytesIO(data["content"].encode("utf-8"))
    file_bytes.name = fname
    await query.message.answer_document(document=file_bytes, caption=f"📄 <code>{h(path)}</code>", parse_mode="HTML",
                                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"file_read:{repo_name}:{path}")]]))

async def show_file_history(query, session, telegram_id, repo_name, path):
    history = await get_file_history(session, telegram_id, repo_name, path)
    lines = ["---", f"  {h(path)}", "---"]
    for i, c in enumerate(history, 1):
        lines += [f"  {i}.  {h(c['sha'])}  \"{h(c['message'][:35])}\"", f"       {h(c['author'])}  ·  {h(time_ago(_parse_dt(c['date'])))}","···"]
    if not history: lines.append("  No commit history found.")
    text = panel("📜  File History", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬅️ Back",callback_data=f"file_read:{repo_name}:{path}"),
                                       InlineKeyboardButton(text="📁 Repo",callback_data=f"repo_open:{repo_name}"),
                                       InlineKeyboardButton(text="🏠 Home",callback_data="home"),
                                   ]]))

async def show_file_blame(query, session, telegram_id, repo_name, path):
    await query.message.edit_text(
        f"<pre>" + panel("👤  Blame", ["---",f"  {h(path)}","---","  View blame on GitHub:","  (Blame requires full browser rendering)"]) + "</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🌐 View Blame on GitHub", url=f"https://github.com/{repo_name}/blame/{session.get('active_branch','main')}/{path}"),
            InlineKeyboardButton(text="⬅️ Back",callback_data=f"file_read:{repo_name}:{path}"),
        ]]))

async def start_search(query, state, repo_name):
    await state.set_state(FileFlow.searching)
    await state.update_data(repo_name=repo_name)
    text = panel("🔍  Search in Repository", ["---", f"  {h(repo_name.split('/')[-1])}", "---", "  Type your search term:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"repo_open:{repo_name}")]]))

@router.message(FileFlow.searching)
async def file_search_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    repo_name = data.get("repo_name","")
    results = await search_code(session, telegram_id, repo_name, message.text.strip())
    lines = ["---", f"  Query: \"{h(message.text.strip())}\"", f"  Found: {len(results)} results", "---"]
    for r in results: lines += [f"  📄  {h(r['path'])}","···"]
    if not results: lines.append("  No results found.")
    text = panel("🔍  Search Results", lines)
    kb_rows = [[InlineKeyboardButton(text=f"👁 {r['name'][:30]}",callback_data=f"file_read:{repo_name}:{r['path']}")] for r in results]
    kb_rows.append([InlineKeyboardButton(text="🔍 Search again",callback_data=f"file_search:{repo_name}"), InlineKeyboardButton(text="📁 Repo",callback_data=f"repo_open:{repo_name}")])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
