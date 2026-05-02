"""Upload handlers — GitroHub v1.2"""
import base64
import io
import logging
import os
import tempfile
import zipfile

from github import GithubException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import (
    add_commit_message, clear_state, get_active_session,
    get_commit_history, get_saved_paths, get_state, set_state,
)
from utils.github_helper import (
    get_error_message, get_file_diff, get_github_client,
    h, is_sensitive_file, sanitize_path,
)

logger = logging.getLogger(__name__)

IGNORED = {"__pycache__", ".DS_Store", ".pyc", ".pyo", "Thumbs.db", ".git", "node_modules"}


def _should_ignore(name: str) -> bool:
    return any(name.lower() == ig or name.lower().endswith(ig) for ig in IGNORED)


def _commit_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Write message", callback_data="commit_write"),
         InlineKeyboardButton("🤖 Auto-generate", callback_data="commit_auto")],
        [InlineKeyboardButton("📋 Recent", callback_data="commit_recent"),
         InlineKeyboardButton("📝 Templates", callback_data="commit_templates")],
        [InlineKeyboardButton("👁 Preview tree", callback_data="preview_tree"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])


async def show_upload_menu(message, telegram_id: int, edit: bool = False):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Single File", callback_data="upload_single"),
         InlineKeyboardButton("📦 Batch Files", callback_data="upload_batch")],
        [InlineKeyboardButton("🗜️ ZIP Mirror", callback_data="upload_mirror"),
         InlineKeyboardButton("🗜️ ZIP Update", callback_data="upload_update")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])
    text = "⬆️ <b>Upload — choose mode</b>"
    if edit:
        await message.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.reply_text(text, parse_mode="HTML", reply_markup=keyboard)


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.", parse_mode="HTML")
        return
    if not context.args:
        await show_upload_menu(update.message, telegram_id)
        return
    file_path = sanitize_path(" ".join(context.args))
    set_state(telegram_id, "awaiting_single_file", {"path": file_path})
    sensitive_note = "\n\n⚠️ <b>Sensitive file detected!</b> Be careful." if is_sensitive_file(file_path) else ""
    await update.message.reply_text(
        f"📬 <b>Ready — send your file</b>\n\n"
        f"Will commit to: <code>{h(session['active_repo'])}/{h(file_path)}</code>{sensitive_note}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    )


async def cmd_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    if context.args:
        paths = [sanitize_path(p) for p in context.args]
        set_state(telegram_id, "batch_collecting", {"paths": paths, "files": {}, "current_index": 0})
        path_list = "\n".join(f"{i+1}. <code>{h(p)}</code>" for i, p in enumerate(paths))
        await update.message.reply_text(
            f"✅ <b>{len(paths)} paths registered:</b>\n{path_list}\n\n📬 Now send files <b>IN ORDER</b>.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Batch", callback_data="cancel")]])
        )
        return
    set_state(telegram_id, "batch_declare_paths", {})
    await update.message.reply_text(
        f"📋 <b>Batch Mode ON</b> — <code>{h(session['active_repo'])}</code>\n\n"
        f"Declare paths first:\ne.g. <code>/batch src/app.py utils/helper.js</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⭐ Saved Paths", callback_data="batch_saved_paths"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]])
    )


async def cmd_mirror(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    set_state(telegram_id, "awaiting_zip_mirror", {})
    await update.message.reply_text(
        f"🗜️ <b>Mirror mode</b> — <code>{h(session['active_repo'])}</code> @ main\n\n"
        f"⚠️ ZIP becomes <b>exact repo state</b>. Missing files will be deleted.\n\n"
        f"📬 Send your ZIP now",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    )


async def cmd_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    set_state(telegram_id, "awaiting_zip_update", {})
    await update.message.reply_text(
        f"🗜️ <b>Update mode</b> — <code>{h(session['active_repo'])}</code> @ main\n\n"
        f"Only adds &amp; modifies. Never deletes.\n\n"
        f"📬 Send your ZIP now",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
    )


async def handle_incoming_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    state_info = get_state(telegram_id)
    state = state_info.get("state", "idle")
    document = update.message.document
    if not document:
        return
    filename = document.file_name or "file"

    if state == "awaiting_single_file":
        await _handle_single_file(update, context, state_info.get("state_data", {}), document)
    elif state == "batch_collecting":
        await _handle_batch_file(update, context, state_info.get("state_data", {}), document)
    elif state in ("awaiting_zip_mirror", "awaiting_zip_update"):
        if not filename.lower().endswith(".zip"):
            await update.message.reply_text(
                f"❌ <b>Expected a ZIP file</b>\nYou sent <code>{h(filename)}</code>.\n\nUse /upload for single files.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📄 Single upload", callback_data="upload_single"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]])
            )
            return
        await _handle_zip(update, context, document, state == "awaiting_zip_mirror")
    elif state == "awaiting_edit_file":
        await _handle_edit_return(update, context, state_info.get("state_data", {}), document)
    else:
        await update.message.reply_text(
            "❓ <b>Unexpected file</b>\nI wasn't expecting a file right now.\n\n"
            "Use /upload &lt;path&gt; first, then send your file.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬆️ Upload menu", callback_data="upload_menu"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )


