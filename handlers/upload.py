import os
import io
import zipfile
import logging
import base64
import tempfile
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_active_session, get_state, set_state, clear_state,
    add_commit_message, get_commit_history, get_saved_paths, get_templates
)
from utils.github_helper import (
    get_github_client, get_repo, get_file_diff,
    is_sensitive_file, sanitize_path, get_error_message, build_tree
)
from handlers.core import escape_md
from github import GithubException

logger = logging.getLogger(__name__)

IGNORED_FILES = {
    "__pycache__", ".DS_Store", ".pyc", ".pyo",
    "Thumbs.db", ".git", "node_modules", ".idea",
    ".vscode", "*.egg-info", "dist", "build"
}

def should_ignore(name: str) -> bool:
    name_lower = name.lower()
    return any(
        name_lower == ig or name_lower.endswith(ig)
        for ig in IGNORED_FILES
    )


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Single file upload — declare path first."""
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.")
        return

    if not context.args:
        # Show upload menu
        await show_upload_menu(update.message, telegram_id)
        return

    # Path declared
    file_path = sanitize_path(" ".join(context.args))
    set_state(telegram_id, "awaiting_single_file", {"path": file_path})

    saved_paths = get_saved_paths(
        telegram_id,
        session["github_username"],
        session["active_repo"]
    )

    keyboard = [[
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]

    if is_sensitive_file(file_path):
        await update.message.reply_text(
            f"⚠️ *Sensitive file detected\\!*\n"
            f"`{escape_md(file_path)}` may contain secrets\\.\n\n"
            f"📬 Send the file now ↓",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text(
            f"📬 *Ready — send your file*\n\n"
            f"Will commit to: `{escape_md(session['active_repo'])}/{escape_md(file_path)}`\n\n"
            f"⏳ Waiting\\.\\.\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def show_upload_menu(message, telegram_id: int):
    keyboard = [
        [
            InlineKeyboardButton("📄 Single File", callback_data="upload_single"),
            InlineKeyboardButton("📦 Batch Files", callback_data="upload_batch"),
        ],
        [
            InlineKeyboardButton("🗜️ ZIP Mirror", callback_data="upload_mirror"),
            InlineKeyboardButton("🗜️ ZIP Update", callback_data="upload_update"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    await message.reply_text(
        "⬆️ *Upload — choose mode*",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Batch upload — declare paths, then send files."""
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.")
        return

    if not context.args:
        set_state(telegram_id, "batch_declare_paths", {})
        keyboard = [[
            InlineKeyboardButton("⭐ Saved Paths", callback_data="batch_saved_paths"),
            InlineKeyboardButton("📂 Browse", callback_data="batch_browse"),
        ], [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
        await update.message.reply_text(
            f"📋 *Batch Mode ON* — `{escape_md(session['active_repo'])}`\n\n"
            f"Declare your paths first:\n"
            f"Example: `/batch src/app\\.py utils/helper\\.js`\n\n"
            f"Or browse/pick from saved paths 👇",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Paths provided in command
    paths = [sanitize_path(p) for p in context.args]
    set_state(telegram_id, "batch_collecting", {
        "paths": paths,
        "files": {},
        "current_index": 0
    })

    path_list = "\n".join(f"{i+1}\\. `{escape_md(p)}`" for i, p in enumerate(paths))
    await update.message.reply_text(
        f"✅ *{len(paths)} paths registered:*\n{path_list}\n\n"
        f"📬 Now send files *IN ORDER*\\. I'll match them\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel Batch", callback_data="cancel")
        ]])
    )


async def cmd_mirror(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ZIP mirror mode."""
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    set_state(telegram_id, "awaiting_zip_mirror", {})
    await update.message.reply_text(
        f"🗜️ *Mirror mode* — `{escape_md(session['active_repo'])}` @ main\n\n"
        f"⚠️ ZIP will become *exact repo state*\n"
        f"Files missing from ZIP = deleted from repo\n\n"
        f"📬 Send your ZIP now",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]])
    )


async def cmd_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ZIP update mode."""
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    set_state(telegram_id, "awaiting_zip_update", {})
    await update.message.reply_text(
        f"🗜️ *Update mode* — `{escape_md(session['active_repo'])}` @ main\n\n"
        f"Only adds \\& modifies\\. Never deletes\\.\n\n"
        f"📬 Send your ZIP now",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]])
    )


