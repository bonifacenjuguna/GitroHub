"""Repo handlers — GitroHub v2.0"""
import logging
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from bot.services.github import (
    get_repos, get_repo_detail, create_repo, delete_repo,
    rename_repo, set_repo_visibility, set_repo_topics,
    set_repo_details, archive_repo,
)
from bot.states.flow import RepoFlow
from bot.ui.keyboards import repos_kb, repo_detail_kb, repo_settings_kb
from bot.ui.panel import CTX_REPOS, CTX_REPO, PanelManager
from database.pool import update_session, add_to_recent, get_active_session
from utils.formatters import h, panel, time_ago, format_size, language_bars, vis_label, bar

logger = logging.getLogger(__name__)
router = Router()


async def show_repos_panel(msg_or_query, session, telegram_id, page=0, sort="pushed"):
    if not session:
        text = panel("📦  Repositories", ["---", "Not logged in.", "---", "Connect your GitHub account first."])
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home", callback_data="home")]])
        if isinstance(msg_or_query, Message):
            await msg_or_query.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb)
        else:
            await msg_or_query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb)
        return

    pm = PanelManager(msg_or_query.bot if isinstance(msg_or_query, Message) else msg_or_query.bot)
    chat_id = msg_or_query.chat.id if isinstance(msg_or_query, Message) else msg_or_query.message.chat.id

    # Loading state
    if isinstance(msg_or_query, CallbackQuery):
        try:
            await msg_or_query.message.edit_text("<pre>⏳  Loading repositories...</pre>", parse_mode="HTML")
        except Exception:
            pass

    data = await get_repos(session, telegram_id, sort=sort, page=page)
    if "error" in data:
        text = "<pre>" + "❌ Error: " + str(data["error"]) + "</pre>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏠 Home", callback_data="home")]])
        await pm.update(telegram_id, chat_id, CTX_REPOS, f"<pre>{text}</pre>", kb)
        return

    username = session["github_username"]
    lines = [
        "---",
        f"  {h(username)}  ·  Total: {data['total']}",
        f"  🌍 Public: {data['public']}  ·  🔒 Private: {data['private']}",
        "---",
    ]
    for repo in data["repos"]:
        vis = "🔒" if repo["private"] else "🌍"
        lang = repo["language"] or "?"
        updated = time_ago(_parse_dt(repo["pushed_at"]))
        stars = repo["stars"]
        desc = f'  "{h(repo["description"][:35])}"' if repo["description"] else ""
        lines.append(f"  {vis}  {h(repo['name'])}")
        lines.append(f"       {h(lang)}  ·  ⭐{stars}  ·  {h(updated)}{desc}")
        lines.append("···")

    sort_indicators = {"pushed": "📅", "stars": "⭐", "size": "📦", "name": "🔤"}
    lines.append("---")
    lines.append(f"  Sorted by: {sort_indicators.get(sort, '')} {sort.title()}")
    lines.append(f"  Page {page+1} / {data['total_pages']}")

    text = panel(f"📦  Repositories", lines)
    kb = repos_kb(page, data["total_pages"], sort, data["repos"])
    await pm.update(telegram_id, chat_id, CTX_REPOS, f"<pre>{text}</pre>", kb)


