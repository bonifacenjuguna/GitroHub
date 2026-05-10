"""
Keyboard Builders — GitroHub v2.0
All InlineKeyboardMarkup and ReplyKeyboardMarkup builders.
Single source of truth for all buttons.
"""
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ── Bottom Menu (persistent) ──────────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    """2 rows × 3 columns main menu — shown when logged in."""
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="📁 Repos"),
        KeyboardButton(text="👤 Account"),
        KeyboardButton(text="🔍 Explore"),
    )
    kb.row(
        KeyboardButton(text="⚙️ Settings"),
        KeyboardButton(text="🔔 Notifs"),
        KeyboardButton(text="🗂️ More"),
    )
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


def auth_menu() -> ReplyKeyboardMarkup:
    """Single button shown when not authenticated."""
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="🔗 Connect GitHub"))
    return kb.as_markup(resize_keyboard=True, is_persistent=True)


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# ── Submenus (reply keyboard, replaces main) ──────────────────────────────────

def repos_submenu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="📋 My Repos"),
        KeyboardButton(text="➕ New Repository"),
    )
    kb.row(
        KeyboardButton(text="🍴 My Forks"),
        KeyboardButton(text="⭐ Starred"),
    )
    kb.row(
        KeyboardButton(text="⬅️ Back"),
        KeyboardButton(text="🏠 Home"),
        KeyboardButton(text="🔍 Search"),
    )
    return kb.as_markup(resize_keyboard=True)


def account_submenu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="👤 My Profile"),
        KeyboardButton(text="🔄 Switch Account"),
    )
    kb.row(
        KeyboardButton(text="➕ Add Account"),
        KeyboardButton(text="🚪 Disconnect"),
    )
    kb.row(
        KeyboardButton(text="⬅️ Back"),
        KeyboardButton(text="🏠 Home"),
        KeyboardButton(text="👥 Organizations"),
    )
    return kb.as_markup(resize_keyboard=True)


def settings_submenu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🔔 Notifications"),
        KeyboardButton(text="🎨 Display"),
    )
    kb.row(
        KeyboardButton(text="⌨️ Shortcuts"),
        KeyboardButton(text="💬 Private Msg"),
    )
    kb.row(
        KeyboardButton(text="⬅️ Back"),
        KeyboardButton(text="🏠 Home"),
        KeyboardButton(text="↩️ Reset All"),
    )
    return kb.as_markup(resize_keyboard=True)


def notifs_submenu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="📋 All Notifications"),
        KeyboardButton(text="🔵 Unread"),
    )
    kb.row(
        KeyboardButton(text="⚙️ Notif Settings"),
        KeyboardButton(text="✅ Mark All Read"),
    )
    kb.row(
        KeyboardButton(text="⬅️ Back"),
        KeyboardButton(text="🏠 Home"),
        KeyboardButton(text="🔕 Mute Repo"),
    )
    return kb.as_markup(resize_keyboard=True)


def more_submenu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🗂️ Projects"),
        KeyboardButton(text="🏓 Health"),
    )
    kb.row(
        KeyboardButton(text="🧬 What's New"),
        KeyboardButton(text="❓ Help"),
    )
    kb.row(
        KeyboardButton(text="⬅️ Back"),
        KeyboardButton(text="🏠 Home"),
        KeyboardButton(text="👥 Users"),
    )
    return kb.as_markup(resize_keyboard=True)


def explore_submenu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(
        KeyboardButton(text="🔍 Search Repos"),
        KeyboardButton(text="⬇️ Download by URL"),
    )
    kb.row(
        KeyboardButton(text="👤 Find User"),
        KeyboardButton(text="📈 Trending"),
    )
    kb.row(
        KeyboardButton(text="⬅️ Back"),
        KeyboardButton(text="🏠 Home"),
        KeyboardButton(text="🔎 Search Code"),
    )
    return kb.as_markup(resize_keyboard=True)


# ── Cancel button (inline) ────────────────────────────────────────────────────

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
    ]])


def cancel_back_kb(back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Back", callback_data=back_cb),
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
    ]])


# ── Dashboard ─────────────────────────────────────────────────────────────────

