import logging
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_active_session, get_state, set_state, clear_state, update_session
from utils.github_helper import get_github_client, get_error_message, format_time_ago
from handlers.core import escape_md
from github import GithubException

logger = logging.getLogger(__name__)


async def cmd_branch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.")
        return

    if context.args:
        # Create new branch
        branch_name = context.args[0]
        await create_branch(update.message, telegram_id, branch_name)
        return

    await show_branches(update.message, telegram_id)


async def show_branches(message, telegram_id: int, edit: bool = False):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        branches = list(repo.get_branches())
        active_branch = session.get("active_branch", "main")

        text = (
            f"🌿 *Branches — {escape_md(session['active_repo'].split('/')[-1])}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for branch in branches:
            is_active = branch.name == active_branch
            is_protected = branch.protected
            marker = "●" if is_active else " "
            prot_icon = "🔒" if is_protected else ""

            text += f"{marker} `{escape_md(branch.name)}` {prot_icon}\n"

            row = []
            if not is_active:
                row.append(InlineKeyboardButton(
                    "🔄 Switch",
                    callback_data=f"switch_branch_{branch.name}"
                ))
            else:
                row.append(InlineKeyboardButton(
                    "✅ Active", callback_data="noop"
                ))

            if not is_protected and not is_active:
                row.append(InlineKeyboardButton(
                    "🔀 Merge",
                    callback_data=f"merge_branch_{branch.name}"
                ))
                row.append(InlineKeyboardButton(
                    "🗑️",
                    callback_data=f"delete_branch_{branch.name}"
                ))
            elif is_active:
                row.append(InlineKeyboardButton(
                    "🔒 Protect",
                    callback_data=f"protect_branch_{branch.name}"
                ))

            keyboard.append(row)

        keyboard.append([
            InlineKeyboardButton("➕ New Branch", callback_data="new_branch"),
            InlineKeyboardButton("🔀 Diff branches", callback_data="diff_menu"),
        ])
        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data="home"),
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