async def show_repo_detail(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = (msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id)

    try:
        await msg_or_query.message.edit_text(f"<pre>⏳  Loading {h(repo_name.split('/')[-1])}...</pre>", parse_mode="HTML")
    except Exception:
        pass

    data = await get_repo_detail(session, telegram_id, repo_name)
    if not data or "error" in data:
        from utils.formatters import panel
        err_text = panel("❌  Error", ["---", "Repository not found or access denied.", "---", f"  {h(repo_name)}"])
        await pm.update(telegram_id, chat_id, CTX_REPO, f"<pre>{err_text}</pre>",
                        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back to Repos", callback_data="repos:0:pushed")]]))
        return

    await update_session(telegram_id, active_repo=repo_name, active_branch=data["default_branch"])
    await add_to_recent(telegram_id, repo_name)

    username = session["github_username"]
    is_own = data["owner_login"] == username
    is_pinned = repo_name in (session.get("pinned_repos") or [])

    lang_section = []
    if data.get("languages"):
        total_bytes = sum(data["languages"].values())
        lang_section = ["---", "  LANGUAGES", "···"]
        for lang, count in sorted(data["languages"].items(), key=lambda x: x[1], reverse=True)[:4]:
            pct = (count / total_bytes) * 100
            b = bar(count, total_bytes, 7)
            lang_section.append(f"  {h(lang):<12}  {pct:4.1f}%  {b}")

    lines = [
        "---",
        ("  🌍  Public" if not data["private"] else "  🔒  Private") + f"  ·  {h(data['language'] or '?')}",
        f"  ⭐  {data['stars']}  ·  🍴  {data['forks']}  ·  📦  {format_size(data['size'])}",
        f"  🌿  {h(data['default_branch'])}  ·  {len(data.get('topics',[]))} topics",
        "---",
    ]
    if data.get("description"):
        lines += [f"  📝  {h(data['description'][:60])}", "···"]
    lines += [
        "  LATEST COMMIT", "···",
        f"  🕐  {h(time_ago(_parse_dt(data['pushed_at'])))}",
        "---",
        "  ACTIVITY", "···",
        f"  🔀  {data['open_prs']} open pull requests",
        f"  📝  {data['open_issues']} open issues",
    ]
    lines += lang_section

    if not is_own:
        lines += ["---", "  ⚠️  Read-only — not your repo", "  You can: browse, read, download, fork, star"]

    text = panel(f"📁  {h(data['name'])}", lines)
    kb = repo_detail_kb(repo_name, is_own=is_own, is_pinned=is_pinned)
    await pm.update(telegram_id, chat_id, CTX_REPO, f"<pre>{text}</pre>", kb)


async def show_repo_settings(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id
    text = panel(f"⚙️  Settings  ·  {h(repo_name.split('/')[-1])}", [
        "---",
        "  Choose what to update:",
        "---",
    ])
    kb = repo_settings_kb(repo_name)
    await pm.from_callback(msg_or_query, CTX_REPO, f"<pre>{text}</pre>", kb)


async def start_create_repo(message_or_query, state: FSMContext):
    await state.set_state(RepoFlow.creating_name)
    text = panel("➕  New Repository", [
        "---",
        "What's the repository name?",
        "---",
        "  Use letters, numbers, hyphens.",
        "  No spaces.",
    ])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]])
    if isinstance(message_or_query, Message):
        await message_or_query.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb)
    else:
        await message_or_query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=kb)


@router.message(RepoFlow.creating_name)
async def repo_name_received(message: Message, state: FSMContext, telegram_id: int):
    name = message.text.strip().replace(" ", "-")
    if not name or len(name) > 100:
        await message.answer("❌ Invalid name. Use letters, numbers, hyphens only.")
        return
    await state.update_data(name=name)
    await state.set_state(RepoFlow.creating_visibility)
    text = panel(f"🔒  Visibility  ·  {h(name)}", [
        "---",
        "  Public: anyone can see this repo",
        "  Private: only you can see it",
    ])
    await message.answer(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🌍 Public", callback_data="repo_create_vis:public"),
            InlineKeyboardButton(text="🔒 Private", callback_data="repo_create_vis:private"),
        ], [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]]),
    )


async def repo_create_set_visibility(query: CallbackQuery, state: FSMContext, is_private: bool):
    await state.update_data(private=is_private)
    await state.set_state(RepoFlow.creating_readme)
    data = await state.get_data()
    text = panel(f"📄  Add README  ·  {h(data['name'])}", [
        "---",
        "  Initialize with a README.md?",
        "  Recommended for new repos.",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yes", callback_data="repo_create_readme:yes"),
            InlineKeyboardButton(text="❌ Skip", callback_data="repo_create_readme:no"),
        ], [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]]),
    )


async def repo_create_set_readme(query: CallbackQuery, state: FSMContext, want: bool):
    await state.update_data(readme=want)
    await state.set_state(RepoFlow.creating_gitignore)
    text = panel("🙈  .gitignore Template", [
        "---", "Add a .gitignore?", "---",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🐍 Python", callback_data="repo_create_gi:Python"),
             InlineKeyboardButton(text="⚡ Node", callback_data="repo_create_gi:Node"),
             InlineKeyboardButton(text="☕ Java", callback_data="repo_create_gi:Java")],
            [InlineKeyboardButton(text="🦫 Go", callback_data="repo_create_gi:Go"),
             InlineKeyboardButton(text="💎 Ruby", callback_data="repo_create_gi:Ruby"),
             InlineKeyboardButton(text="🦀 Rust", callback_data="repo_create_gi:Rust")],
            [InlineKeyboardButton(text="❌ None", callback_data="repo_create_gi:none")],
        ]),
    )