def dashboard_kb(has_repo: bool = False,
                 unread_notifs: int = 0) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if has_repo:
        b.row(
            InlineKeyboardButton(text="📁 Open Repo", callback_data="repo_open_active"),
            InlineKeyboardButton(text="⬆️ Upload", callback_data="upload_menu"),
        )
        b.row(
            InlineKeyboardButton(text="📜 Commits", callback_data="commits"),
            InlineKeyboardButton(text="🌿 Branches", callback_data="branches"),
        )
    notif_label = f"🔔 Notifications ({unread_notifs})" if unread_notifs > 0 else "🔔 Notifications"
    b.row(
        InlineKeyboardButton(text=notif_label, callback_data="notifs_all"),
        InlineKeyboardButton(text="📊 Stats", callback_data="stats"),
    )
    b.row(
        InlineKeyboardButton(text="🍴 My Forks", callback_data="forks"),
        InlineKeyboardButton(text="🛡️ Security", callback_data="security"),
    )
    return b.as_markup()


# ── Repos ─────────────────────────────────────────────────────────────────────

def repos_kb(page: int, total_pages: int, sort: str,
             repos: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for repo in repos:
        vis = "🔒" if repo["private"] else "🌍"
        b.row(InlineKeyboardButton(
            text=f"{vis} {repo['name']}",
            callback_data=f"repo_open:{repo['full_name']}"
        ))
    # Sort buttons
    b.row(
        InlineKeyboardButton(text="📅" + (" ✓" if sort == "pushed" else ""),
                             callback_data="repos_sort:pushed"),
        InlineKeyboardButton(text="⭐" + (" ✓" if sort == "stars" else ""),
                             callback_data="repos_sort:stars"),
        InlineKeyboardButton(text="📦" + (" ✓" if sort == "size" else ""),
                             callback_data="repos_sort:size"),
        InlineKeyboardButton(text="🔤" + (" ✓" if sort == "name" else ""),
                             callback_data="repos_sort:name"),
    )
    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"repos_page:{page-1}:{sort}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"repos_page:{page+1}:{sort}"))
    b.row(*nav)
    b.row(
        InlineKeyboardButton(text="➕ New Repository", callback_data="repo_create"),
        InlineKeyboardButton(text="🔍 Search", callback_data="explore_search"),
    )
    return b.as_markup()


def repo_detail_kb(repo_name: str, is_own: bool = True,
                    is_pinned: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📂 Browse Files", callback_data=f"browse:{repo_name}:"),
        InlineKeyboardButton(text="📜 Commits", callback_data=f"commits:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="🌿 Branches", callback_data=f"branches:{repo_name}"),
        InlineKeyboardButton(text="🔀 Pull Requests", callback_data=f"pulls:{repo_name}:open:0"),
    )
    b.row(
        InlineKeyboardButton(text="📝 Issues", callback_data=f"issues:{repo_name}:open:0"),
        InlineKeyboardButton(text="🚀 Releases", callback_data=f"releases:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="⚙️ Actions", callback_data=f"actions:{repo_name}"),
        InlineKeyboardButton(text="📊 Stats", callback_data=f"stats:{repo_name}"),
    )
    if is_own:
        b.row(
            InlineKeyboardButton(text="⬆️ Upload Files", callback_data="upload_menu"),
            InlineKeyboardButton(text="⚙️ Settings", callback_data=f"repo_settings:{repo_name}"),
        )
    else:
        b.row(
            InlineKeyboardButton(text="🍴 Fork", callback_data=f"repo_fork:{repo_name}"),
            InlineKeyboardButton(text="⭐ Star", callback_data=f"repo_star:{repo_name}"),
            InlineKeyboardButton(text="⬇️ Download", callback_data=f"dl_repo:{repo_name}"),
        )
    pin_label = "📌 Unpin" if is_pinned else "📌 Pin"
    pin_cb = f"repo_unpin:{repo_name}" if is_pinned else f"repo_pin:{repo_name}"
    b.row(
        InlineKeyboardButton(text=pin_label, callback_data=pin_cb),
        InlineKeyboardButton(text="⬅️ Back to Repos", callback_data="repos:0:pushed"),
        InlineKeyboardButton(text="🏠", callback_data="home"),
    )
    return b.as_markup()


def repo_settings_kb(repo_name: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✏️ Rename", callback_data=f"repo_rename:{repo_name}"),
        InlineKeyboardButton(text="🔒 Visibility", callback_data=f"repo_visibility:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="📄 Edit README", callback_data=f"file_edit:{repo_name}:README.md"),
        InlineKeyboardButton(text="🏷️ Topics", callback_data=f"repo_topics:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="📝 Description", callback_data=f"repo_description:{repo_name}"),
        InlineKeyboardButton(text="🌐 Website", callback_data=f"repo_website:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="📋 Template Repo", callback_data=f"repo_template:{repo_name}"),
        InlineKeyboardButton(text="📤 Transfer", callback_data=f"repo_transfer:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="📦 Archive", callback_data=f"repo_archive:{repo_name}"),
        InlineKeyboardButton(text="🗑️ Delete Repo", callback_data=f"repo_delete:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Files ─────────────────────────────────────────────────────────────────────

def browse_kb(repo_name: str, path: str, branch: str,
              items: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for item in items:
        if item["type"] == "dir":
            b.row(InlineKeyboardButton(
                text=f"📁 {item['name']}/",
                callback_data=f"browse:{repo_name}:{item['path']}"
            ))
        else:
            b.row(
                InlineKeyboardButton(text=f"👁 {item['name']}",
                                     callback_data=f"file_read:{repo_name}:{item['path']}"),
                InlineKeyboardButton(text="✏️", callback_data=f"file_edit:{repo_name}:{item['path']}"),
                InlineKeyboardButton(text="🗑️", callback_data=f"file_delete:{repo_name}:{item['path']}"),
                InlineKeyboardButton(text="🔗", callback_data=f"file_url:{repo_name}:{item['path']}:{branch}"),
            )
    # Breadcrumb nav
    if path:
        parts = path.split("/")
        nav = [InlineKeyboardButton(text=f"📁 {repo_name.split('/')[-1]}",
                                     callback_data=f"browse:{repo_name}:")]
        for i in range(len(parts) - 1):
            partial = "/".join(parts[:i + 1])
            nav.append(InlineKeyboardButton(text=f"📁 {parts[i]}",
                                             callback_data=f"browse:{repo_name}:{partial}"))
        b.row(*nav[:4])  # max 4 breadcrumbs per row
    b.row(
        InlineKeyboardButton(text="➕ New File", callback_data=f"file_create:{repo_name}:{path}"),
        InlineKeyboardButton(text="🔍 Search", callback_data=f"file_search:{repo_name}"),
        InlineKeyboardButton(text="⬆️ Upload", callback_data="upload_menu"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Root", callback_data=f"browse:{repo_name}:"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def file_view_kb(repo_name: str, path: str,
                 branch: str) -> InlineKeyboardMarkup:
    parent = "/".join(path.split("/")[:-1])
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✏️ Edit File", callback_data=f"file_edit:{repo_name}:{path}"),
        InlineKeyboardButton(text="🗑️ Delete", callback_data=f"file_delete:{repo_name}:{path}"),
    )
    b.row(
        InlineKeyboardButton(text="📜 File History", callback_data=f"file_history:{repo_name}:{path}"),
        InlineKeyboardButton(text="👤 Blame", callback_data=f"file_blame:{repo_name}:{path}"),
    )
    b.row(
        InlineKeyboardButton(text="⬇️ Download File", callback_data=f"file_download:{repo_name}:{path}"),
        InlineKeyboardButton(text="🔗 Copy URL", callback_data=f"file_url:{repo_name}:{path}:{branch}"),
    )
    b.row(
        InlineKeyboardButton(text="📦 Move", callback_data=f"file_move:{repo_name}:{path}"),
        InlineKeyboardButton(text="✏️ Rename", callback_data=f"file_rename:{repo_name}:{path}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Browse",
                             callback_data=f"browse:{repo_name}:{parent}"),
        InlineKeyboardButton(text="📁 Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠", callback_data="home"),
    )
    return b.as_markup()


# ── Upload / Commit ────────────────────────────────────────────────────────────

def upload_menu_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📄 Single File", callback_data="commit_single"),
        InlineKeyboardButton(text="📦 Multiple Files", callback_data="commit_batch"),
    )
    b.row(
        InlineKeyboardButton(text="🗜️ Push from ZIP", callback_data="commit_zip_mirror"),
        InlineKeyboardButton(text="🔄 Sync from ZIP", callback_data="commit_zip_sync"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
    )
    return b.as_markup()


def commit_message_kb(repo_name: str,
                       github_username: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✏️ Write Message", callback_data="commit_write_msg"),
        InlineKeyboardButton(text="🤖 Auto-Generate", callback_data="commit_auto_msg"),
    )
    b.row(
        InlineKeyboardButton(text="📋 Recent Messages", callback_data="commit_recent_msg"),
        InlineKeyboardButton(text="📝 Templates", callback_data="commit_template_msg"),
    )
    b.row(
        InlineKeyboardButton(text="👁 Preview Tree", callback_data="commit_preview_tree"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
    )
    return b.as_markup()


def commit_confirm_kb(back_cb: str = "upload_menu") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✅ Commit", callback_data="commit_confirm"),
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data=back_cb),
    )
    return b.as_markup()


def sensitive_file_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, commit anyway",
                              callback_data="commit_sensitive_confirm"),
         InlineKeyboardButton(text="❌ Skip this file",
                              callback_data="commit_sensitive_skip")],
        [InlineKeyboardButton(text="⬅️ Cancel all", callback_data="cancel")],
    ])


def mismatch_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Use declared path",
                              callback_data="mismatch_use_path"),
         InlineKeyboardButton(text="✅ Use file name",
                              callback_data="mismatch_use_file")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")],
    ])


# ── Branches ──────────────────────────────────────────────────────────────────

def branches_kb(repo_name: str, branches: list[dict],
                active_branch: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for branch in branches:
        is_active = branch["name"] == active_branch
        icon = "●" if is_active else "○"
        prot = "🔒" if branch["protected"] else ""
        label = f"{icon} {branch['name']} {prot}".strip()
        if is_active:
            b.row(InlineKeyboardButton(text=label, callback_data="noop"))
            b.row(
                InlineKeyboardButton(text="🔒 Branch Protection",
                                     callback_data=f"branch_protect:{repo_name}:{branch['name']}"),
                InlineKeyboardButton(text="🔀 Set Default",
                                     callback_data=f"branch_set_default:{repo_name}:{branch['name']}"),
            )
        else:
            row = [InlineKeyboardButton(text=label, callback_data="noop")]
            b.row(*row)
            b.row(
                InlineKeyboardButton(text="🔄 Checkout",
                                     callback_data=f"branch_checkout:{repo_name}:{branch['name']}"),
                InlineKeyboardButton(text="🔀 Merge",
                                     callback_data=f"branch_merge:{repo_name}:{branch['name']}"),
                InlineKeyboardButton(text="✏️ Rename",
                                     callback_data=f"branch_rename:{repo_name}:{branch['name']}"),
                InlineKeyboardButton(text="🗑️",
                                     callback_data=f"branch_delete:{repo_name}:{branch['name']}"),
            )
    b.row(
        InlineKeyboardButton(text="➕ New Branch", callback_data=f"branch_create:{repo_name}"),
        InlineKeyboardButton(text="🔀 Compare", callback_data=f"branch_compare:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Commits ───────────────────────────────────────────────────────────────────

def commits_kb(repo_name: str, branch: str, page: int,
               total_pages: int, commits: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for commit in commits:
        b.row(InlineKeyboardButton(
            text=f"🔸 {commit['sha_short']}  {commit['message'][:35]}",
            callback_data=f"commit_view:{repo_name}:{commit['sha']}"
        ))
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"commits_page:{repo_name}:{branch}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"commits_page:{repo_name}:{branch}:{page+1}"))
    b.row(*nav)
    b.row(
        InlineKeyboardButton(text="↩️ Revert Last", callback_data=f"commit_revert_last:{repo_name}:{branch}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🌿 Branches", callback_data=f"branches:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def commit_detail_kb(repo_name: str, sha: str,
                     branch: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="↩️ Revert Commit",
                             callback_data=f"commit_revert:{repo_name}:{branch}:{sha}"),
        InlineKeyboardButton(text="🔄 Reset to This",
                             callback_data=f"commit_reset:{repo_name}:{branch}:{sha}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Commits",
                             callback_data=f"commits:{repo_name}"),
        InlineKeyboardButton(text="📁 Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Pull Requests ─────────────────────────────────────────────────────────────

def pulls_kb(repo_name: str, state: str, page: int,
             total_pages: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🟢 Open" + (" ✓" if state == "open" else ""),
                             callback_data=f"pulls:{repo_name}:open:0"),
        InlineKeyboardButton(text="🔴 Closed" + (" ✓" if state == "closed" else ""),
                             callback_data=f"pulls:{repo_name}:closed:0"),
    )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"pulls:{repo_name}:{state}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"pulls:{repo_name}:{state}:{page+1}"))
    b.row(*nav)
    b.row(
        InlineKeyboardButton(text="➕ New Pull Request",
                             callback_data=f"pull_create:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def pull_detail_kb(repo_name: str, pr_number: int,
                   state: str, mergeable: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if state == "open":
        if mergeable:
            b.row(
                InlineKeyboardButton(text="🔀 Merge",
                                     callback_data=f"pull_merge:{repo_name}:{pr_number}:merge"),
                InlineKeyboardButton(text="⚡ Squash & Merge",
                                     callback_data=f"pull_merge:{repo_name}:{pr_number}:squash"),
                InlineKeyboardButton(text="🔄 Rebase & Merge",
                                     callback_data=f"pull_merge:{repo_name}:{pr_number}:rebase"),
            )
        b.row(
            InlineKeyboardButton(text="✅ Approve",
                                 callback_data=f"pull_approve:{repo_name}:{pr_number}"),
            InlineKeyboardButton(text="❌ Close PR",
                                 callback_data=f"pull_close:{repo_name}:{pr_number}"),
        )
    b.row(
        InlineKeyboardButton(text="🔍 View Diff",
                             callback_data=f"pull_diff:{repo_name}:{pr_number}"),
        InlineKeyboardButton(text="📜 Commits",
                             callback_data=f"pull_commits:{repo_name}:{pr_number}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to PRs",
                             callback_data=f"pulls:{repo_name}:open:0"),
        InlineKeyboardButton(text="📁 Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Issues ────────────────────────────────────────────────────────────────────

def issues_kb(repo_name: str, state: str, page: int,
              total_pages: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🟢 Open" + (" ✓" if state == "open" else ""),
                             callback_data=f"issues:{repo_name}:open:0"),
        InlineKeyboardButton(text="🔴 Closed" + (" ✓" if state == "closed" else ""),
                             callback_data=f"issues:{repo_name}:closed:0"),
    )
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"issues:{repo_name}:{state}:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"issues:{repo_name}:{state}:{page+1}"))
    b.row(*nav)
    b.row(InlineKeyboardButton(text="➕ New Issue", callback_data=f"issue_create:{repo_name}"))
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def issue_detail_kb(repo_name: str, issue_number: int,
                    state: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if state == "open":
        b.row(
            InlineKeyboardButton(text="💬 Comment",
                                 callback_data=f"issue_comment:{repo_name}:{issue_number}"),
            InlineKeyboardButton(text="🔴 Close Issue",
                                 callback_data=f"issue_close:{repo_name}:{issue_number}"),
        )
        b.row(
            InlineKeyboardButton(text="🏷️ Labels",
                                 callback_data=f"issue_label:{repo_name}:{issue_number}"),
            InlineKeyboardButton(text="👤 Assign",
                                 callback_data=f"issue_assign:{repo_name}:{issue_number}"),
            InlineKeyboardButton(text="🎯 Milestone",
                                 callback_data=f"issue_milestone:{repo_name}:{issue_number}"),
        )
    else:
        b.row(
            InlineKeyboardButton(text="🟢 Reopen Issue",
                                 callback_data=f"issue_reopen:{repo_name}:{issue_number}"),
            InlineKeyboardButton(text="💬 Comment",
                                 callback_data=f"issue_comment:{repo_name}:{issue_number}"),
        )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Issues",
                             callback_data=f"issues:{repo_name}:open:0"),
        InlineKeyboardButton(text="📁 Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Releases ──────────────────────────────────────────────────────────────────

def releases_kb(repo_name: str,
                releases: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for r in releases:
        label = f"{'🔖' if r['prerelease'] else '🚀'} {r['tag_name']} — {r['name'][:25]}"
        b.row(InlineKeyboardButton(text=label,
                                    callback_data=f"release_view:{repo_name}:{r['id']}"))
    b.row(InlineKeyboardButton(text="➕ Create Release",
                                callback_data=f"release_create:{repo_name}"))
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def release_detail_kb(repo_name: str, release_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🗑️ Delete Release",
                             callback_data=f"release_delete:{repo_name}:{release_id}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Releases",
                             callback_data=f"releases:{repo_name}"),
        InlineKeyboardButton(text="📁 Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Actions ───────────────────────────────────────────────────────────────────

def actions_kb(repo_name: str,
               workflows: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for wf in workflows:
        b.row(InlineKeyboardButton(
            text=f"⚙️ {wf['name']}",
            callback_data=f"action_workflow_view:{repo_name}:{wf['id']}"
        ))
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def workflow_detail_kb(repo_name: str, workflow_id: int,
                        run_id: int = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="▶️ Run Workflow",
                             callback_data=f"action_run:{repo_name}:{workflow_id}"),
    )
    if run_id:
        b.row(
            InlineKeyboardButton(text="⛔ Cancel Run",
                                 callback_data=f"action_cancel_run:{repo_name}:{run_id}"),
            InlineKeyboardButton(text="📜 View Logs",
                                 callback_data=f"action_logs:{repo_name}:{run_id}"),
        )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Actions",
                             callback_data=f"actions:{repo_name}"),
        InlineKeyboardButton(text="📁 Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Forks ─────────────────────────────────────────────────────────────────────

def forks_kb(forks: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for fork in forks:
        b.row(InlineKeyboardButton(
            text=f"🍴 {fork['full_name']}",
            callback_data=f"fork_view:{fork['full_name']}"
        ))
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def fork_detail_kb(fork_name: str,
                    parent_name: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔄 Sync Fork",
                             callback_data=f"fork_sync:{fork_name}"),
        InlineKeyboardButton(text="🔀 Contribute (PR)",
                             callback_data=f"fork_contribute:{fork_name}:{parent_name}"),
    )
    b.row(
        InlineKeyboardButton(text="📂 Browse My Fork",
                             callback_data=f"browse:{fork_name}:"),
        InlineKeyboardButton(text="🔍 Compare Changes",
                             callback_data=f"branch_compare:{fork_name}"),
    )
    b.row(
        InlineKeyboardButton(text="🗑️ Delete Fork",
                             callback_data=f"fork_delete:{fork_name}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Forks", callback_data="forks"),
        InlineKeyboardButton(text="📁 Open Fork", callback_data=f"repo_open:{fork_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Account ───────────────────────────────────────────────────────────────────

def accounts_kb(sessions: list[dict], oauth_url: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in sessions:
        uname = s["github_username"]
        label = f"✅ {uname} (active)" if s["is_active"] else f"   {uname}"
        if not s["is_active"]:
            b.row(
                InlineKeyboardButton(text=label, callback_data="noop"),
                InlineKeyboardButton(text="🔄 Switch",
                                     callback_data=f"account_switch:{uname}"),
                InlineKeyboardButton(text="🗑️",
                                     callback_data=f"account_disconnect:{uname}"),
            )
        else:
            b.row(
                InlineKeyboardButton(text=label, callback_data="noop"),
                InlineKeyboardButton(text="🚪 Disconnect",
                                     callback_data=f"account_disconnect:{uname}"),
            )
    b.row(InlineKeyboardButton(text="➕ Add GitHub Account", url=oauth_url))
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def profile_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✏️ Edit Profile", callback_data="profile_edit"),
        InlineKeyboardButton(text="⭐ Pinned Repos", callback_data="profile_pinned"),
    )
    b.row(
        InlineKeyboardButton(text="🔗 Social Links", callback_data="profile_edit_links"),
        InlineKeyboardButton(text="👥 Following", callback_data="profile_following"),
    )
    b.row(
        InlineKeyboardButton(text="👥 Followers", callback_data="profile_followers"),
        InlineKeyboardButton(text="🏢 Organizations", callback_data="profile_orgs"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def profile_edit_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="👤 Name", callback_data="profile_edit_name"),
        InlineKeyboardButton(text="📝 Bio", callback_data="profile_edit_bio"),
    )
    b.row(
        InlineKeyboardButton(text="🏢 Company", callback_data="profile_edit_company"),
        InlineKeyboardButton(text="📍 Location", callback_data="profile_edit_location"),
    )
    b.row(
        InlineKeyboardButton(text="🌐 Website", callback_data="profile_edit_website"),
        InlineKeyboardButton(text="🐦 Twitter", callback_data="profile_edit_twitter"),
    )
    b.row(
        InlineKeyboardButton(text="🔗 Social Links", callback_data="profile_edit_links"),
        InlineKeyboardButton(text="⚠️ Pronouns", callback_data="profile_edit_pronouns"),
    )
    b.row(
        InlineKeyboardButton(text="🎓 Learning", callback_data="profile_edit_learning"),
        InlineKeyboardButton(text="💼 Hireable", callback_data="profile_hireable"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Profile", callback_data="account_profile"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Notifications ─────────────────────────────────────────────────────────────

def notifs_kb(page: int, total: int, per_page: int,
              has_unread: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    total_pages = max(1, (total + per_page - 1) // per_page)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"notifs_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"notifs_page:{page+1}"))
    b.row(*nav)
    if has_unread:
        b.row(InlineKeyboardButton(text="✅ Mark All Read",
                                    callback_data="notifs_mark_all_read"))
    b.row(
        InlineKeyboardButton(text="⚙️ Notification Settings",
                             callback_data="notifs_settings"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def notif_item_kb(notif_id: int, url: str = None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    row = [InlineKeyboardButton(text="✅ Mark Read",
                                 callback_data=f"notif_read:{notif_id}")]
    if url:
        row.append(InlineKeyboardButton(text="🔗 View on GitHub", url=url))
    b.row(*row)
    b.row(InlineKeyboardButton(text="⬅️ Back to Notifications",
                                callback_data="notifs_all"))
    return b.as_markup()


def notifs_settings_kb(s: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    events = [
        ("⭐ Stars", "notif_stars"),
        ("🔀 Pull Requests", "notif_pulls"),
        ("📝 Issues", "notif_issues"),
        ("❌ Workflow Fail", "notif_workflow_fail"),
        ("✅ Workflow Pass", "notif_workflow_pass"),
        ("🚀 Releases", "notif_releases"),
        ("🍴 Forks", "notif_forks"),
        ("👤 Followers", "notif_followers"),
        ("🛡️ Security", "notif_security"),
        ("💬 Comments", "notif_comments"),
    ]
    for label, key in events:
        status = "✅" if s.get(key, False) else "🔕"
        b.row(InlineKeyboardButton(
            text=f"{status}  {label}",
            callback_data=f"notif_toggle:{key}"
        ))
    b.row(
        InlineKeyboardButton(text="⏰ Quiet Hours",
                             callback_data="notifs_quiet_hours"),
        InlineKeyboardButton(text="🔕 Mute a Repo",
                             callback_data="notifs_mute_repo"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="notifs_all"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Settings ──────────────────────────────────────────────────────────────────

def settings_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🎨 Theme", callback_data="settings_theme"),
        InlineKeyboardButton(text="🕐 Time Format", callback_data="settings_time"),
    )
    b.row(
        InlineKeyboardButton(text="📅 Date Format", callback_data="settings_date"),
        InlineKeyboardButton(text="🌐 Timezone", callback_data="settings_timezone"),
    )
    b.row(
        InlineKeyboardButton(text="💬 Private Message", callback_data="settings_pm"),
        InlineKeyboardButton(text="⌨️ Aliases", callback_data="settings_aliases"),
    )
    b.row(
        InlineKeyboardButton(text="📝 Templates", callback_data="settings_templates"),
        InlineKeyboardButton(text="⭐ Saved Paths", callback_data="settings_savedpaths"),
    )
    b.row(
        InlineKeyboardButton(text="↩️ Reset All", callback_data="settings_reset"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def theme_kb(current: str) -> InlineKeyboardMarkup:
    themes = [
        ("🌑 Dark", "dark"), ("☀️ Light", "light"),
        ("🌈 Monokai", "monokai"), ("💜 Dracula", "dracula"),
        ("🤍 GitHub", "github"),
    ]
    b = InlineKeyboardBuilder()
    for label, key in themes:
        check = " ✓" if current == key else ""
        b.row(InlineKeyboardButton(text=f"{label}{check}",
                                    callback_data=f"settings_set_theme:{key}"))
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Settings", callback_data="settings_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Explore ───────────────────────────────────────────────────────────────────

def explore_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔍 Search Repositories",
                             callback_data="explore_search"),
        InlineKeyboardButton(text="👤 Find User",
                             callback_data="explore_find_user"),
    )
    b.row(
        InlineKeyboardButton(text="⬇️ Download by URL",
                             callback_data="explore_download_url"),
        InlineKeyboardButton(text="🔎 Search Code",
                             callback_data="explore_search_code"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Projects (offline workspace) ──────────────────────────────────────────────

def projects_kb(projects: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for p in projects:
        file_count = len(p.get("files", {}))
        b.row(InlineKeyboardButton(
            text=f"🗂️ {p['name']}  ({file_count} files)",
            callback_data=f"project_open:{p['name']}"
        ))
    b.row(InlineKeyboardButton(text="➕ New Project",
                                callback_data="project_create"))
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


def project_detail_kb(name: str,
                       has_files: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="➕ Add File",
                             callback_data=f"project_add_file:{name}"),
        InlineKeyboardButton(text="📋 View Files",
                             callback_data=f"project_view_files:{name}"),
    )
    if has_files:
        b.row(
            InlineKeyboardButton(text="🚀 Push to GitHub",
                                 callback_data=f"project_push:{name}"),
        )
    b.row(
        InlineKeyboardButton(text="🗑️ Delete Project",
                             callback_data=f"project_delete:{name}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Projects", callback_data="projects"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Health ────────────────────────────────────────────────────────────────────

def health_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📜 View Logs", callback_data="health_logs"),
        InlineKeyboardButton(text="🔄 Refresh", callback_data="health"),
    )
    b.row(
        InlineKeyboardButton(text="🗑️ Clear Queue", callback_data="health_clear_queue"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Admin / Users ─────────────────────────────────────────────────────────────

def users_kb(users: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for user in users:
        if user["role"] == "admin":
            continue
        uname = user.get("github_username", str(user["telegram_id"]))
        b.row(
            InlineKeyboardButton(text=f"👤 {uname}", callback_data="noop"),
            InlineKeyboardButton(text="🔕 Revoke",
                                 callback_data=f"user_revoke:{user['telegram_id']}"),
        )
    b.row(
        InlineKeyboardButton(text="➕ New Invite", callback_data="user_invite"),
        InlineKeyboardButton(text="📊 Usage Stats", callback_data="user_stats"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Security ──────────────────────────────────────────────────────────────────

def security_kb(repo_name: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🛡️ Dependabot Alerts",
                             callback_data=f"security_alerts:{repo_name}"),
        InlineKeyboardButton(text="📋 Advisories",
                             callback_data=f"security_advisories:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="🔑 Deploy Keys",
                             callback_data=f"security_deploy_keys:{repo_name}"),
        InlineKeyboardButton(text="🔗 Webhooks",
                             callback_data=f"security_webhooks:{repo_name}"),
    )
    b.row(
        InlineKeyboardButton(text="⬅️ Back to Repo", callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Gists ─────────────────────────────────────────────────────────────────────

def gists_kb(gists: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for g in gists:
        desc = g["description"][:35]
        pub = "🌍" if g["public"] else "🔒"
        b.row(
            InlineKeyboardButton(text=f"{pub} {desc}",
                                 callback_data=f"gist_view:{g['id']}"),
            InlineKeyboardButton(text="🗑️",
                                 callback_data=f"gist_delete:{g['id']}"),
        )
    b.row(InlineKeyboardButton(text="➕ Create Gist",
                                callback_data="gist_create"))
    b.row(
        InlineKeyboardButton(text="⬅️ Back", callback_data="home"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Receipt / Confirmation (persistent output) ───────────────────────────────

def commit_receipt_kb(repo_name: str, branch: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📜 View Commits",
                             callback_data=f"commits:{repo_name}"),
        InlineKeyboardButton(text="📂 Browse Files",
                             callback_data=f"browse:{repo_name}:"),
    )
    b.row(
        InlineKeyboardButton(text="🌿 Branches",
                             callback_data=f"branches:{repo_name}"),
        InlineKeyboardButton(text="📁 Back to Repo",
                             callback_data=f"repo_open:{repo_name}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Error ─────────────────────────────────────────────────────────────────────

def error_kb(back_cb: str = "home") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🔄 Retry", callback_data=back_cb),
        InlineKeyboardButton(text="🏠 Home", callback_data="home"),
    )
    return b.as_markup()


# ── Confirm / Dangerous actions ───────────────────────────────────────────────

def confirm_dangerous_kb(confirm_cb: str,
                          cancel_cb: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Yes, proceed",
                              callback_data=confirm_cb),
         InlineKeyboardButton(text="❌ Cancel",
                              callback_data=cancel_cb)],
    ])


def delete_repo_step1_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
    ]])


def delete_repo_step3_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ I approved it",
                              callback_data="repo_delete_confirmed"),
         InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")],
    ])


# ── Helpers ───────────────────────────────────────────────────────────────────

def paginate_kb(current: int, total: int, base_cb: str) -> list:
    """Return a row of pagination buttons. base_cb must contain {page} placeholder."""
    row = []
    if current > 0:
        row.append(InlineKeyboardButton(
            text="⬅️", callback_data=base_cb.format(page=current - 1)
        ))
    row.append(InlineKeyboardButton(
        text=f"{current + 1}/{total}", callback_data="noop"
    ))
    if current < total - 1:
        row.append(InlineKeyboardButton(
            text="➡️", callback_data=base_cb.format(page=current + 1)
        ))
    return row