async def _handle_single_file(update, context, state_data, document):
    telegram_id = update.effective_user.id
    declared_path = state_data.get("path", "")
    filename = document.file_name or "file"
    declared_filename = declared_path.split("/")[-1]

    if declared_filename and filename != declared_filename:
        set_state(telegram_id, "awaiting_single_file_mismatch", {
            **state_data, "sent_filename": filename, "file_id": document.file_id
        })
        await update.message.reply_text(
            f"⚠️ <b>Filename mismatch</b>\n\n"
            f"Path specified: <code>{h(declared_path)}</code>\n"
            f"File sent: <code>{h(filename)}</code>\n\nWhich should I use?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ Use path: {declared_filename}", callback_data="mismatch_use_path"),
                InlineKeyboardButton(f"✅ Use file: {filename}", callback_data="mismatch_use_file"),
            ], [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        )
        return
    await process_single_file(update, context, declared_path, document.file_id)


async def process_single_file(update, context, file_path: str, file_id: str):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    await update.message.reply_text("⏳ Analyzing file...", parse_mode="HTML")
    try:
        tg_file = await context.bot.get_file(file_id)
        content_bytes = await tg_file.download_as_bytearray()
        new_content = content_bytes.decode("utf-8", errors="replace")

        filename = file_path.split("/")[-1]
        if is_sensitive_file(filename):
            set_state(telegram_id, "confirming_sensitive_commit", {"path": file_path, "content": new_content, "file_id": file_id})
            await update.message.reply_text(
                f"⚠️ <b>Secrets file detected!</b>\n"
                f"<b>Reason:</b> <code>{h(filename)}</code> may contain API keys or passwords.\n"
                f"Committing to a public repo exposes them permanently.\n\nAre you absolutely sure?",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ I know, commit anyway", callback_data="confirm_sensitive"),
                    InlineKeyboardButton("❌ Skip file", callback_data="cancel"),
                ]])
            )
            return

        gh = get_github_client(telegram_id)
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")

        try:
            existing = repo.get_contents(file_path, ref=branch)
            old_content = base64.b64decode(existing.content).decode("utf-8", errors="replace")
            if old_content == new_content:
                clear_state(telegram_id)
                await update.message.reply_text(
                    f"⏭️ <b>No changes detected</b>\n<code>{h(file_path)}</code> is identical to GitHub. Nothing committed.",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
                )
                return
            diff, changed = get_file_diff(old_content, new_content, filename)
            sha = existing.sha
            set_state(telegram_id, "confirming_single_commit", {"path": file_path, "content": new_content, "sha": sha, "is_new": False})
            await show_diff_preview(update.message, file_path, diff, changed, is_new=False)
        except GithubException:
            set_state(telegram_id, "confirming_single_commit", {"path": file_path, "content": new_content, "sha": None, "is_new": True})
            await show_diff_preview(update.message, file_path, "", 0, is_new=True)
    except Exception as e:
        logger.error(f"Single file error: {e}")
        clear_state(telegram_id)
        await update.message.reply_text(
            "❌ <b>Upload failed</b>\n<b>Reason:</b> File arrived damaged or upload interrupted.\n\n<b>Fix:</b> Try sending the file again.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Try again", callback_data="upload_single"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )


async def show_diff_preview(message, file_path: str, diff: str, changed: int, is_new: bool = False):
    if is_new:
        status = f"✨ <b>New file</b> — <code>{h(file_path)}</code> will be created"
    elif diff:
        status = f"🔄 <code>{h(file_path)}</code> — <b>{changed} lines changed</b>\n\n<pre>{h(diff[:1500])}</pre>"
    else:
        status = f"📄 <code>{h(file_path)}</code> — ready to commit"
    await message.reply_text(status, parse_mode="HTML", reply_markup=_commit_keyboard())


async def _handle_batch_file(update, context, state_data, document):
    telegram_id = update.effective_user.id
    paths = state_data.get("paths", [])
    files = state_data.get("files", {})
    current_index = state_data.get("current_index", 0)

    if current_index >= len(paths):
        await update.message.reply_text("✅ All files already received. Type /commit to review.", parse_mode="HTML")
        return

    current_path = paths[current_index]
    tg_file = await context.bot.get_file(document.file_id)
    content_bytes = await tg_file.download_as_bytearray()
    files[current_path] = content_bytes.decode("utf-8", errors="replace")
    next_index = current_index + 1
    set_state(telegram_id, "batch_collecting", {"paths": paths, "files": files, "current_index": next_index})

    if next_index >= len(paths):
        await update.message.reply_text(
            f"✅ <b>{len(paths)}/{len(paths)} files received!</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔍 Review Diff", callback_data="batch_review"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )
    else:
        await update.message.reply_text(
            f"✅ <b>{next_index}/{len(paths)}</b> → <code>{h(current_path)}</code> received\n\n"
            f"Next: <code>{h(paths[next_index])}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Batch", callback_data="cancel")]])
        )


async def _handle_zip(update, context, document, is_mirror: bool):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    await update.message.reply_text("📦 <b>ZIP received</b> — analyzing...", parse_mode="HTML")
    try:
        tg_file = await context.bot.get_file(document.file_id)
        content_bytes = await tg_file.download_as_bytearray()

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(content_bytes)

            if not zipfile.is_zipfile(zip_path):
                clear_state(telegram_id)
                await update.message.reply_text(
                    "❌ <b>ZIP file is corrupted</b>\n<b>Reason:</b> File arrived damaged.\n<b>Fix:</b> Re-compress and send again.",
                    parse_mode="HTML"
                )
                return

            with zipfile.ZipFile(zip_path, "r") as zf:
                all_names = [n for n in zf.namelist() if not n.endswith("/")]
                names = [n for n in all_names if not any(_should_ignore(p) for p in n.split("/"))]

                top_dirs = set()
                for name in names:
                    parts = name.split("/")
                    if len(parts) > 1:
                        top_dirs.add(parts[0])

                strip_prefix = None
                if len(top_dirs) == 1:
                    strip_prefix = list(top_dirs)[0] + "/"
                    detection_msg = f"✂️ Wrapper folder stripped: <code>{h(strip_prefix)}</code>"
                else:
                    detection_msg = "📁 No wrapper folder — committing as-is"

                file_map = {}
                sensitive_found = []
                for name in names:
                    clean = name[len(strip_prefix):] if strip_prefix and name.startswith(strip_prefix) else name
                    if not clean:
                        continue
                    clean = sanitize_path(clean)
                    if not clean:
                        continue
                    if is_sensitive_file(clean.split("/")[-1]):
                        sensitive_found.append(clean)
                        continue
                    try:
                        file_map[clean] = zf.read(name).decode("utf-8", errors="replace")
                    except Exception:
                        file_map[clean] = None  # binary

            gh = get_github_client(telegram_id)
            repo = gh.get_repo(session["active_repo"])
            branch = session.get("active_branch", "main")

            await update.message.reply_text(f"{detection_msg}\n🔄 Comparing with GitHub...", parse_mode="HTML")

            existing_files = {}
            try:
                def _get_all(path=""):
                    contents = repo.get_contents(path, ref=branch)
                    if not isinstance(contents, list):
                        contents = [contents]
                    for item in contents:
                        if item.type == "dir":
                            _get_all(item.path)
                        else:
                            existing_files[item.path] = item
                _get_all()
            except GithubException:
                pass

            new_files, modified_files, unchanged_files, deleted_files = [], [], [], []
            for path, content in file_map.items():
                if content is None:
                    modified_files.append(path)
                    continue
                if path in existing_files:
                    old = base64.b64decode(existing_files[path].content).decode("utf-8", errors="replace")
                    if content != old:
                        modified_files.append(path)
                    else:
                        unchanged_files.append(path)
                else:
                    new_files.append(path)

            if is_mirror:
                for path in existing_files:
                    if path not in file_map:
                        deleted_files.append(path)

            set_state(telegram_id, "confirming_zip_commit", {
                "file_map": {k: v for k, v in file_map.items() if v is not None},
                "new_files": new_files,
                "modified_files": modified_files,
                "unchanged_files": unchanged_files,
                "deleted_files": deleted_files,
                "sensitive_found": sensitive_found,
                "is_mirror": is_mirror,
                "existing_sha": {k: v.sha for k, v in existing_files.items()},
            })

            text = f"📊 <b>Analysis — {h(session['active_repo'])}</b>\n\n"
            if new_files:
                text += f"✨ <b>New ({len(new_files)}):</b>\n" + "\n".join(f"  + <code>{h(f)}</code>" for f in new_files[:5])
                if len(new_files) > 5:
                    text += f"\n  ... and {len(new_files)-5} more"
                text += "\n\n"
            if modified_files:
                text += f"🟡 <b>Modified ({len(modified_files)}):</b>\n" + "\n".join(f"  ~ <code>{h(f)}</code>" for f in modified_files[:5])
                if len(modified_files) > 5:
                    text += f"\n  ... and {len(modified_files)-5} more"
                text += "\n\n"
            if deleted_files and is_mirror:
                text += f"🗑️ <b>Will delete ({len(deleted_files)}):</b>\n" + "\n".join(f"  - <code>{h(f)}</code>" for f in deleted_files[:5])
                text += "\n\n"
            if unchanged_files:
                text += f"⏭️ <b>Unchanged:</b> {len(unchanged_files)} files (skipped)\n"
            if sensitive_found:
                text += f"\n⚠️ <b>Auto-excluded (sensitive):</b>\n" + "\n".join(f"  🔒 <code>{h(f)}</code>" for f in sensitive_found)

            await update.message.reply_text(text, parse_mode="HTML", reply_markup=_commit_keyboard())

    except Exception as e:
        logger.error(f"ZIP error: {e}")
        clear_state(telegram_id)
        await update.message.reply_text(
            f"❌ <b>ZIP processing failed</b>\n<b>Reason:</b> {h(str(e))}\n<b>Fix:</b> Re-compress and try again.",
            parse_mode="HTML"
        )