async def create_branch(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        current_branch = session.get("active_branch", "main")

        # Get SHA of current branch
        ref = repo.get_git_ref(f"heads/{current_branch}")
        sha = ref.object.sha

        # Create new branch
        repo.create_git_ref(f"refs/heads/{branch_name}", sha)

        keyboard = [[
            InlineKeyboardButton("🔄 Switch to it",
                callback_data=f"switch_branch_{branch_name}"),
            InlineKeyboardButton("🌿 All branches", callback_data="branches"),
        ], [
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ]]

        await message.reply_text(
            f"✅ *Branch created\\!*\n\n"
            f"🌿 `{escape_md(branch_name)}` from `{escape_md(current_branch)}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        if e.status == 422:
            await message.reply_text(
                f"❌ *Branch already exists*\n"
                f"Reason: A branch named `{escape_md(branch_name)}` already exists "
                f"in this repo\\. GitHub doesn't allow duplicate branch names\\.\n\n"
                f"Fix: Choose a different name or switch to the existing branch\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Switch to it",
                        callback_data=f"switch_branch_{branch_name}"),
                    InlineKeyboardButton("✏️ New name", callback_data="new_branch"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
        else:
            await message.reply_text(get_error_message(e.status))


async def cmd_switch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await show_branches(update.message, telegram_id)
        return

    branch_name = context.args[0]
    await do_switch_branch(update.message, telegram_id, branch_name)


async def do_switch_branch(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        # Verify branch exists
        repo.get_branch(branch_name)
        update_session(telegram_id, active_branch=branch_name)

        # Main branch protection warning
        if branch_name in ("main", "master"):
            warning = (
                f"\n\n⚠️ *You're on main* — commits go directly to main\\.\n"
                f"Consider using a feature branch\\."
            )
        else:
            warning = ""

        await message.reply_text(
            f"✅ *Switched to* `{escape_md(branch_name)}`{warning}",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
                InlineKeyboardButton("📂 Browse", callback_data="browse"),
                InlineKeyboardButton("🌿 Branches", callback_data="branches"),
            ]])
        )

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def cmd_merge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /merge <branch-to-merge>\n"
            "Merges the specified branch into your current branch."
        )
        return

    branch_name = context.args[0]
    session = get_active_session(telegram_id)
    current = session.get("active_branch", "main")

    keyboard = [[
        InlineKeyboardButton(
            f"✅ Merge {branch_name} → {current}",
            callback_data=f"confirm_merge_{branch_name}"
        ),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]

    await update.message.reply_text(
        f"🔀 *Merge branch?*\n\n"
        f"From: `{escape_md(branch_name)}`\n"
        f"Into: `{escape_md(current)}`",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def do_merge(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    current = session.get("active_branch", "main")

    try:
        repo = gh.get_repo(session["active_repo"])
        merge = repo.merge(current, branch_name,
                            f"Merge {branch_name} into {current}")

        if merge is None:
            await message.reply_text(
                f"⏭️ *Nothing to merge*\n"
                f"`{escape_md(branch_name)}` is already up to date with `{escape_md(current)}`\\.",
                parse_mode="MarkdownV2"
            )
            return

        await message.reply_text(
            f"✅ *Merged successfully\\!*\n\n"
            f"`{escape_md(branch_name)}` → `{escape_md(current)}`\n"
            f"Commit: `{escape_md(merge.sha[:7])}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📜 View Log", callback_data="log"),
                InlineKeyboardButton("🌿 Branches", callback_data="branches"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )

    except GithubException as e:
        if e.status == 409:
            await message.reply_text(
                f"❌ *Merge conflict detected*\n"
                f"Reason: Both branches modified the same lines differently\\. "
                f"GitHub can't automatically decide which version to keep\\.\n\n"
                f"Fix: Resolve the conflict manually on GitHub then retry\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Resolve on GitHub",
                        url=f"https://github.com/{session['active_repo']}/compare/{branch_name}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
        else:
            await message.reply_text(get_error_message(e.status))


async def cmd_diff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /diff <branch1> <branch2>\n"
            "Example: /diff main dev"
        )
        return

    b1, b2 = context.args[0], context.args[1]
    gh = get_github_client(telegram_id)

    try:
        repo = gh.get_repo(session["active_repo"])
        comparison = repo.compare(b1, b2)

        ahead = comparison.ahead_by
        behind = comparison.behind_by
        files = list(comparison.files)[:10]

        text = (
            f"🔀 *Diff: `{escape_md(b1)}` vs `{escape_md(b2)}`*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"`{escape_md(b2)}` is:\n"
            f"⬆️ {ahead} commits ahead\n"
            f"⬇️ {behind} commits behind `{escape_md(b1)}`\n\n"
            f"*Changed files ({len(files)}):*\n"
        )

        for f in files:
            status_icon = {"added": "✨", "modified": "🟡",
                           "removed": "🗑️", "renamed": "📝"}.get(f.status, "📄")
            text += f"{status_icon} `{escape_md(f.filename)}`\n"

        keyboard = [[
            InlineKeyboardButton(
                f"🔀 Merge {b2} → {b1}",
                callback_data=f"confirm_merge_{b2}"
            ),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def delete_branch(message, telegram_id: int, branch_name: str):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    current = session.get("active_branch", "main")

    if branch_name == current:
        await message.reply_text(
            f"❌ *Cannot delete active branch*\n"
            f"Reason: You're currently on `{escape_md(branch_name)}`\\.\n"
            f"Switch to another branch first\\.",
            parse_mode="MarkdownV2"
        )
        return

    try:
        repo = gh.get_repo(session["active_repo"])
        ref = repo.get_git_ref(f"heads/{branch_name}")
        ref.delete()

        await message.reply_text(
            f"🗑️ *Branch deleted*\n\n"
            f"`{escape_md(branch_name)}` removed from "
            f"`{escape_md(session['active_repo'])}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🌿 All branches", callback_data="branches"),
                InlineKeyboardButton("🏠 Home", callback_data="home")
            ]])
        )

    except GithubException as e:
        if e.status == 422:
            await message.reply_text(
                f"❌ *Cannot delete protected branch*\n"
                f"Reason: `{escape_md(branch_name)}` is marked as protected\\. "
                f"Protected branches cannot be deleted directly\\.\n\n"
                f"Fix: Remove branch protection in repo settings first\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⚙️ Repo Settings",
                        callback_data="repo_settings"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
        else:
            await message.reply_text(get_error_message(e.status))