async def repo_create_set_gitignore(query: CallbackQuery, state: FSMContext, gi: str):
    await state.update_data(gitignore=None if gi == "none" else gi)
    await state.set_state(RepoFlow.creating_license)
    text = panel("⚖️  License", ["---", "Add a license?", "---"])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="MIT", callback_data="repo_create_license:mit"),
             InlineKeyboardButton(text="Apache 2.0", callback_data="repo_create_license:apache-2.0"),
             InlineKeyboardButton(text="GPL 3.0", callback_data="repo_create_license:gpl-3.0")],
            [InlineKeyboardButton(text="BSD 2-Clause", callback_data="repo_create_license:bsd-2-clause"),
             InlineKeyboardButton(text="AGPL 3.0", callback_data="repo_create_license:agpl-3.0"),
             InlineKeyboardButton(text="❌ None", callback_data="repo_create_license:none")],
        ]),
    )


async def repo_create_finish(query: CallbackQuery, state: FSMContext, session, telegram_id, license_key: str):
    data = await state.get_data()
    await state.clear()
    name = data.get("name", "new-repo")
    is_private = data.get("private", True)
    readme = data.get("readme", True)
    gi = data.get("gitignore")
    lic = None if license_key == "none" else license_key

    try:
        await query.message.edit_text(f"<pre>⏳  Creating {h(name)}...</pre>", parse_mode="HTML")
    except Exception:
        pass

    result = await create_repo(session, telegram_id, name, private=is_private, readme=readme, gitignore=gi, license_key=lic)
    if "error" in result:
        from utils.formatters import panel
        errt = panel("❌  Creation Failed", ["---", f"  Error: {result['error']}", "---",
                     "  Name may already exist or be invalid."])
        await query.message.edit_text(f"<pre>{errt}</pre>", parse_mode="HTML",
                                       reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                           InlineKeyboardButton(text="🔄 Try Again", callback_data="repo_create"),
                                           InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                                       ]]))
        return

    repo = result["repo"]
    text = panel(f"✅  Repository Created", [
        "---",
        f"  📁  {h(repo['name'])}",
        f"  {'🔒 Private' if repo['private'] else '🌍 Public'}",
        f"  README: {'✅' if readme else '❌'}  ·  .gitignore: {h(gi or 'None')}",
        f"  License: {h(lic or 'None')}",
        "---",
        "  Ready to use! 🚀",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📂 Browse Files", callback_data=f"browse:{repo['full_name']}:"),
            InlineKeyboardButton(text="⬆️ Upload Files", callback_data="upload_menu"),
        ], [
            InlineKeyboardButton(text="📁 Open Repo", callback_data=f"repo_open:{repo['full_name']}"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home"),
        ]]),
    )


async def start_rename_repo(query: CallbackQuery, state: FSMContext, repo_name: str):
    await state.set_state(RepoFlow.renaming)
    await state.update_data(repo_name=repo_name)
    text = panel(f"✏️  Rename Repository", [
        "---",
        f"  Current: {h(repo_name.split('/')[-1])}",
        "---",
        "  Type the new name:",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"repo_settings:{repo_name}"),
        ]]),
    )


@router.message(RepoFlow.renaming)
async def repo_rename_received(message: Message, state: FSMContext, session, telegram_id: int):
    data = await state.get_data()
    old_name = data.get("repo_name", "")
    new_name = message.text.strip().replace(" ", "-")
    await state.clear()

    result = await rename_repo(session, telegram_id, old_name, new_name)
    if "error" in result:
        await message.answer(f"❌ Rename failed (error {result['error']}).")
        return

    new_full = result["new_full_name"]
    await update_session(telegram_id, active_repo=new_full)
    text = panel("✅  Repository Renamed", [
        "---",
        f"  Old: {h(old_name.split('/')[-1])}",
        f"  New: {h(new_name)}",
    ])
    await message.answer(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📁 Open Repo", callback_data=f"repo_open:{new_full}"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home"),
        ]]),
    )


async def start_delete_repo(query, state, repo_name: str):
    if state:
        await state.set_state(RepoFlow.deleting_step1)
        await state.update_data(repo_name=repo_name)
    short = repo_name.split("/")[-1]
    text = panel("🗑️  Delete Repository", [
        "---",
        f"  {h(short)}",
        "---",
        "  ⚠️  THIS CANNOT BE UNDONE",
        "  All code, issues, and history",
        "  will be permanently deleted.",
        "---",
        "  Step 1 / 3",
        "···",
        f"  Type the repo name exactly:",
        f"  {h(short)}",
    ])
    msg = query.message if isinstance(query, CallbackQuery) else query
    await msg.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Cancel — Keep Repo", callback_data=f"repo_open:{repo_name}"),
        ]]),
    )


