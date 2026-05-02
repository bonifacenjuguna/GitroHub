"""Branch management — GitroHub v1.2"""
import logging

from github import GithubException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import get_active_session, update_session
from utils.github_helper import format_time_ago, get_error_message, get_github_client, h

logger = logging.getLogger(__name__)


async def cmd_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.", parse_mode="HTML")
        return
    if context.args:
        await create_branch(update.message, telegram_id, context.args[0])
        return
    await show_branches(update.message, telegram_id, send_new=True)


async def show_branches(msg_or_query, telegram_id: int, send_new: bool = False):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branches = list(repo.get_branches())
        active_branch = session.get("active_branch", "main")

        text = (
            f"🌿 <b>Branches — {h(repo.name)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for branch in branches:
            is_active = branch.name == active_branch
            is_protected = branch.protected
            marker = "●" if is_active else " "
            prot = "🔒" if is_protected else ""
            text += f"{marker} <code>{h(branch.name)}</code> {prot}\n"

            row = []
            if is_active:
                row.append(InlineKeyboardButton("✅ Active", callback_data="noop"))
                row.append(InlineKeyboardButton("🔒 Protect", callback_data=f"protect_branch_{branch.name}"))
            else:
                row.append(InlineKeyboardButton("🔄 Switch", callback_data=f"switch_branch_{branch.name}"))
                if not is_protected:
                    row.append(InlineKeyboardButton("🔀 Merge", callback_data=f"merge_branch_{branch.name}"))
                    row.append(InlineKeyboardButton("🗑️", callback_data=f"delete_branch_{branch.name}"))
            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("➕ New Branch", callback_data="new_branch"),
            InlineKeyboardButton("🔀 Diff", callback_data="diff_menu"),
        ])
        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data="home"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ])

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


async def create_branch(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        current = session.get("active_branch", "main")
        ref = repo.get_git_ref(f"heads/{current}")
        repo.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)
        await message.reply_text(
            f"✅ <b>Branch created!</b>\n\n🌿 <code>{h(branch_name)}</code> from <code>{h(current)}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Switch to it", callback_data=f"switch_branch_{branch_name}"),
                InlineKeyboardButton("🌿 All branches", callback_data="branches"),
            ]])
        )
    except GithubException as e:
        if e.status == 422:
            await message.reply_text(
                f"❌ <b>Branch already exists</b>\n<b>Reason:</b> <code>{h(branch_name)}</code> already exists.\n\n<b>Fix:</b> Choose a different name.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Switch to it", callback_data=f"switch_branch_{branch_name}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]])
            )
        else:
            await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await show_branches(update.message, telegram_id, send_new=True)
        return
    await do_switch_branch(update.message, telegram_id, context.args[0])


async def do_switch_branch(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        repo.get_branch(branch_name)  # verify exists
        update_session(telegram_id, active_branch=branch_name)
        warning = ""
        if branch_name in ("main", "master"):
            warning = "\n\n⚠️ You're on <b>main</b> — commits go directly here. Consider using a feature branch."
        await message.reply_text(
            f"✅ Switched to <code>{h(branch_name)}</code>{warning}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
                InlineKeyboardButton("📂 Browse", callback_data="browse"),
                InlineKeyboardButton("🌿 Branches", callback_data="branches"),
            ]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /merge &lt;branch-to-merge&gt;", parse_mode="HTML")
        return
    branch_name = context.args[0]
    session = get_active_session(telegram_id)
    current = session.get("active_branch", "main") if session else "main"
    await update.message.reply_text(
        f"🔀 <b>Merge branch?</b>\n\nFrom: <code>{h(branch_name)}</code>\nInto: <code>{h(current)}</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ Merge", callback_data=f"confirm_merge_{branch_name}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]])
    )


async def do_merge(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    current = session.get("active_branch", "main")
    try:
        repo = gh.get_repo(session["active_repo"])
        merge = repo.merge(current, branch_name, f"Merge {branch_name} into {current}")
        if merge is None:
            await message.reply_text(f"⏭️ Already up to date. Nothing to merge.", parse_mode="HTML")
            return
        await message.reply_text(
            f"✅ <b>Merged!</b>\n<code>{h(branch_name)}</code> → <code>{h(current)}</code>\nCommit: <code>{merge.sha[:7]}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 Log", callback_data="log"),
                InlineKeyboardButton("🌿 Branches", callback_data="branches"),
            ]])
        )
    except GithubException as e:
        if e.status == 409:
            await message.reply_text(
                "❌ <b>Merge conflict detected</b>\n<b>Reason:</b> Both branches modified the same lines.\n<b>Fix:</b> Resolve the conflict on GitHub first.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Resolve on GitHub", url=f"https://github.com/{session['active_repo']}/compare/{branch_name}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]])
            )
        else:
            await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /diff &lt;branch1&gt; &lt;branch2&gt;", parse_mode="HTML")
        return
    b1, b2 = context.args[0], context.args[1]
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        comparison = repo.compare(b1, b2)
        files = list(comparison.files)[:10]
        text = (
            f"🔀 <b>Diff: <code>{h(b1)}</code> vs <code>{h(b2)}</code></b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<code>{h(b2)}</code> is:\n"
            f"⬆️ {comparison.ahead_by} commits ahead\n"
            f"⬇️ {comparison.behind_by} commits behind <code>{h(b1)}</code>\n\n"
            f"<b>Changed files ({len(files)}):</b>\n"
        )
        for f in files:
            icon = {"added": "✨", "modified": "🟡", "removed": "🗑️", "renamed": "📝"}.get(f.status, "📄")
            text += f"{icon} <code>{h(f.filename)}</code>\n"
        await update.message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"🔀 Merge {b2}→{b1}", callback_data=f"confirm_merge_{b2}"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]])
        )
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def protect_branch(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        branch = repo.get_branch(branch_name)
        branch.edit_protection(required_approving_review_count=0, enforce_admins=False)
        await message.reply_text(
            f"🔒 <code>{h(branch_name)}</code> is now protected.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌿 Branches", callback_data="branches")]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def delete_branch(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    if branch_name == session.get("active_branch"):
        await message.reply_text(
            f"❌ <b>Cannot delete active branch</b>\nSwitch to another branch first.",
            parse_mode="HTML"
        )
        return
    try:
        repo = gh.get_repo(session["active_repo"])
        ref = repo.get_git_ref(f"heads/{branch_name}")
        ref.delete()
        await message.reply_text(
            f"🗑️ Branch <code>{h(branch_name)}</code> deleted.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌿 Branches", callback_data="branches")]])
        )
    except GithubException as e:
        if e.status == 422:
            await message.reply_text(
                "❌ <b>Cannot delete protected branch</b>\nRemove protection in repo settings first.",
                parse_mode="HTML"
            )
        else:
            await message.reply_text(get_error_message(e.status), parse_mode="HTML")
