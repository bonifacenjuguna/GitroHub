"""File browsing & operations — GitroHub v1.2"""
import base64
import logging

from github import GithubException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import clear_state, get_active_session, get_state, set_state
from utils.github_helper import get_error_message, get_file_diff, get_github_client, h, is_sensitive_file, sanitize_path

logger = logging.getLogger(__name__)


def _breadcrumb(repo_name: str, path: str, branch: str) -> str:
    parts = [repo_name.split("/")[-1]]
    if path:
        parts.extend(path.split("/"))
    return " › ".join(parts) + f" @ {branch}"


async def cmd_browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.", parse_mode="HTML")
        return
    path = context.args[0] if context.args else ""
    await show_browse(update.message, telegram_id, path, send_new=True)


async def show_browse(msg_or_query, telegram_id: int, path: str = "", send_new: bool = False):
    session = get_active_session(telegram_id)
    repo_name = session["active_repo"]
    branch = session.get("active_branch", "main")
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(repo_name)
        contents = repo.get_contents(path, ref=branch)
        if not isinstance(contents, list):
            contents = [contents]
        contents.sort(key=lambda x: (x.type != "dir", x.name.lower()))

        breadcrumb = _breadcrumb(repo_name, path, branch)
        text = f"<code>{h(breadcrumb)}</code>\n━━━━━━━━━━━━━━━━━━\n\n"

        keyboard = []
        for item in contents:
            if item.type == "dir":
                text += f"📁 {h(item.name)}/\n"
                keyboard.append([InlineKeyboardButton(f"📁 {item.name}", callback_data=f"browse_{item.path}")])
            else:
                text += f"📄 {h(item.name)}\n"
                keyboard.append([
                    InlineKeyboardButton("👁 Read", callback_data=f"read_file_{item.path}"),
                    InlineKeyboardButton("✏️ Edit", callback_data=f"edit_file_{item.path}"),
                    InlineKeyboardButton("🗑️", callback_data=f"delete_file_{item.path}"),
                    InlineKeyboardButton("🔗", callback_data=f"copy_url_{item.path}"),
                ])

        # Breadcrumb nav buttons
        if path:
            parts = path.split("/")
            nav_row = [InlineKeyboardButton(f"📁 {repo_name.split('/')[-1]}", callback_data="browse_root")]
            for i in range(len(parts) - 1):
                partial = "/".join(parts[:i+1])
                nav_row.append(InlineKeyboardButton(f"📁 {parts[i]}", callback_data=f"browse_{partial}"))
            keyboard.append(nav_row)

        keyboard.append([
            InlineKeyboardButton("➕ Upload Here", callback_data=f"upload_to_path_{path}"),
            InlineKeyboardButton("🔍 Search", callback_data="search_repo"),
            InlineKeyboardButton("🏠 Root", callback_data="browse_root"),
        ])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])

        if send_new:
            await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

    except GithubException as e:
        err = get_error_message(e.status)
        if send_new:
            await msg_or_query.reply_text(err, parse_mode="HTML")
        else:
            await msg_or_query.edit_message_text(err, parse_mode="HTML")


async def cmd_read(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /read &lt;filepath&gt;", parse_mode="HTML")
        return
    await read_file(update.message, telegram_id, sanitize_path(" ".join(context.args)))


async def read_file(message, telegram_id: int, file_path: str):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        file_content = repo.get_contents(file_path, ref=branch)
        content = base64.b64decode(file_content.content).decode("utf-8", errors="replace")
        if len(content) > 3500:
            content = content[:3500] + f"\n\n... ({len(content)-3500} chars truncated)"
        parent = "/".join(file_path.split("/")[:-1])
        await message.reply_text(
            f"📄 <code>{h(file_path)}</code>\n━━━━━━━━━━━━━━━━━━\n<pre>{h(content)}</pre>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_file_{file_path}"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_file_{file_path}"),
                InlineKeyboardButton("🔗 URL", callback_data=f"copy_url_{file_path}"),
            ], [
                InlineKeyboardButton("⬅️ Back", callback_data=f"browse_{parent}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /edit &lt;filepath&gt;", parse_mode="HTML")
        return
    await start_edit(update.message, telegram_id, sanitize_path(" ".join(context.args)))


async def start_edit(message, telegram_id: int, file_path: str):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        import io
        repo = gh.get_repo(session["active_repo"])
        branch = session.get("active_branch", "main")
        file_content = repo.get_contents(file_path, ref=branch)
        content = base64.b64decode(file_content.content).decode("utf-8", errors="replace")
        set_state(telegram_id, "awaiting_edit_file", {
            "path": file_path,
            "sha": file_content.sha,
            "original": content,
        })
        await message.reply_document(
            document=io.BytesIO(content.encode("utf-8")),
            filename=file_path.split("/")[-1],
            caption=f"✏️ <b>Edit mode</b> — <code>{h(file_path)}</code>\n\nEdit this file and send it back ↩️",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel edit", callback_data="cancel")]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_delete_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /delete &lt;filepath&gt;", parse_mode="HTML")
        return
    file_path = sanitize_path(" ".join(context.args))
    await update.message.reply_text(
        f"🗑️ <b>Delete</b> <code>{h(file_path)}</code>?\n\nThis cannot be undone.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, delete", callback_data=f"confirm_delete_{file_path}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]])
    )


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.", parse_mode="HTML")
        return
    if not context.args:
        set_state(telegram_id, "awaiting_search", {})
        await update.message.reply_text(
            f"🔍 <b>Search in</b> <code>{h(session['active_repo'])}</code>\n\nSend your search term:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        )
        return
    await do_search(update.message, telegram_id, " ".join(context.args))


async def do_search(message, telegram_id: int, query: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    repo_name = session["active_repo"]
    try:
        results = list(gh.search_code(f"{query} repo:{repo_name}"))[:10]
        if not results:
            await message.reply_text(
                f"🔍 No results for <code>{h(query)}</code> in <code>{h(repo_name)}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Search again", callback_data="search_repo"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]])
            )
            return
        text = f"🔍 <b>Results for</b> <code>{h(query)}</code> in <code>{h(repo_name)}</code>\n━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []
        for item in results:
            text += f"📄 {h(item.path)}\n"
            keyboard.append([
                InlineKeyboardButton(f"👁 {item.name}", callback_data=f"read_file_{item.path}"),
                InlineKeyboardButton("✏️ Edit", callback_data=f"edit_file_{item.path}"),
            ])
        keyboard.append([
            InlineKeyboardButton("🔄 New search", callback_data="search_repo"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ])
        await message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /move &lt;source&gt; &lt;destination&gt;", parse_mode="HTML")
        return
    src = sanitize_path(context.args[0])
    dst = sanitize_path(context.args[1])
    await update.message.reply_text(
        f"📦 <b>Move file?</b>\n\nFrom: <code>{h(src)}</code>\nTo: <code>{h(dst)}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Yes, move", callback_data=f"confirm_move_{src}_TO_{dst}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]])
    )