async def _handle_edit_return(update, context, state_data, document):
    telegram_id = update.effective_user.id
    file_path = state_data.get("path", "")
    original = state_data.get("original", "")
    sha = state_data.get("sha", "")
    tg_file = await context.bot.get_file(document.file_id)
    content_bytes = await tg_file.download_as_bytearray()
    new_content = content_bytes.decode("utf-8", errors="replace")
    if new_content == original:
        clear_state(telegram_id)
        await update.message.reply_text(
            "⏭️ <b>No changes detected</b> — file is identical. Nothing committed.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]])
        )
        return
    diff, changed = get_file_diff(original, new_content, file_path.split("/")[-1])
    set_state(telegram_id, "confirming_single_commit", {"path": file_path, "content": new_content, "sha": sha, "is_new": False})
    await show_diff_preview(update.message, file_path, diff, changed, is_new=False)


async def do_commit_single(message, telegram_id: int, commit_message: str, context=None):
    state_info = get_state(telegram_id)
    state_data = state_info.get("state_data", {})
    session = get_active_session(telegram_id)
    file_path = state_data.get("path")
    content = state_data.get("content")
    sha = state_data.get("sha")
    is_new = state_data.get("is_new", True)
    if not file_path or content is None:
        await message.reply_text("❌ No file data. Please re-upload.", parse_mode="HTML")
        clear_state(telegram_id)
        return
    gh = get_github_client(telegram_id)
    repo = gh.get_repo(session["active_repo"])
    branch = session.get("active_branch", "main")
    try:
        if is_new or not sha:
            repo.create_file(file_path, commit_message, content, branch=branch)
        else:
            repo.update_file(file_path, commit_message, content, sha, branch=branch)
        add_commit_message(telegram_id, session["github_username"], session["active_repo"], commit_message)
        clear_state(telegram_id)
        action = "Created" if (is_new or not sha) else "Updated"
        await message.reply_text(
            f"✅ <b>Committed</b> → <code>{h(branch)}</code>\n"
            f"📄 {action}: <code>{h(file_path)}</code>\n"
            f"💬 \"{h(commit_message)}\"\n\n"
            f"🔗 github.com/{h(session['active_repo'])}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 Log", callback_data="log"),
                InlineKeyboardButton("🌿 Branch", callback_data="branches"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        clear_state(telegram_id)
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def do_commit_batch(message, telegram_id: int, commit_message: str):
    state_info = get_state(telegram_id)
    state_data = state_info.get("state_data", {})
    session = get_active_session(telegram_id)
    files = state_data.get("files", {})
    if not files:
        await message.reply_text("❌ No files to commit.", parse_mode="HTML")
        clear_state(telegram_id)
        return
    gh = get_github_client(telegram_id)
    repo = gh.get_repo(session["active_repo"])
    branch = session.get("active_branch", "main")
    committed, skipped, failed = 0, 0, 0
    for path, content in files.items():
        try:
            try:
                existing = repo.get_contents(path, ref=branch)
                old = base64.b64decode(existing.content).decode("utf-8", errors="replace")
                if old == content:
                    skipped += 1
                    continue
                repo.update_file(path, commit_message, content, existing.sha, branch=branch)
            except GithubException as ge:
                if ge.status == 404:
                    repo.create_file(path, commit_message, content, branch=branch)
                else:
                    raise
            committed += 1
        except Exception as e:
            logger.error(f"Batch commit error {path}: {e}")
            failed += 1
    add_commit_message(telegram_id, session["github_username"], session["active_repo"], commit_message)
    clear_state(telegram_id)
    await message.reply_text(
        f"✅ <b>Batch committed</b> → <code>{h(branch)}</code>\n\n"
        f"📝 Committed: {committed}\n⏭️ Skipped: {skipped}\n❌ Failed: {failed}\n\n"
        f"💬 \"{h(commit_message)}\"",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("📜 Log", callback_data="log"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ]])
    )


