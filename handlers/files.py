import logging
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_active_session, get_state, set_state, clear_state
from utils.github_helper import (
    get_github_client, get_repo, get_file_diff,
    is_sensitive_file, sanitize_path, get_error_message, build_tree
)
from handlers.core import escape_md
from github import GithubException, UnknownObjectException

logger = logging.getLogger(__name__)


def build_breadcrumb(repo_name: str, path: str, branch: str) -> str:
    """Build hamburger/breadcrumb navigation string."""
    parts = [f"📁 {repo_name.split('/')[-1]}"]
    if path:
        parts.extend(path.split("/"))
    return " > ".join(parts) + f" @ {branch}"


async def cmd_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text(
            "❌ No active repo. Use /use <reponame> first."
        )
        return

    path = context.args[0] if context.args else ""
    await show_browse(update.message, telegram_id, path)


async def show_browse(message, telegram_id: int, path: str = "",
                      edit: bool = False):
    session = get_active_session(telegram_id)
    repo_name = session["active_repo"]
    branch = session.get("active_branch", "main")

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(repo_name)
        contents = repo.get_contents(path, ref=branch)
        if not isinstance(contents, list):
            contents = [contents]

        # Sort: dirs first then files
        contents.sort(key=lambda x: (x.type != "dir", x.name.lower()))

        breadcrumb = build_breadcrumb(repo_name, path, branch)
        text = f"`{escape_md(breadcrumb)}`\n━━━━━━━━━━━━━━━━━━\n\n"

        keyboard = []
        for item in contents:
            if item.type == "dir":
                text += f"📁 {escape_md(item.name)}/\n"
                keyboard.append([
                    InlineKeyboardButton(
                        f"📁 {item.name}",
                        callback_data=f"browse_{item.path}"
                    )
                ])
            else:
                text += f"📄 {escape_md(item.name)}\n"
                keyboard.append([
                    InlineKeyboardButton("👁 Read",
                        callback_data=f"read_file_{item.path}"),
                    InlineKeyboardButton("✏️ Edit",
                        callback_data=f"edit_file_{item.path}"),
                    InlineKeyboardButton("🗑️",
                        callback_data=f"delete_file_{item.path}"),
                    InlineKeyboardButton("🔗",
                        callback_data=f"copy_url_{item.path}"),
                ])

        # Breadcrumb navigation buttons
        nav_row = []
        if path:
            # Build parent paths
            parts = path.split("/")
            # Root button
            nav_row.append(InlineKeyboardButton(
                f"📁 {repo_name.split('/')[-1]}",
                callback_data="browse_root"
            ))
            # Intermediate parts
            for i in range(len(parts) - 1):
                partial = "/".join(parts[:i+1])
                nav_row.append(InlineKeyboardButton(
                    f"📁 {parts[i]}",
                    callback_data=f"browse_{partial}"
                ))
            keyboard.append(nav_row)

        keyboard.append([
            InlineKeyboardButton("➕ Upload Here",
                callback_data=f"upload_to_path_{path}"),
            InlineKeyboardButton("🔍 Search",
                callback_data="search_repo"),
            InlineKeyboardButton("🏠 Root",
                callback_data="browse_root"),
        ])
        keyboard.append([
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ])

        if edit and hasattr(message, 'edit_text'):
            await message.edit_text(text, parse_mode="MarkdownV2",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await message.reply_text(text, parse_mode="MarkdownV2",
                                     reply_markup=InlineKeyboardMarkup(keyboard))

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def cmd_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /read <filepath>\nExample: /read src/app.py"
        )
        return

    file_path = sanitize_path(" ".join(context.args))
    await read_file(update.message, telegram_id, file_path)


