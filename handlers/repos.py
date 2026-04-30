import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_active_session, update_session, add_to_recent,
    get_state, set_state, clear_state
)
from utils.github_helper import (
    get_github_client, get_repo, format_size,
    format_time_ago, get_language_bar, get_error_message
)
from handlers.core import escape_md
from github import GithubException

logger = logging.getLogger(__name__)

GITIGNORE_TEMPLATES = [
    "Python", "Node", "Java", "Go", "Ruby",
    "Swift", "C++", "Rust", "None"
]

LICENSES = {
    "MIT": "mit",
    "Apache 2.0": "apache-2.0",
    "GPL 3.0": "gpl-3.0",
    "BSD": "bsd-2-clause",
    "None": None
}

STARTERS = {
    "🐍 Python": ["README.md", "main.py", "requirements.txt", ".gitignore"],
    "⚡ Node.js": ["README.md", "index.js", "package.json", ".gitignore"],
    "🌐 HTML/CSS": ["README.md", "index.html", "style.css", "script.js"],
    "📱 React": ["README.md", "src/App.jsx", "src/index.js", "package.json"],
    "Empty": []
}


async def cmd_repos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_repos(update.message, telegram_id, page=0)


async def show_repos(message, telegram_id: int, page: int = 0,
                     sort: str = "updated", edit: bool = False):
    gh = get_github_client(telegram_id)
    if not gh:
        await message.reply_text("❌ Not logged in. Use /login first.")
        return

    try:
        user = gh.get_user()
        all_repos = sorted(
            list(user.get_repos()),
            key=lambda r: r.pushed_at or r.updated_at,
            reverse=True
        )
        if sort == "stars":
            all_repos.sort(key=lambda r: r.stargazers_count, reverse=True)
        elif sort == "size":
            all_repos.sort(key=lambda r: r.size, reverse=True)
        elif sort == "name":
            all_repos.sort(key=lambda r: r.name.lower())

        total = len(all_repos)
        public_count = sum(1 for r in all_repos if not r.private)
        private_count = total - public_count

        per_page = 8
        start = page * per_page
        end = start + per_page
        page_repos = all_repos[start:end]
        total_pages = (total + per_page - 1) // per_page

        text = (
            f"📦 *Your GitHub Repos — {escape_md(user.login)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Total: {total} repos\n"
            f"🌍 Public: {public_count}  •  🔒 Private: {private_count}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for repo in page_repos:
            vis = "🔒" if repo.private else "🌍"
            lang = repo.language or "?"
            stars = repo.stargazers_count
            forks = repo.forks_count
            size = format_size(repo.size)
            updated = format_time_ago(repo.pushed_at or repo.updated_at)
            last_commit = ""

            text += (
                f"{vis} *{escape_md(repo.name)}*\n"
                f"   {lang}  •  ⭐{stars}  •  🍴{forks}  •  {escape_md(size)}\n"
                f"   Last edited: {escape_md(updated)}\n\n"
            )

            toggle_label = "🔒→🌍 Make Public" if repo.private else "🌍→🔒 Make Private"
            toggle_data = f"toggle_vis_{repo.full_name}"
            keyboard.append([
                InlineKeyboardButton(toggle_label, callback_data=toggle_data),
                InlineKeyboardButton("📂 Open", callback_data=f"open_repo_{repo.full_name}")
            ])

        # Pagination
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️ Prev",
                       callback_data=f"repos_page_{page-1}_{sort}"))
        nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
        if end < total:
            nav.append(InlineKeyboardButton("Next ➡️",
                       callback_data=f"repos_page_{page+1}_{sort}"))
        keyboard.append(nav)

        # Sort buttons
        keyboard.append([
            InlineKeyboardButton("📅 Date", callback_data=f"repos_sort_updated_{page}"),
            InlineKeyboardButton("⭐ Stars", callback_data=f"repos_sort_stars_{page}"),
            InlineKeyboardButton("📦 Size", callback_data=f"repos_sort_size_{page}"),
            InlineKeyboardButton("🔤 A-Z", callback_data=f"repos_sort_name_{page}"),
        ])
        keyboard.append([
            InlineKeyboardButton("🔍 Search", callback_data="search_repos"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"repos_page_0_{sort}"),
            InlineKeyboardButton("➕ New", callback_data="create_repo"),
        ])

        if edit and hasattr(message, 'edit_text'):
            await message.edit_text(text, parse_mode="MarkdownV2",
                                    reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await message.reply_text(text, parse_mode="MarkdownV2",
                                     reply_markup=InlineKeyboardMarkup(keyboard))

    except GithubException as e:
        await message.reply_text(get_error_message(e.status))


async def cmd_projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_projects(update.message, telegram_id)


async def show_projects(message, telegram_id: int, edit: bool = False):
    session = get_active_session(telegram_id)
    if not session:
        await message.reply_text("❌ Not logged in. Use /login first.")
        return

    username = session["github_username"]
    active_repo = session.get("active_repo")
    active_branch = session.get("active_branch", "main")
    recent_repos = session.get("recent_repos") or []
    pinned_repos = session.get("pinned_repos") or []

    text = f"🗄️ *Your Projects — {escape_md(username)}*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []

    # Pinned
    if pinned_repos:
        text += "━━━━ 📌 PINNED ━━━━\n"
        pin_row = []
        for repo in pinned_repos[:4]:
            name = repo.split("/")[-1]
            pin_row.append(InlineKeyboardButton(
                f"⭐ {name}", callback_data=f"open_repo_{repo}"))
        keyboard.append(pin_row)
        text += "\n"

    # Active
    if active_repo:
        text += f"━━━━ 🟢 ACTIVE ━━━━\n"
        text += f"📁 *{escape_md(active_repo)}* @ `{escape_md(active_branch)}`\n\n"
        keyboard.append([
            InlineKeyboardButton("📂 Open", callback_data="browse"),
            InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
            InlineKeyboardButton("📜 Log", callback_data="log"),
        ])
        text += "\n"

    # Recent
    if recent_repos:
        text += "━━━━ ⏱ RECENT ━━━━\n"
        for repo in recent_repos[:5]:
            name = repo.split("/")[-1]
            text += f"• {escape_md(name)}\n"
            keyboard.append([
                InlineKeyboardButton(f"📁 {name}", callback_data=f"open_repo_{repo}"),
                InlineKeyboardButton("⬆️", callback_data=f"upload_to_{repo}"),
                InlineKeyboardButton("📜", callback_data=f"log_of_{repo}"),
            ])

    keyboard.append([
        InlineKeyboardButton("➕ New Repo", callback_data="create_repo"),
        InlineKeyboardButton("🔍 Search", callback_data="search_repos"),
        InlineKeyboardButton("🔄 Refresh", callback_data="projects"),
    ])

    if edit and hasattr(message, 'edit_text'):
        await message.edit_text(text, parse_mode="MarkdownV2",
                                reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(text, parse_mode="MarkdownV2",
                                 reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    args = context.args

    if args:
        repo_name = args[0]
        set_state(telegram_id, "creating_repo", {"name": repo_name, "step": "visibility"})
        await ask_visibility(update.message, repo_name)
    else:
        set_state(telegram_id, "creating_repo", {"step": "name"})
        await update.message.reply_text(
            "📝 *New Repo*\n\nWhat's the repo name?",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data="cancel")
            ]])
        )


