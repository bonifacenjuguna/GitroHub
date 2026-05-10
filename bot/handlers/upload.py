"""Upload/Commit handlers — GitroHub v2.0"""
import base64, io, logging, os, tempfile, zipfile
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from bot.services.github import commit_file, commit_multiple_files, commit_zip_files, browse_files
from bot.states.flow import CommitFlow
from bot.ui.keyboards import upload_menu_kb, commit_message_kb, sensitive_file_kb, mismatch_kb
from bot.ui.panel import CTX_UPLOAD, PanelManager, COMMIT_STEPS, ZIP_STEPS
from database.pool import add_commit_message, get_commit_messages, get_templates, get_saved_paths
from utils.formatters import h, panel, auto_commit_message

logger = logging.getLogger(__name__)
router = Router()

IGNORED = {"__pycache__",".DS_Store",".pyc",".git","node_modules","Thumbs.db"}

def _should_ignore(name):
    return any(name.lower()==ig or name.lower().endswith(ig) for ig in IGNORED)

def _is_sensitive(filename):
    sensitive = {".env",".env.local",".env.production",".env.development","secrets.json","credentials.json","id_rsa","id_ed25519",".pem",".key"}
    name = filename.lower()
    return any(name==s or name.endswith(s) for s in sensitive)

async def show_upload_menu(msg_or_query, session, telegram_id):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    repo = session.get("active_repo","?") if session else "?"
    branch = session.get("active_branch","main") if session else "main"
    text = panel("⬆️  Upload Files", ["---",f"  Repository:  {h(repo.split('/')[-1])}",f"  Branch:      {h(branch)}","---","  Choose upload mode:","---"])
    await pm.update(telegram_id, chat_id, CTX_UPLOAD, f"<pre>{text}</pre>", upload_menu_kb())