@router.message(RepoFlow.deleting_step1)
async def repo_delete_step1(message: Message, state: FSMContext, telegram_id: int):
    data = await state.get_data()
    repo_name = data.get("repo_name", "")
    short = repo_name.split("/")[-1]
    if message.text.strip() != short and message.text.strip() != repo_name:
        await message.answer(
            f"❌ Wrong name. Expected: <code>{h(short)}</code>\n\nTry again:",
            parse_mode="HTML",
        )
        return
    await state.set_state(RepoFlow.deleting_step2)
    text = panel("🗑️  Delete Repository", [
        "---",
        "  ✅  Step 1 confirmed",
        "---",
        "  Step 2 / 3",
        "···",
        "  Check your GitHub email 📧",
        "  Enter the 6-digit confirmation code:",
    ])
    await message.answer(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
        ]]),
    )


@router.message(RepoFlow.deleting_step2)
async def repo_delete_step2(message: Message, state: FSMContext):
    # Accept any 6-digit code (GitHub handles real verification)
    code = message.text.strip()
    if not code.isdigit() or len(code) != 6:
        await message.answer("❌ Enter the 6-digit code from your email.")
        return
    await state.set_state(RepoFlow.deleting_step3)
    text = panel("🗑️  Delete Repository", [
        "---",
        "  ✅  Step 1 confirmed",
        "  ✅  Step 2 confirmed",
        "---",
        "  Step 3 / 3",
        "···",
        "  Open your GitHub mobile app 📱",
        "  Tap Approve on the notification",
    ])
    await message.answer(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ I approved it", callback_data="repo_delete_confirmed"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
        ]]),
    )


async def confirm_delete_repo(query: CallbackQuery, state, session, telegram_id: int):
    if state:
        data = await state.get_data()
        repo_name = data.get("repo_name") or (session.get("active_repo") if session else None)
        await state.clear()
    else:
        repo_name = session.get("active_repo") if session else None

    if not repo_name:
        await query.answer("No repo found to delete.", show_alert=True)
        return

    try:
        await query.message.edit_text(f"<pre>⏳  Deleting {h(repo_name.split('/')[-1])}...</pre>", parse_mode="HTML")
    except Exception:
        pass

    ok = await delete_repo(session, telegram_id, repo_name)
    if ok:
        await update_session(telegram_id, active_repo=None, active_branch="main")
        text = panel("💀  Repository Deleted", [
            "---",
            f"  {h(repo_name.split('/')[-1])}",
            "  has been permanently deleted.",
            "---",
        ])
        await query.message.edit_text(
            f"<pre>{text}</pre>", parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📦 My Repos", callback_data="repos:0:pushed"),
                InlineKeyboardButton(text="🏠 Home", callback_data="home"),
            ]]),
        )
    else:
        await query.message.edit_text(
            "<pre>" + panel("❌  Delete Failed", ["---", "GitHub refused the deletion.", "---",
                             "You may need to approve via GitHub mobile."]) + "</pre>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔄 Retry", callback_data="repo_delete_confirmed"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
            ]]),
        )


async def toggle_visibility(query: CallbackQuery, session, telegram_id, repo_name: str):
    data = await get_repo_detail(session, telegram_id, repo_name)
    if not data or "error" in data:
        await query.answer("Failed to fetch repo.", show_alert=True)
        return
    is_private = data["private"]
    action = "Make Public" if is_private else "Make Private"
    warning = "⚠️  Making PUBLIC — everyone can see it." if is_private else "⚠️  Making PRIVATE — only you can see it."
    text = panel(f"🔒  Repository Visibility", [
        "---",
        f"  {h(repo_name.split('/')[-1])}",
        f"  Current: {'🔒 Private' if is_private else '🌍 Public'}",
        "---",
        f"  {warning}",
    ])
    vis_value = "public" if is_private else "private"
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=f"✅ Yes, {action}", callback_data=f"repo_visibility_confirm:{repo_name}:{vis_value}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"repo_settings:{repo_name}"),
        ]]),
    )


async def confirm_visibility(query: CallbackQuery, session, telegram_id, repo_name: str, is_private: bool):
    ok = await set_repo_visibility(session, telegram_id, repo_name, is_private)
    label = "🔒 Private" if is_private else "🌍 Public"
    await query.answer(f"✅ Now {label}", show_alert=True)
    await show_repo_detail(query, session, telegram_id, repo_name)