async def do_commit_zip(message, telegram_id: int, commit_message: str):
    state_info = get_state(telegram_id)
    state_data = state_info.get("state_data", {})
    session = get_active_session(telegram_id)
    file_map = state_data.get("file_map", {})
    new_files = state_data.get("new_files", [])
    modified_files = state_data.get("modified_files", [])
    deleted_files = state_data.get("deleted_files", [])
    existing_sha = state_data.get("existing_sha", {})
    if not file_map:
        await message.reply_text("❌ No file data. Please re-upload the ZIP.", parse_mode="HTML")
        clear_state(telegram_id)
        return
    gh = get_github_client(telegram_id)
    repo = gh.get_repo(session["active_repo"])
    branch = session.get("active_branch", "main")
    committed, deleted_count, failed = 0, 0, 0
    try:
        for path in new_files + modified_files:
            content = file_map.get(path)
            if content is None:
                continue
            try:
                if path in existing_sha and path in modified_files:
                    repo.update_file(path, commit_message, content, existing_sha[path], branch=branch)
                else:
                    repo.create_file(path, commit_message, content, branch=branch)
                committed += 1
            except GithubException as e:
                logger.error(f"ZIP commit {path}: {e}")
                failed += 1
        for path in deleted_files:
            try:
                sha = existing_sha.get(path)
                if sha:
                    repo.delete_file(path, commit_message, sha, branch=branch)
                    deleted_count += 1
            except GithubException as e:
                logger.error(f"ZIP delete {path}: {e}")
                failed += 1
        add_commit_message(telegram_id, session["github_username"], session["active_repo"], commit_message)
        clear_state(telegram_id)
        await message.reply_text(
            f"✅ <b>ZIP committed</b> → <code>{h(branch)}</code>\n\n"
            f"✨ Created/Updated: {committed}\n🗑️ Deleted: {deleted_count}\n❌ Failed: {failed}\n\n"
            f"💬 \"{h(commit_message)}\"\n"
            f"🔗 github.com/{h(session['active_repo'])}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 Log", callback_data="log"),
                InlineKeyboardButton("⬇️ Download", callback_data="download_menu"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        clear_state(telegram_id)
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")