async def read_file(message, telegram_id: int, file_path: str):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        file_content = repo.get_contents(file_path, ref=branch)

        content = base64.b64decode(file_content.content).decode("utf-8",
                                                                  errors="replace")

        # Truncate if too long for Telegram
        if len(content) > 3500:
            content = content[:3500] + f"\n\n... ({len(content) - 3500} chars truncated)"

        keyboard = [[
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit_file_{file_path}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_file_{file_path}"),
            InlineKeyboardButton("🔗 Copy URL", callback_data=f"copy_url_{file_path}"),
        ], [
            InlineKeyboardButton("⬅️ Back", callback_data=f"browse_{'/'.join(file_path.split('/')[:-1])}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]

        await message.reply_text(
            f"📄 `{escape_md(file_path)}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"```\n{content}\n```",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /edit <filepath>\nExample: /edit src/app.py"
        )
        return

    file_path = sanitize_path(" ".join(context.args))
    await start_edit(update.message, telegram_id, file_path)


async def start_edit(message, telegram_id: int, file_path: str):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        file_content = repo.get_contents(file_path, ref=branch)
        content = base64.b64decode(file_content.content).decode("utf-8",
                                                                  errors="replace")

        # Send current file to user
        import io
        file_bytes = content.encode("utf-8")
        filename = file_path.split("/")[-1]

        set_state(telegram_id, "awaiting_edit_file", {
            "path": file_path,
            "sha": file_content.sha,
            "original": content
        })

        await message.reply_document(
            document=io.BytesIO(file_bytes),
            filename=filename,
            caption=(
                f"✏️ *Edit mode — * `{escape_md(file_path)}`\n\n"
                f"Edit this file and send it back ↩️\n\n"
                f"Or type your changes directly as a message\\."
            ),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel edit", callback_data="cancel")
            ]])
        )

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def cmd_delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /delete <filepath>\nExample: /delete src/old.py"
        )
        return

    file_path = sanitize_path(" ".join(context.args))

    keyboard = [[
        InlineKeyboardButton("✅ Yes, delete",
                             callback_data=f"confirm_delete_{file_path}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]

    await update.message.reply_text(
        f"🗑️ *Delete* `{escape_md(file_path)}`?\n\nThis cannot be undone\\.",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.")
        return

    if not context.args:
        set_state(telegram_id, "awaiting_search", {})
        await update.message.reply_text(
            f"🔍 *Search in* `{escape_md(session['active_repo'])}`\n\n"
            f"Send your search term:",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )
        return

    query = " ".join(context.args)
    await do_search(update.message, telegram_id, query)


async def do_search(message, telegram_id: int, query: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    repo_name = session["active_repo"]

    try:
        repo = gh.get_repo(repo_name)
        # Search code in repo
        results = gh.search_code(f"{query} repo:{repo_name}")

        items = list(results[:10])
        if not items:
            await message.reply_text(
                f"🔍 No results for `{escape_md(query)}` in `{escape_md(repo_name)}`",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Search again", callback_data="search_repo"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
            return

        text = (f"🔍 *Results for* `{escape_md(query)}`\n"
                f"in `{escape_md(repo_name)}`\n"
                f"━━━━━━━━━━━━━━━━━━\n\n")

        keyboard = []
        for item in items:
            text += f"📄 {escape_md(item.path)}\n"
            keyboard.append([
                InlineKeyboardButton(f"👁 {item.name}",
                    callback_data=f"read_file_{item.path}"),
                InlineKeyboardButton("✏️ Edit",
                    callback_data=f"edit_file_{item.path}"),
            ])

        keyboard.append([
            InlineKeyboardButton("🔄 New search", callback_data="search_repo"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ])

        await message.reply_text(text, parse_mode="MarkdownV2",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def cmd_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /move <source> <destination>\n"
            "Example: /move src/old.py src/new_location/old.py"
        )
        return

    src = sanitize_path(context.args[0])
    dst = sanitize_path(context.args[1])

    keyboard = [[
        InlineKeyboardButton("✅ Yes, move", callback_data=f"confirm_move_{src}_{dst}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]
    await update.message.reply_text(
        f"📦 *Move file?*\n\n"
        f"From: `{escape_md(src)}`\n"
        f"To:   `{escape_md(dst)}`",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