async def ask_visibility(message, repo_name: str):
    keyboard = [[
        InlineKeyboardButton("🌍 Public", callback_data="repo_vis_public"),
        InlineKeyboardButton("🔒 Private", callback_data="repo_vis_private"),
    ], [
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]
    await message.reply_text(
        f"🔒 *Visibility for* `{escape_md(repo_name)}`?",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_use(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    gh = get_github_client(telegram_id)
    if not gh:
        await update.message.reply_text("❌ Not logged in. Use /login first.")
        return

    if not context.args:
        await show_projects(update.message, telegram_id)
        return

    repo_name = context.args[0]
    try:
        # Support short name or full name
        session = get_active_session(telegram_id)
        username = session["github_username"]
        if "/" not in repo_name:
            repo_name = f"{username}/{repo_name}"

        repo = gh.get_repo(repo_name)
        update_session(telegram_id,
                       active_repo=repo.full_name,
                       active_branch=repo.default_branch)
        add_to_recent(telegram_id, repo.full_name)

        is_own = repo.owner.login == username
        vis = "🔒 Private" if repo.private else "🌍 Public"
        lang = repo.language or "?"
        size = format_size(repo.size)

        keyboard = [
            [
                InlineKeyboardButton("📂 Browse", callback_data="browse"),
                InlineKeyboardButton("⬆️ Upload", callback_data="upload_menu"),
                InlineKeyboardButton("⬇️ Download", callback_data="download_menu"),
            ],
            [
                InlineKeyboardButton("🌿 Branches", callback_data="branches"),
                InlineKeyboardButton("📜 History", callback_data="log"),
                InlineKeyboardButton("🔍 Search", callback_data="search_repo"),
            ],
            [
                InlineKeyboardButton("📝 Issues", callback_data="issues"),
                InlineKeyboardButton("🚀 Releases", callback_data="releases"),
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
            ],
            [
                InlineKeyboardButton("⚙️ Settings", callback_data="repo_settings"),
                InlineKeyboardButton("📌 Pin", callback_data=f"pin_repo_{repo.full_name}"),
            ]
        ]

        if not is_own:
            keyboard.append([
                InlineKeyboardButton("⚠️ Read-only — not your repo",
                                     callback_data="noop")
            ])

        await update.message.reply_text(
            f"✅ *Now working on* `{escape_md(repo.full_name)}`\n\n"
            f"{vis}  •  {escape_md(lang)}  •  {escape_md(size)}\n"
            f"Branch: `{escape_md(repo.default_branch)}`" +
            ("\n\n⚠️ Read\\-only — this isn't your repo\\.\nYou can: /ls /read /download"
             if not is_own else ""),
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def cmd_delete_repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session:
        await update.message.reply_text("❌ Not logged in.")
        return

    repo_name = context.args[0] if context.args else session.get("active_repo")
    if not repo_name:
        await update.message.reply_text(
            "❌ No repo specified.\nUsage: /deleterepo <reponame>"
        )
        return

    set_state(telegram_id, "deleting_repo_step1",
              {"repo": repo_name})

    await update.message.reply_text(
        f"⚠️ *Delete* `{escape_md(repo_name)}` *permanently?*\n\n"
        f"This is IRREVERSIBLE\\.\n\n"
        f"*Step 1/3* — Type the repo name in chat:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]])
    )


async def cmd_rename_repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /rename <current-name> <new-name>"
        )
        return

    old_name, new_name = context.args[0], context.args[1]
    set_state(telegram_id, "confirming_rename",
              {"old": old_name, "new": new_name})

    keyboard = [[
        InlineKeyboardButton(f"✅ Rename to {new_name}",
                             callback_data=f"confirm_rename_{old_name}_{new_name}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel")
    ]]
    await update.message.reply_text(
        f"✏️ Rename `{escape_md(old_name)}` → `{escape_md(new_name)}`?",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def cmd_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session:
        await update.message.reply_text("❌ Not logged in.")
        return

    repo_name = context.args[0] if context.args else session.get("active_repo")
    if not repo_name:
        await update.message.reply_text("❌ No repo specified.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(repo_name)
        current = "🔒 Private" if repo.private else "🌍 Public"
        action = "Make Public 🌍" if repo.private else "Make Private 🔒"
        callback = f"toggle_vis_{repo.full_name}"

        keyboard = [[
            InlineKeyboardButton(action, callback_data=callback),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]
        await update.message.reply_text(
            f"📁 `{escape_md(repo.full_name)}`\n"
            f"Current: {current}\n\n"
            f"Change visibility?",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))