async def handle_incoming_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Central handler for all incoming files."""
    telegram_id = update.effective_user.id
    state_info = get_state(telegram_id)
    state = state_info.get("state", "idle")
    state_data = state_info.get("state_data", {})

    document = update.message.document
    if not document:
        return

    filename = document.file_name or "file"

    if state == "awaiting_single_file":
        await handle_single_file(update, context, state_data, document)

    elif state == "batch_collecting":
        await handle_batch_file(update, context, state_data, document)

    elif state in ("awaiting_zip_mirror", "awaiting_zip_update"):
        if not filename.endswith(".zip"):
            session = get_active_session(telegram_id)
            await update.message.reply_text(
                f"❌ *Expected a ZIP file*\n"
                f"Reason: You sent `{escape_md(filename)}` but this mode requires a ZIP\\.\n\n"
                f"Fix: Compress your folder into a \\.zip file first\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📄 Switch to single upload",
                                         callback_data="upload_single"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
            return
        await handle_zip(update, context, state_data,
                          document, state == "awaiting_zip_mirror")

    elif state == "awaiting_edit_file":
        await handle_edit_return(update, context, state_data, document)

    else:
        # Unexpected file
        await update.message.reply_text(
            f"❓ *Unexpected file*\n"
            f"I wasn't expecting a file right now\\.\n\n"
            f"Use /upload \\<path\\> first, then send your file\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬆️ Upload menu", callback_data="upload_menu"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )


async def handle_single_file(update, context, state_data, document):
    telegram_id = update.effective_user.id
    declared_path = state_data.get("path", "")
    filename = document.file_name or "file"

    # Mismatch detection
    declared_filename = declared_path.split("/")[-1]
    if declared_filename and filename != declared_filename:
        set_state(telegram_id, "awaiting_single_file_mismatch", {
            **state_data,
            "sent_filename": filename,
            "file_id": document.file_id
        })
        keyboard = [[
            InlineKeyboardButton(f"✅ Use path: {declared_path}",
                                  callback_data="mismatch_use_path"),
            InlineKeyboardButton(f"✅ Use filename: {filename}",
                                  callback_data="mismatch_use_file"),
        ], [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
        await update.message.reply_text(
            f"⚠️ *Filename mismatch detected*\n\n"
            f"Path you specified: `{escape_md(declared_path)}`\n"
            f"File you sent: `{escape_md(filename)}`\n\n"
            f"Which should I use?",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await process_single_file(update, context, declared_path, document.file_id)


async def process_single_file(update, context, file_path: str, file_id: str):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)

    await update.message.reply_text("⏳ Analyzing file\\.\\.\\.", parse_mode="MarkdownV2")

    try:
        # Download file
        tg_file = await context.bot.get_file(file_id)
        content_bytes = await tg_file.download_as_bytearray()
        new_content = content_bytes.decode("utf-8", errors="replace")

        gh = get_github_client(telegram_id)
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")

        # Sensitive file check
        filename = file_path.split("/")[-1]
        if is_sensitive_file(filename):
            set_state(telegram_id, "confirming_sensitive_commit", {
                "path": file_path,
                "content": new_content,
                "file_id": file_id
            })
            keyboard = [[
                InlineKeyboardButton("✅ I know, commit anyway",
                                      callback_data="confirm_sensitive"),
                InlineKeyboardButton("❌ Skip file", callback_data="cancel")
            ]]
            await update.message.reply_text(
                f"⚠️ *Secrets file detected\\!*\n"
                f"Reason: `{escape_md(filename)}` typically contains API keys, "
                f"passwords and tokens\\. Committing this to GitHub — especially "
                f"a public repo — exposes your secrets to the entire internet permanently\\.\n\n"
                f"Are you absolutely sure?",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # Check if file exists
        try:
            existing = repo.get_contents(file_path, ref=branch)
            old_content = base64.b64decode(existing.content).decode("utf-8",
                                                                      errors="replace")

            if old_content == new_content:
                clear_state(telegram_id)
                await update.message.reply_text(
                    f"⏭️ *No changes detected*\n"
                    f"`{escape_md(file_path)}` is identical to what's on GitHub\\.\n"
                    f"Nothing committed\\.",
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🏠 Home", callback_data="home")
                    ]])
                )
                return

            # Show diff
            diff, changed = get_file_diff(old_content, new_content, filename)
            sha = existing.sha

            set_state(telegram_id, "confirming_single_commit", {
                "path": file_path,
                "content": new_content,
                "sha": sha,
                "is_new": False
            })

            await show_diff_preview(update.message, file_path, diff,
                                     changed, is_new=False)

        except GithubException:
            # New file
            set_state(telegram_id, "confirming_single_commit", {
                "path": file_path,
                "content": new_content,
                "sha": None,
                "is_new": True
            })
            await show_diff_preview(update.message, file_path, "",
                                     0, is_new=True)

    except Exception as e:
        logger.error(f"Single file error: {e}")
        clear_state(telegram_id)
        await update.message.reply_text(
            f"❌ *Upload incomplete — file corrupted*\n"
            f"Reason: The file arrived damaged or the upload was interrupted\\.\n"
            f"Nothing was committed\\.\n\n"
            f"Fix: Try sending the file again\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Try again", callback_data="upload_single"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )


async def show_diff_preview(message, file_path: str, diff: str,
                             changed: int, is_new: bool = False):
    if is_new:
        status = f"✨ *New file* — doesn't exist in repo yet\n\n\\+ `{escape_md(file_path)}` will be created"
    elif diff:
        diff_escaped = escape_md(diff[:1500])
        status = f"🔄 `{escape_md(file_path)}` — *{changed} lines changed*\n\n```\n{diff_escaped}\n```"
    else:
        status = f"📄 `{escape_md(file_path)}` — ready to commit"

    keyboard = [
        [
            InlineKeyboardButton("👁 Preview tree", callback_data="preview_tree"),
            InlineKeyboardButton("🤖 Auto-message", callback_data="commit_auto"),
        ],
        [
            InlineKeyboardButton("✏️ Write message", callback_data="commit_write"),
            InlineKeyboardButton("📋 Recent", callback_data="commit_recent"),
        ],
        [
            InlineKeyboardButton("📝 Templates", callback_data="commit_templates"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]
    ]

    await message.reply_text(
        status,
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_batch_file(update, context, state_data, document):
    telegram_id = update.effective_user.id
    paths = state_data.get("paths", [])
    files = state_data.get("files", {})
    current_index = state_data.get("current_index", 0)

    if current_index >= len(paths):
        await update.message.reply_text(
            "✅ All files already received\\!\nType /commit to review diff\\.",
            parse_mode="MarkdownV2"
        )
        return

    current_path = paths[current_index]
    tg_file = await context.bot.get_file(document.file_id)
    content_bytes = await tg_file.download_as_bytearray()
    content = content_bytes.decode("utf-8", errors="replace")

    files[current_path] = content
    next_index = current_index + 1

    set_state(telegram_id, "batch_collecting", {
        "paths": paths,
        "files": files,
        "current_index": next_index
    })

    if next_index >= len(paths):
        keyboard = [[
            InlineKeyboardButton("🔍 Review Diff", callback_data="batch_review"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
        await update.message.reply_text(
            f"✅ *{len(paths)}/{len(paths)} files received\\!*\n"
            f"All files received\\!",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        remaining = len(paths) - next_index
        await update.message.reply_text(
            f"✅ *{next_index}/{len(paths)}* → `{escape_md(current_path)}` received\n\n"
            f"Next: `{escape_md(paths[next_index])}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel Batch", callback_data="cancel")
            ]])
        )


async def handle_zip(update, context, state_data, document, is_mirror: bool):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)

    await update.message.reply_text(
        "📦 *ZIP received* \\— analyzing\\.\\.\\.",
        parse_mode="MarkdownV2"
    )

    try:
        tg_file = await context.bot.get_file(document.file_id)
        content_bytes = await tg_file.download_as_bytearray()

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, "upload.zip")
            with open(zip_path, "wb") as f:
                f.write(content_bytes)

            # Validate ZIP
            if not zipfile.is_zipfile(zip_path):
                clear_state(telegram_id)
                await update.message.reply_text(
                    "❌ *ZIP file is corrupted*\n"
                    "Reason: The ZIP arrived damaged — this usually happens when "
                    "the file was compressed incorrectly or the upload was interrupted\\.\n\n"
                    "Fix: Re\\-compress your folder and send again\\.",
                    parse_mode="MarkdownV2",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📤 Try again",
                            callback_data="upload_mirror" if is_mirror else "upload_update"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                    ]])
                )
                return

            with zipfile.ZipFile(zip_path, "r") as zf:
                all_names = [n for n in zf.namelist()
                             if not n.endswith("/")]

                # Filter ignored
                names = [n for n in all_names
                         if not any(should_ignore(part)
                                    for part in n.split("/"))]

                # Detect wrapper folder
                top_dirs = set()
                for name in names:
                    parts = name.split("/")
                    if len(parts) > 1:
                        top_dirs.add(parts[0])

                strip_prefix = None
                if len(top_dirs) == 1:
                    strip_prefix = list(top_dirs)[0] + "/"
                    detection_msg = f"✂️ Single root folder detected: `{escape_md(strip_prefix)}`\nStripping wrapper\\.\\.\\."
                elif len(top_dirs) == 0:
                    detection_msg = "📁 No wrapper folder detected — committing as\\-is"
                else:
                    detection_msg = f"📁 No single wrapper — committing as\\-is \\({len(top_dirs)} root folders\\)"

                # Strip prefix
                file_map = {}
                sensitive_found = []
                for name in names:
                    if strip_prefix and name.startswith(strip_prefix):
                        clean_name = name[len(strip_prefix):]
                    else:
                        clean_name = name

                    if not clean_name:
                        continue

                    # ZIP slip protection
                    clean_name = sanitize_path(clean_name)
                    if not clean_name:
                        continue

                    if is_sensitive_file(clean_name.split("/")[-1]):
                        sensitive_found.append(clean_name)
                        continue

                    try:
                        content = zf.read(name).decode("utf-8", errors="replace")
                        file_map[clean_name] = content
                    except Exception:
                        # Binary file
                        file_map[clean_name] = zf.read(name)

            # Now compare with GitHub
            gh = get_github_client(telegram_id)
            repo = gh.get_repo(session["active_repo"])
            branch = session.get("active_branch", "main")

            # Get all existing files
            await update.message.reply_text(
                f"{detection_msg}\n🔄 Comparing with GitHub\\.\\.\\.",
                parse_mode="MarkdownV2"
            )

            existing_files = {}
            try:
                def get_all_files(path=""):
                    contents = repo.get_contents(path, ref=branch)
                    if not isinstance(contents, list):
                        contents = [contents]
                    for item in contents:
                        if item.type == "dir":
                            get_all_files(item.path)
                        else:
                            existing_files[item.path] = item

                get_all_files()
            except GithubException:
                pass

            new_files = []
            modified_files = []
            unchanged_files = []
            deleted_files = []

            for path, content in file_map.items():
                if path in existing_files:
                    if isinstance(content, bytes):
                        modified_files.append(path)
                    else:
                        existing_content = base64.b64decode(
                            existing_files[path].content
                        ).decode("utf-8", errors="replace")
                        if content != existing_content:
                            modified_files.append(path)
                        else:
                            unchanged_files.append(path)
                else:
                    new_files.append(path)

            if is_mirror:
                for path in existing_files:
                    if path not in file_map:
                        deleted_files.append(path)

            # Store for confirmation
            set_state(telegram_id, "confirming_zip_commit", {
                "file_map": {k: v if isinstance(v, str) else None
                             for k, v in file_map.items()},
                "new_files": new_files,
                "modified_files": modified_files,
                "unchanged_files": unchanged_files,
                "deleted_files": deleted_files,
                "sensitive_found": sensitive_found,
                "is_mirror": is_mirror,
                "existing_sha": {
                    k: v.sha for k, v in existing_files.items()
                }
            })

            # Build summary
            text = f"📊 *Analysis complete* — `{escape_md(session['active_repo'])}`\n\n"

            if new_files:
                text += f"✨ *New \\({len(new_files)}\\):*\n"
                for f in new_files[:5]:
                    text += f"   \\+ `{escape_md(f)}`\n"
                if len(new_files) > 5:
                    text += f"   _and {len(new_files)-5} more_\n"
                text += "\n"

            if modified_files:
                text += f"🟡 *Modified \\({len(modified_files)}\\):*\n"
                for f in modified_files[:5]:
                    text += f"   ~ `{escape_md(f)}`\n"
                if len(modified_files) > 5:
                    text += f"   _and {len(modified_files)-5} more_\n"
                text += "\n"

            if deleted_files and is_mirror:
                text += f"🗑️ *Will delete \\({len(deleted_files)}\\):*\n"
                for f in deleted_files[:5]:
                    text += f"   \\- `{escape_md(f)}`\n"
                text += "\n"

            if unchanged_files:
                text += f"⏭️ *Unchanged:* {len(unchanged_files)} files \\(skipped\\)\n"

            if sensitive_found:
                text += f"\n⚠️ *Auto\\-excluded \\(sensitive\\):*\n"
                for f in sensitive_found:
                    text += f"   🔒 `{escape_md(f)}`\n"

            keyboard = [
                [
                    InlineKeyboardButton("👁 Preview tree",
                        callback_data="preview_zip_tree"),
                ],
                [
                    InlineKeyboardButton("✏️ Write message",
                        callback_data="commit_write"),
                    InlineKeyboardButton("🤖 Auto-generate",
                        callback_data="commit_auto"),
                ],
                [
                    InlineKeyboardButton("📋 Recent", callback_data="commit_recent"),
                    InlineKeyboardButton("📝 Templates",
                        callback_data="commit_templates"),
                ],
                [
                    InlineKeyboardButton("✅ Commit", callback_data="confirm_zip_commit"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]

            await update.message.reply_text(
                text, parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except Exception as e:
        logger.error(f"ZIP processing error: {e}")
        clear_state(telegram_id)
        await update.message.reply_text(
            f"❌ *Failed to process ZIP*\n"
            f"Reason: {escape_md(str(e))}\n\n"
            f"Fix: Try re\\-compressing and sending again\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📤 Try again",
                    callback_data="upload_mirror" if is_mirror else "upload_update"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )


async def handle_edit_return(update, context, state_data, document):
    """Handle file returned after /edit."""
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
            "⏭️ *No changes detected* — file is identical\\.\nNothing committed\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 Home", callback_data="home")
            ]])
        )
        return

    diff, changed = get_file_diff(original, new_content,
                                   file_path.split("/")[-1])

    set_state(telegram_id, "confirming_single_commit", {
        "path": file_path,
        "content": new_content,
        "sha": sha,
        "is_new": False
    })

    await show_diff_preview(update.message, file_path, diff,
                             changed, is_new=False)


async def do_commit_single(update_or_message, telegram_id: int,
                            commit_message: str, context=None):
    """Execute the actual single file commit."""
    from database.db import add_commit_message as save_msg
    state_info = get_state(telegram_id)
    state_data = state_info.get("state_data", {})
    session = get_active_session(telegram_id)

    file_path = state_data.get("path")
    content = state_data.get("content")
    sha = state_data.get("sha")
    is_new = state_data.get("is_new", True)

    gh = get_github_client(telegram_id)
    repo = gh.get_repo(session["active_repo"])
    branch = session.get("active_branch", "main")

    # Main branch protection
    if branch == "main" or branch == "master":
        pass  # Already warned in UI

    try:
        if is_new or not sha:
            repo.create_file(file_path, commit_message,
                              content, branch=branch)
        else:
            repo.update_file(file_path, commit_message,
                              content, sha, branch=branch)

        save_msg(telegram_id, session["github_username"],
                 session["active_repo"], commit_message)
        clear_state(telegram_id)

        from handlers.core import escape_md
        repo_url = f"https://github.com/{session['active_repo']}"
        action = "Created" if is_new else "Updated"

        msg = (
            f"✅ *Committed* → `{escape_md(branch)}`\n"
            f"📄 {action}: `{escape_md(file_path)}`\n"
            f"💬 \"{escape_md(commit_message)}\"\n\n"
            f"🔗 [View on GitHub]({repo_url})"
        )

        keyboard = [[
            InlineKeyboardButton("📜 View Log", callback_data="log"),
            InlineKeyboardButton("🔄 Diff", callback_data="diff_menu"),
            InlineKeyboardButton("🌿 Branch", callback_data="branches"),
        ], [
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ]]

        if hasattr(update_or_message, 'reply_text'):
            await update_or_message.reply_text(
                msg, parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update_or_message.edit_message_text(
                msg, parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    except GithubException as e:
        clear_state(telegram_id)
        await update_or_message.reply_text(get_error_message(e.status))