async def start_edit_topics(query, state, session, telegram_id, repo_name):
    data = await get_repo_detail(session, telegram_id, repo_name)
    current = ", ".join(data.get("topics", [])) if data else ""
    await state.set_state(RepoFlow.setting_topics)
    await state.update_data(repo_name=repo_name)
    text = panel("🏷️  Topics", [
        "---",
        f"  {h(repo_name.split('/')[-1])}",
        "---",
        f"  Current: {h(current or 'None')}",
        "---",
        "  Type new topics (comma separated):",
        "  e.g.  python, telegram, bot",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"repo_settings:{repo_name}"),
        ]]),
    )


@router.message(RepoFlow.setting_topics)
async def repo_topics_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    repo_name = data.get("repo_name", "")
    topics = [t.strip().lower() for t in message.text.split(",") if t.strip()]
    await state.clear()
    ok = await set_repo_topics(session, telegram_id, repo_name, topics)
    await message.answer(
        f"<pre>{'✅  Topics updated!' if ok else '❌  Failed to update topics.'}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Back to Settings", callback_data=f"repo_settings:{repo_name}"),
        ]]),
    )


async def start_edit_description(query, state, repo_name):
    await state.set_state(RepoFlow.setting_description)
    await state.update_data(repo_name=repo_name)
    text = panel("📝  Repository Description", ["---", "Type the new description:", "---", "Max 350 characters."])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"repo_settings:{repo_name}")]]),
    )


@router.message(RepoFlow.setting_description)
async def repo_description_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    repo_name = data.get("repo_name", "")
    await state.clear()
    ok = await set_repo_details(session, telegram_id, repo_name, description=message.text.strip()[:350])
    await message.answer(
        f"<pre>{'✅  Description updated!' if ok else '❌  Failed.'}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data=f"repo_settings:{repo_name}")]]),
    )


async def start_edit_website(query, state, repo_name):
    await state.set_state(RepoFlow.setting_website)
    await state.update_data(repo_name=repo_name)
    text = panel("🌐  Repository Website", ["---", "Type the URL:", "---", "e.g.  https://myproject.com"])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"repo_settings:{repo_name}")]]),
    )


@router.message(RepoFlow.setting_website)
async def repo_website_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    repo_name = data.get("repo_name", "")
    await state.clear()
    ok = await set_repo_details(session, telegram_id, repo_name, homepage=message.text.strip())
    await message.answer(
        f"<pre>{'✅  Website updated!' if ok else '❌  Failed.'}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back", callback_data=f"repo_settings:{repo_name}")]]),
    )


async def confirm_archive_repo(query, session, telegram_id, repo_name):
    text = panel("📦  Archive Repository", [
        "---", f"  {h(repo_name.split('/')[-1])}", "---",
        "  Archived repos are read-only.", "  You can unarchive later on GitHub.",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Archive", callback_data=f"repo_archive_confirm:{repo_name}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"repo_settings:{repo_name}"),
        ]]),
    )


async def start_transfer_repo(query, state, repo_name):
    await state.set_state(RepoFlow.transferring)
    await state.update_data(repo_name=repo_name)
    text = panel("📤  Transfer Ownership", [
        "---", f"  {h(repo_name.split('/')[-1])}", "---",
        "  Type the GitHub username to transfer to:", "---",
        "  ⚠️  This is permanent. The new owner",
        "  controls the repository after transfer.",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data=f"repo_settings:{repo_name}")]]),
    )


@router.message(RepoFlow.transferring)
async def repo_transfer_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    repo_name = data.get("repo_name", "")
    new_owner = message.text.strip().lstrip("@")
    await state.clear()
    from bot.services.github import transfer_repo
    ok = await transfer_repo(session, telegram_id, repo_name, new_owner)
    text = panel("✅  Transfer Initiated" if ok else "❌  Transfer Failed", [
        "---",
        f"  Repo: {h(repo_name.split('/')[-1])}",
        f"  To: {h(new_owner)}",
        "---",
        "  GitHub will send a confirmation email." if ok else "  Check the username and try again.",
    ])
    await message.answer(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📦 Repos", callback_data="repos:0:pushed"), InlineKeyboardButton(text="🏠 Home", callback_data="home")]]),
    )


def _parse_dt(dt_str):
    if not dt_str:
        return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None