async def start_single_commit(query, state, session, telegram_id):
    await state.set_state(CommitFlow.awaiting_path)
    text = panel("📄  Single File Commit", ["---",f"  Repository: {h(session['active_repo'].split('/')[-1] if session else '?')}","---","  Type the destination path:","  e.g.  src/app.py","---","  Then send your file."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Saved Paths",callback_data="show_saved_paths"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

async def start_single_commit_at_path(query, state, session, telegram_id, path):
    await state.set_state(CommitFlow.awaiting_file)
    await state.update_data(path=path)
    text = panel("📄  Single File Commit", ["---",f"  Repository: {h(session['active_repo'].split('/')[-1] if session else '?')}",f"  Path: {h(path)}","---","  📬  Send your file now ↓"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

async def start_batch_commit(query, state, session, telegram_id):
    await state.set_state(CommitFlow.awaiting_path)
    await state.update_data(batch=True, paths=[], files={})
    repo = session.get("active_repo","?") if session else "?"
    text = panel("📦  Commit Multiple Files", ["---",f"  Repository: {h(repo.split('/')[-1])}","---","  First declare your paths:","  Type them space-separated","  or tap Saved Paths","---","  e.g.  src/app.py utils/helper.js"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Saved Paths",callback_data="show_saved_paths"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

async def start_zip_commit(query, state, session, telegram_id, is_mirror):
    mode = "Push from ZIP" if is_mirror else "Sync from ZIP"
    desc = "⚠️  ZIP becomes exact repo state. Missing files will be deleted." if is_mirror else "Only adds & modifies. Never deletes."
    await state.set_state(CommitFlow.awaiting_zip)
    await state.update_data(is_mirror=is_mirror)
    repo = session.get("active_repo","?") if session else "?"
    text = panel(f"🗜️  {mode}", ["---",f"  Repository: {h(repo.split('/')[-1])}",f"  Branch:     {h(session.get('active_branch','main') if session else 'main')}","---",f"  {desc}","---","  📬  Send your ZIP file now ↓"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(CommitFlow.awaiting_path)
async def path_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    if data.get("batch"):
        paths = [p.strip() for p in message.text.replace(",", " ").split() if p.strip()]
        await state.update_data(paths=paths, current_index=0)
        await state.set_state(CommitFlow.batch_collecting)
        path_list = "\n".join(f"  {i+1}.  {h(p)}" for i,p in enumerate(paths))
        text = panel(f"📦  {len(paths)} Paths Registered", ["---",path_list,"---","  📬  Now send files IN ORDER ↓"])
        await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))
    else:
        path = message.text.strip()
        await state.update_data(path=path)
        await state.set_state(CommitFlow.awaiting_file)
        text = panel("📬  Ready", ["---",f"  Path: {h(path)}","---","  Send your file now ↓"])
        await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(CommitFlow.awaiting_file, F.document)
async def file_received_single(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    declared_path = data.get("path","")
    filename = message.document.file_name or "file"
    declared_filename = declared_path.split("/")[-1]
    if declared_filename and filename != declared_filename and declared_filename:
        await state.update_data(file_id=message.document.file_id, sent_filename=filename)
        text = panel("⚠️  Filename Mismatch", ["---",f"  Path declared:  {h(declared_path)}",f"  File sent:      {h(filename)}","---","  Which should I use?"])
        await message.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=mismatch_kb())
        return
    await _process_single_file(message, state, session, telegram_id, declared_path, message.document.file_id)

async def mismatch_use_path(query, state, session, telegram_id):
    data = await state.get_data()
    await _process_single_file(query.message, state, session, telegram_id, data.get("path",""), data.get("file_id",""))

async def mismatch_use_file(query, state, session, telegram_id):
    data = await state.get_data()
    declared = data.get("path","")
    parent = "/".join(declared.split("/")[:-1])
    new_path = f"{parent}/{data.get('sent_filename','file')}" if parent else data.get('sent_filename','file')
    await _process_single_file(query.message, state, session, telegram_id, new_path, data.get("file_id",""))

async def _process_single_file(message, state, session, telegram_id, path, file_id):
    status_msg = await message.answer("<pre>⏳  Receiving file...</pre>", parse_mode="HTML")
    try:
        tg_file = await message.bot.get_file(file_id)
        content_bytes = await tg_file.download_as_bytearray()
    except Exception as e:
        await status_msg.edit_text(f"❌ Download failed: {e}")
        return
    fname = path.split("/")[-1]
    if _is_sensitive(fname):
        await state.update_data(path=path, content=content_bytes.decode("utf-8",errors="replace"), file_id=file_id)
        await state.set_state(CommitFlow.confirming_sensitive)
        await status_msg.edit_text(
            "<pre>" + panel("⚠️  Sensitive File Detected!", ["---",f"  {h(fname)}","---","  This file may contain API keys,","  passwords or tokens.","---","  Committing to a PUBLIC repo","  exposes them permanently."]) + "</pre>",
            parse_mode="HTML", reply_markup=sensitive_file_kb())
        return
    content = content_bytes.decode("utf-8", errors="replace")
    await status_msg.edit_text("<pre>🔍  Analyzing changes...</pre>", parse_mode="HTML")
    # Check if file exists and is identical
    branch = session.get("active_branch","main") if session else "main"
    repo = session.get("active_repo","") if session else ""
    try:
        existing = await browse_files(session, telegram_id, repo, "/".join(path.split("/")[:-1]), branch)
        existing_file = next((i for i in existing.get("items",[]) if i["path"]==path), None)
        if existing_file:
            from bot.services.github import read_file as gh_read
            old = await gh_read(session, telegram_id, repo, path, branch)
            if old.get("content") == content:
                await state.clear()
                await status_msg.edit_text("<pre>" + panel("⏭️  No Changes", ["---","File is identical to GitHub.","Nothing to commit."]) + "</pre>",
                                            parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))
                return
    except: pass
    await state.update_data(path=path, content=content, sha=None)
    await state.set_state(CommitFlow.awaiting_message)
    new_f = []
    mod_f = [path]
    auto_msg = auto_commit_message(new_files=new_f, modified_files=mod_f, path=path)
    text = panel("📤  Ready to Commit", ["---",f"  File: {h(fname)}","---",f"  Auto message: \"{h(auto_msg)}\"","---","  Choose commit message:"])
    await status_msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=commit_message_kb(repo, session.get("github_username","") if session else ""))

@router.message(CommitFlow.batch_collecting, F.document)
async def file_received_batch(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    paths = data.get("paths",[])
    files = data.get("files",{})
    idx = data.get("current_index",0)
    if idx >= len(paths):
        await message.answer("✅ All files received!")
        return
    current_path = paths[idx]
    tg_file = await message.bot.get_file(message.document.file_id)
    content_bytes = await tg_file.download_as_bytearray()
    files[current_path] = content_bytes.decode("utf-8", errors="replace")
    next_idx = idx + 1
    await state.update_data(files=files, current_index=next_idx)
    if next_idx >= len(paths):
        await message.answer(f"<pre>" + panel(f"✅  {len(paths)}/{len(paths)} Files Received", ["---","Ready to commit!","---"]) + "</pre>",
                              parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔍 Review & Commit",callback_data="batch_review"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))
    else:
        await message.answer(f"<pre>✅  {next_idx}/{len(paths)} → <code>{h(current_path)}</code>\n\nNext: <code>{h(paths[next_idx])}</code></pre>",
                              parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

async def batch_add_path(query, state, path):
    data = await state.get_data()
    paths = data.get("paths",[])
    if path not in paths: paths.append(path)
    await state.update_data(paths=paths)
    await query.answer(f"✅ Added: {path}", show_alert=False)

async def batch_paths_done(query, state):
    data = await state.get_data()
    paths = data.get("paths",[])
    if not paths:
        await query.answer("No paths selected!", show_alert=True)
        return
    await state.update_data(current_index=0, files={})
    await state.set_state(CommitFlow.batch_collecting)
    path_list = "\n".join(f"  {i+1}.  {h(p)}" for i,p in enumerate(paths))
    text = panel(f"📦  {len(paths)} Paths Registered", ["---",path_list,"---","  📬  Send files IN ORDER ↓"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

async def batch_review(query, state, session, telegram_id):
    data = await state.get_data()
    files = data.get("files",{})
    new_f, mod_f, skip_f = [], [], []
    repo = session.get("active_repo","") if session else ""
    branch = session.get("active_branch","main") if session else "main"
    for path, content in files.items():
        try:
            from bot.services.github import read_file as gh_read
            old = await gh_read(session, telegram_id, repo, path, branch)
            if "error" in old: new_f.append(path)
            elif old["content"] == content: skip_f.append(path)
            else: mod_f.append(path)
        except: new_f.append(path)
    await state.update_data(new_files=new_f, modified_files=mod_f)
    lines = ["---"]
    if new_f: lines += [f"  ✨  NEW ({len(new_f)})","···"] + [f"  + {h(f)}" for f in new_f]
    if mod_f: lines += ["---",f"  🟡  MODIFIED ({len(mod_f)})","···"] + [f"  ~ {h(f)}" for f in mod_f]
    if skip_f: lines += ["---",f"  ⏭️  Unchanged: {len(skip_f)} (skipped)"]
    lines.append("---")
    text = panel("🔄  Changes Preview", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                                       [InlineKeyboardButton(text="✏️ Write message",callback_data="commit_write_msg"), InlineKeyboardButton(text="🤖 Auto-generate",callback_data="commit_auto_msg")],
                                       [InlineKeyboardButton(text="📋 Recent",callback_data="commit_recent_msg"), InlineKeyboardButton(text="📝 Templates",callback_data="commit_template_msg")],
                                       [InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")],
                                   ]))

@router.message(CommitFlow.awaiting_zip, F.document)
async def zip_received(message: Message, state: FSMContext, session, telegram_id):
    filename = message.document.file_name or ""
    if not filename.lower().endswith(".zip"):
        text = panel("❌  Expected a ZIP file", ["---",f"  You sent: {h(filename)}","---","  Use single file upload for other files."])
        await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📄 Single file",callback_data="commit_single"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))
        return
    data = await state.get_data()
    is_mirror = data.get("is_mirror", True)
    pm = PanelManager(message.bot)
    status = await message.answer("<pre>📦  ZIP received — extracting...</pre>", parse_mode="HTML")
    try:
        tg_file = await message.bot.get_file(message.document.file_id)
        content_bytes = await tg_file.download_as_bytearray()
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "upload.zip")
            with open(zip_path,"wb") as f: f.write(content_bytes)
            if not zipfile.is_zipfile(zip_path):
                await status.edit_text("<pre>" + panel("❌  Corrupted ZIP",["---","File arrived damaged.","Re-compress and try again."]) + "</pre>", parse_mode="HTML")
                return
            with zipfile.ZipFile(zip_path,"r") as zf:
                all_names = [n for n in zf.namelist() if not n.endswith("/")]
                names = [n for n in all_names if not any(_should_ignore(p) for p in n.split("/"))]
                top_dirs = set(n.split("/")[0] for n in names if "/" in n)
                strip_prefix = (list(top_dirs)[0]+"/") if len(top_dirs)==1 else None
                await status.edit_text("<pre>✂️  Stripping wrapper folder...</pre>", parse_mode="HTML")
                file_map, sensitive = {}, []
                for name in names:
                    clean = name[len(strip_prefix):] if strip_prefix and name.startswith(strip_prefix) else name
                    if not clean: continue
                    if _is_sensitive(clean.split("/")[-1]): sensitive.append(clean); continue
                    try: file_map[clean] = zf.read(name).decode("utf-8",errors="replace")
                    except: pass
            await status.edit_text("<pre>📡  Comparing with GitHub...</pre>", parse_mode="HTML")
            repo = session.get("active_repo","") if session else ""
            branch = session.get("active_branch","main") if session else "main"
            existing_files = {}
            try:
                def _walk(path=""):
                    from bot.services.github import browse_files as sync_browse
                    pass
                from bot.services.github import read_file as gh_read
                from bot.services.cache import cache_get
                # Fetch existing tree
                import asyncio
                async def get_existing():
                    try:
                        root = await browse_files(session, telegram_id, repo, "", branch)
                        stack = list(root.get("items",[]))
                        while stack:
                            item = stack.pop()
                            if item["type"]=="dir":
                                sub = await browse_files(session, telegram_id, repo, item["path"], branch)
                                stack.extend(sub.get("items",[]))
                            else:
                                existing_files[item["path"]] = item
                    except: pass
                await get_existing()
            except: pass
            new_f, mod_f, skip_f, del_f = [], [], [], []
            for path, content in file_map.items():
                if path in existing_files:
                    old = await gh_read(session, telegram_id, repo, path, branch)
                    if old.get("content")==content: skip_f.append(path)
                    else: mod_f.append(path)
                else: new_f.append(path)
            if is_mirror:
                for path in existing_files:
                    if path not in file_map: del_f.append(path)
            existing_sha = {k:v["sha"] for k,v in existing_files.items()}
            await state.update_data(file_map=file_map, new_files=new_f, modified_files=mod_f, deleted_files=del_f, existing_sha=existing_sha, sensitive=sensitive)
            lines = ["---"]
            if new_f: lines += [f"  ✨  New ({len(new_f)})","···"]+[f"  + {h(f)}" for f in new_f[:5]]+(["  ..."] if len(new_f)>5 else [])
            if mod_f: lines += ["---",f"  🟡  Modified ({len(mod_f)})","···"]+[f"  ~ {h(f)}" for f in mod_f[:5]]+(["  ..."] if len(mod_f)>5 else [])
            if del_f and is_mirror: lines += ["---",f"  🗑️  Will delete ({len(del_f)})","···"]+[f"  - {h(f)}" for f in del_f[:5]]
            if skip_f: lines += ["---",f"  ⏭️  Unchanged: {len(skip_f)} (skipped)"]
            if sensitive: lines += ["---",f"  ⚠️  Auto-excluded (sensitive): {len(sensitive)}"]+[f"  🔒 {h(f)}" for f in sensitive]
            lines.append("---")
            text = panel("📊  Analysis Complete", lines)
            await status.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                    reply_markup=commit_message_kb(repo, session.get("github_username","") if session else ""))
    except Exception as e:
        logger.error(f"ZIP error: {e}", exc_info=True)
        await status.edit_text(f"<pre>" + panel("❌  ZIP Processing Failed",["---",f"  {h(str(e)[:80])}","---","Re-compress and try again."]) + "</pre>", parse_mode="HTML")

async def prompt_write_message(query, state):
    data = await state.get_data()
    await state.update_data(**data)
    text = panel("✏️  Commit Message", ["---","  Write your commit message:","---","  Keep it short and descriptive."])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

async def use_auto_message(query, state):
    data = await state.get_data()
    msg = auto_commit_message(new_files=data.get("new_files",[]), modified_files=data.get("modified_files",[]), deleted_files=data.get("deleted_files",[]), path=data.get("path"))
    text = panel("🤖  Auto-Generated Message", ["---",f"  \"{h(msg)}\"","---","  Use this message?"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Use this",callback_data=f"commit_use_msg:{msg}"),
                                       InlineKeyboardButton(text="✏️ Edit it",callback_data="commit_write_msg"),
                                       InlineKeyboardButton(text="❌ Cancel",callback_data="cancel"),
                                   ]]))

async def show_recent_messages(query, state, session, telegram_id):
    if not session: return
    msgs = await get_commit_messages(telegram_id, session["github_username"], session.get("active_repo",""))
    if not msgs:
        await query.answer("No recent messages yet.", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=m[:45], callback_data=f"commit_use_msg:{m}")] for m in msgs]
    kb.append([InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")])
    await query.message.edit_text("<pre>" + panel("📋  Recent Messages",["---"]) + "</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_template_messages(query, state, session, telegram_id):
    if not session: return
    templates = await get_templates(telegram_id, session["github_username"], session.get("active_repo",""))
    if not templates:
        await query.answer("No templates yet. Use Settings → Templates.", show_alert=True)
        return
    kb = [[InlineKeyboardButton(text=t["template"][:45], callback_data=f"commit_use_template:{t['id']}")] for t in templates]
    kb.append([InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")])
    await query.message.edit_text("<pre>" + panel("📝  Templates",["---"]) + "</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def use_template_message(query, state, session, telegram_id, tmpl_id):
    if not session: return
    templates = await get_templates(telegram_id, session["github_username"], session.get("active_repo",""))
    tmpl = next((t["template"] for t in templates if str(t["id"])==tmpl_id), None)
    if not tmpl:
        await query.answer("Template not found.", show_alert=True)
        return
    text = panel("📝  Complete the Template", ["---",f"  {h(tmpl)}","---","  Send your full commit message:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

async def preview_tree(query, state, session, telegram_id):
    data = await state.get_data()
    repo = session.get("active_repo","") if session else ""
    branch = session.get("active_branch","main") if session else "main"
    new_f = set(data.get("new_files",[]))
    mod_f = set(data.get("modified_files",[]))
    del_f = set(data.get("deleted_files",[]))
    if data.get("path"): (new_f if data.get("is_new") else mod_f).add(data["path"])
    try:
        root = await browse_files(session, telegram_id, repo, "", branch)
        lines = ["---",f"  {h(repo.split('/')[-1])}  @  {h(branch)}","---"]
        for item in root.get("items",[])[:15]:
            path = item["path"]
            if path in new_f: icon="✨"
            elif path in mod_f: icon="🟡"
            elif path in del_f: icon="🗑️"
            else: icon="📄" if item["type"]=="file" else "📁"
            lines.append(f"  {icon}  {h(item['name'])}")
        lines += ["---","  ✨ New  🟡 Modified  🗑️ Deleted"]
    except:
        lines = ["---","  Unable to generate preview."]
    text = panel("👁️  Preview After Commit", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="✅ Looks good, commit",callback_data="commit_confirm"),
                                       InlineKeyboardButton(text="❌ Cancel",callback_data="cancel"),
                                   ]]))

async def commit_with_message(query, state, session, telegram_id, commit_msg):
    data = await state.get_data()
    await state.clear()
    await _execute_commit(query.message, session, telegram_id, data, commit_msg)

@router.message(CommitFlow.awaiting_message)
async def commit_message_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    await _execute_commit(message, session, telegram_id, data, message.text.strip())

async def do_commit(query, state, session, telegram_id):
    data = await state.get_data()
    commit_msg = auto_commit_message(new_files=data.get("new_files",[]), modified_files=data.get("modified_files",[]), path=data.get("path"))
    await state.clear()
    await _execute_commit(query.message, session, telegram_id, data, commit_msg)

async def _execute_commit(message, session, telegram_id, data, commit_msg):
    status = await message.answer("<pre>⬆️  Committing...</pre>", parse_mode="HTML")
    repo = session.get("active_repo","") if session else ""
    branch = session.get("active_branch","main") if session else "main"
    try:
        if data.get("file_map"):
            result = await commit_zip_files(session, telegram_id, repo, data["file_map"], data.get("new_files",[]), data.get("modified_files",[]), data.get("deleted_files",[]), data.get("existing_sha",{}), commit_msg, branch)
            committed = result.get("committed",0)
            deleted = result.get("deleted",0)
            failed = result.get("failed",0)
            summary = f"  ✨  Created/Updated: {committed}\n  🗑️  Deleted: {deleted}\n  ❌  Failed: {failed}"
        elif data.get("files"):
            result = await commit_multiple_files(session, telegram_id, repo, data["files"], commit_msg, branch)
            summary = f"  📝  Committed: {result.get('committed',0)}\n  ⏭️  Skipped: {result.get('skipped',0)}\n  ❌  Failed: {result.get('failed',0)}"
        else:
            result = await commit_file(session, telegram_id, repo, data.get("path",""), data.get("content",""), commit_msg, branch, data.get("sha"))
            summary = f"  📄  {h(data.get('path',''))}\n  ✅  Committed"
        if "error" in result:
            await status.edit_text(f"<pre>" + panel("❌  Commit Failed",["---",f"  GitHub error: {result['error']}","---","  Check your token and try again."]) + "</pre>", parse_mode="HTML")
            return
        await add_commit_message(telegram_id, session.get("github_username","") if session else "", repo, commit_msg)
        sha = result.get("sha","")
        text = panel("✅  Committed", ["---",f"  Repository:  {h(repo.split('/')[-1])}",f"  Branch:      {h(branch)}","---",summary,"---",f"  💬  \"{h(commit_msg[:50])}\"",f"  🔗  {h(sha)}" if sha else ""])
        await status.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                    InlineKeyboardButton(text="📜 View Commits",callback_data=f"commits:{repo}"),
                                    InlineKeyboardButton(text="📂 Browse",callback_data=f"browse:{repo}:"),
                                ],[
                                    InlineKeyboardButton(text="📁 Repo",callback_data=f"repo_open:{repo}"),
                                    InlineKeyboardButton(text="🏠 Home",callback_data="home"),
                                ]]))
    except Exception as e:
        logger.error(f"Commit error: {e}", exc_info=True)
        await status.edit_text(f"❌ Commit failed: {h(str(e)[:100])}", parse_mode="HTML")

async def sensitive_confirmed(query, state, session, telegram_id):
    data = await state.get_data()
    await state.set_state(CommitFlow.awaiting_message)
    auto_msg = auto_commit_message(path=data.get("path",""))
    await query.message.edit_text(f"<pre>" + panel("⚠️  Sensitive File — Choose Message",["---",f"  {h(data.get('path',''))}","---","  Select commit message:"]) + "</pre>",
                                   parse_mode="HTML", reply_markup=commit_message_kb("",""))

async def sensitive_skipped(query, state):
    await state.clear()
    await query.message.edit_text("<pre>" + panel("⏭️  File Skipped",["---","Sensitive file was not committed."]) + "</pre>",
                                   parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))
