from typing import Optional, Any
"""
Central Callback Router — GitroHub v2.0
Routes all 211 callbacks to their handlers.
Every callback_data defined in keyboards.py is handled here.
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from bot.ui.panel import PanelManager
from utils.formatters import h, panel

logger = logging.getLogger(__name__)
router = Router()


# ── Helper: safe answer + route ───────────────────────────────────────────────

async def _answer(query: CallbackQuery):
    try:
        await query.answer()
    except Exception:
        pass


# ── Repos ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("repos:"))
async def cb_repos(query: CallbackQuery, session: Optional[dict],
                    telegram_id: int):
    await _answer(query)
    parts = query.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 0
    sort = parts[2] if len(parts) > 2 else "pushed"
    from bot.handlers.repos import show_repos_panel
    await show_repos_panel(query, session, telegram_id, page=page, sort=sort)


@router.callback_query(F.data.startswith("repos_page:"))
async def cb_repos_page(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    _, page, sort = query.data.split(":")
    from bot.handlers.repos import show_repos_panel
    await show_repos_panel(query, session, telegram_id,
                            page=int(page), sort=sort)


@router.callback_query(F.data.startswith("repos_sort:"))
async def cb_repos_sort(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    sort = query.data.split(":", 1)[1]
    from bot.handlers.repos import show_repos_panel
    await show_repos_panel(query, session, telegram_id, page=0, sort=sort)


@router.callback_query(F.data.startswith("repo_open:"))
async def cb_repo_open(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import show_repo_detail
    await show_repo_detail(query, session, telegram_id, repo_name)


@router.callback_query(F.data == "repo_open_active")
async def cb_repo_open_active(query: CallbackQuery, session: Optional[dict],
                               telegram_id: int):
    await _answer(query)
    if not session or not session.get("active_repo"):
        await query.message.answer("❌ No active repository. Select one from Repos.")
        return
    from bot.handlers.repos import show_repo_detail
    await show_repo_detail(query, session, telegram_id, session["active_repo"])


@router.callback_query(F.data == "repo_create")
async def cb_repo_create(query: CallbackQuery, state: FSMContext):
    await _answer(query)
    from bot.handlers.repos import start_create_repo
    await start_create_repo(query.message, state)


@router.callback_query(F.data.startswith("repo_settings:"))
async def cb_repo_settings(query: CallbackQuery, session: Optional[dict],
                             telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import show_repo_settings
    await show_repo_settings(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("repo_pin:"))
async def cb_repo_pin(query: CallbackQuery, session: Optional[dict],
                       telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from database.pool import get_active_session, update_session
    s = await get_active_session(telegram_id)
    if s:
        pinned = list(s.get("pinned_repos") or [])
        if repo_name not in pinned:
            pinned.append(repo_name)
            await update_session(telegram_id, pinned_repos=pinned)
    await query.answer("📌 Pinned!", show_alert=False)


@router.callback_query(F.data.startswith("repo_unpin:"))
async def cb_repo_unpin(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from database.pool import update_session
    s = session
    if s:
        pinned = [r for r in (s.get("pinned_repos") or []) if r != repo_name]
        await update_session(telegram_id, pinned_repos=pinned)
    await query.answer("📌 Unpinned.", show_alert=False)


@router.callback_query(F.data.startswith("repo_star:"))
async def cb_repo_star(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.services.github import star_repo
    ok = await star_repo(session, telegram_id, repo_name)
    await query.answer("⭐ Starred!" if ok else "❌ Failed", show_alert=True)


@router.callback_query(F.data.startswith("repo_fork:"))
async def cb_repo_fork(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.forks import show_fork_options
    await show_fork_options(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("repo_rename:"))
async def cb_repo_rename(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import start_rename_repo
    await start_rename_repo(query, state, repo_name)


@router.callback_query(F.data.startswith("repo_delete:"))
async def cb_repo_delete(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import start_delete_repo
    await start_delete_repo(query, state, repo_name)


@router.callback_query(F.data == "repo_delete_confirmed")
async def cb_repo_delete_confirmed(query: CallbackQuery,
                                    state: FSMContext,
                                    session: Optional[dict],
                                    telegram_id: int):
    await _answer(query)
    from bot.handlers.repos import confirm_delete_repo
    await confirm_delete_repo(query, state, session, telegram_id)


@router.callback_query(F.data.startswith("repo_visibility:"))
async def cb_repo_visibility(query: CallbackQuery, session: Optional[dict],
                              telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import toggle_visibility
    await toggle_visibility(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("repo_visibility_confirm:"))
async def cb_repo_visibility_confirm(query: CallbackQuery,
                                      session: Optional[dict],
                                      telegram_id: int):
    await _answer(query)
    _, repo_name, vis = query.data.split(":")
    from bot.handlers.repos import confirm_visibility
    await confirm_visibility(query, session, telegram_id,
                              repo_name, vis == "private")


@router.callback_query(F.data.startswith("repo_topics:"))
async def cb_repo_topics(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import start_edit_topics
    await start_edit_topics(query, state, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("repo_description:"))
async def cb_repo_description(query: CallbackQuery, state: FSMContext,
                               session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import start_edit_description
    await start_edit_description(query, state, repo_name)


@router.callback_query(F.data.startswith("repo_website:"))
async def cb_repo_website(query: CallbackQuery, state: FSMContext,
                           session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import start_edit_website
    await start_edit_website(query, state, repo_name)


@router.callback_query(F.data.startswith("repo_template:"))
async def cb_repo_template(query: CallbackQuery, session: Optional[dict],
                            telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.services.github import make_template_repo
    ok = await make_template_repo(session, telegram_id, repo_name)
    await query.answer(
        "✅ Now a template repository!" if ok else "❌ Failed",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("repo_archive:"))
async def cb_repo_archive(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import confirm_archive_repo
    await confirm_archive_repo(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("repo_transfer:"))
async def cb_repo_transfer(query: CallbackQuery, state: FSMContext,
                            session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import start_transfer_repo
    await start_transfer_repo(query, state, repo_name)


# ── Repo create flow ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("repo_create_vis:"))
async def cb_repo_create_vis(query: CallbackQuery, state: FSMContext,
                              telegram_id: int):
    await _answer(query)
    vis = query.data.split(":", 1)[1]
    from bot.handlers.repos import repo_create_set_visibility
    await repo_create_set_visibility(query, state, vis == "private")


@router.callback_query(F.data.startswith("repo_create_readme:"))
async def cb_repo_create_readme(query: CallbackQuery, state: FSMContext,
                                 telegram_id: int):
    await _answer(query)
    want = query.data.split(":", 1)[1] == "yes"
    from bot.handlers.repos import repo_create_set_readme
    await repo_create_set_readme(query, state, want)


@router.callback_query(F.data.startswith("repo_create_gi:"))
async def cb_repo_create_gi(query: CallbackQuery, state: FSMContext,
                             telegram_id: int):
    await _answer(query)
    gi = query.data.split(":", 1)[1]
    from bot.handlers.repos import repo_create_set_gitignore
    await repo_create_set_gitignore(query, state, gi)


@router.callback_query(F.data.startswith("repo_create_license:"))
async def cb_repo_create_license(query: CallbackQuery, state: FSMContext,
                                  session: Optional[dict], telegram_id: int):
    await _answer(query)
    lic = query.data.split(":", 1)[1]
    from bot.handlers.repos import repo_create_finish
    await repo_create_finish(query, state, session, telegram_id, lic)


# ── Files ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("browse:"))
async def cb_browse(query: CallbackQuery, session: Optional[dict],
                     telegram_id: int):
    await _answer(query)
    parts = query.data.split(":", 2)
    repo_name = parts[1]
    path = parts[2] if len(parts) > 2 else ""
    from bot.handlers.files import show_browse
    await show_browse(query, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_read:"))
async def cb_file_read(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import show_file
    await show_file(query, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_edit:"))
async def cb_file_edit(query: CallbackQuery, state: FSMContext,
                        session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import start_file_edit
    await start_file_edit(query, state, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_delete:"))
async def cb_file_delete(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import confirm_delete_file
    await confirm_delete_file(query, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_delete_confirm:"))
async def cb_file_delete_confirm(query: CallbackQuery, session: Optional[dict],
                                  telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import do_delete_file
    await do_delete_file(query, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_move:"))
async def cb_file_move(query: CallbackQuery, state: FSMContext,
                        session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import start_move_file
    await start_move_file(query, state, repo_name, path)


@router.callback_query(F.data.startswith("file_rename:"))
async def cb_file_rename(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import start_rename_file
    await start_rename_file(query, state, repo_name, path)


@router.callback_query(F.data.startswith("file_create:"))
async def cb_file_create(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    parts = query.data.split(":", 2)
    repo_name = parts[1]
    base_path = parts[2] if len(parts) > 2 else ""
    from bot.handlers.files import start_create_file
    await start_create_file(query, state, repo_name, base_path)


@router.callback_query(F.data.startswith("file_download:"))
async def cb_file_download(query: CallbackQuery, session: Optional[dict],
                            telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import download_single_file
    await download_single_file(query, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_history:"))
async def cb_file_history(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import show_file_history
    await show_file_history(query, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_blame:"))
async def cb_file_blame(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    _, repo_name, path = query.data.split(":", 2)
    from bot.handlers.files import show_file_blame
    await show_file_blame(query, session, telegram_id, repo_name, path)


@router.callback_query(F.data.startswith("file_url:"))
async def cb_file_url(query: CallbackQuery, session: Optional[dict],
                       telegram_id: int):
    await _answer(query)
    parts = query.data.split(":", 3)
    repo_name, path = parts[1], parts[2]
    branch = parts[3] if len(parts) > 3 else "main"
    url = f"https://github.com/{repo_name}/blob/{branch}/{path}"
    text = panel("🔗  File URL", [
        "---",
        f"  {h(path)}",
        "---",
        f"  {h(url)}",
        "---",
        "  Copy the link above.",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🌐 Open on GitHub", url=url),
            InlineKeyboardButton(text="⬅️ Back",
                                  callback_data=f"browse:{repo_name}:{'/'.join(path.split('/')[:-1])}"),
        ]]),
    )


@router.callback_query(F.data.startswith("file_search:"))
async def cb_file_search(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.files import start_search
    await start_search(query, state, repo_name)


# ── Upload / Commit ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "upload_menu")
async def cb_upload_menu(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import show_upload_menu
    await show_upload_menu(query, session, telegram_id)


@router.callback_query(F.data == "commit_single")
async def cb_commit_single(query: CallbackQuery, state: FSMContext,
                            session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import start_single_commit
    await start_single_commit(query, state, session, telegram_id)


@router.callback_query(F.data == "commit_batch")
async def cb_commit_batch(query: CallbackQuery, state: FSMContext,
                           session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import start_batch_commit
    await start_batch_commit(query, state, session, telegram_id)


@router.callback_query(F.data == "commit_zip_mirror")
async def cb_commit_zip_mirror(query: CallbackQuery, state: FSMContext,
                                session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import start_zip_commit
    await start_zip_commit(query, state, session, telegram_id, is_mirror=True)


@router.callback_query(F.data == "commit_zip_sync")
async def cb_commit_zip_sync(query: CallbackQuery, state: FSMContext,
                              session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import start_zip_commit
    await start_zip_commit(query, state, session, telegram_id, is_mirror=False)


@router.callback_query(F.data == "commit_write_msg")
async def cb_commit_write_msg(query: CallbackQuery, state: FSMContext,
                               telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import prompt_write_message
    await prompt_write_message(query, state)


@router.callback_query(F.data == "commit_auto_msg")
async def cb_commit_auto_msg(query: CallbackQuery, state: FSMContext,
                              telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import use_auto_message
    await use_auto_message(query, state)


@router.callback_query(F.data == "commit_recent_msg")
async def cb_commit_recent_msg(query: CallbackQuery, state: FSMContext,
                                session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import show_recent_messages
    await show_recent_messages(query, state, session, telegram_id)


@router.callback_query(F.data == "commit_template_msg")
async def cb_commit_template_msg(query: CallbackQuery, state: FSMContext,
                                  session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import show_template_messages
    await show_template_messages(query, state, session, telegram_id)


@router.callback_query(F.data == "commit_preview_tree")
async def cb_commit_preview_tree(query: CallbackQuery, state: FSMContext,
                                  session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import preview_tree
    await preview_tree(query, state, session, telegram_id)


@router.callback_query(F.data == "commit_confirm")
async def cb_commit_confirm(query: CallbackQuery, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import do_commit
    await do_commit(query, state, session, telegram_id)


@router.callback_query(F.data.startswith("commit_use_msg:"))
async def cb_commit_use_msg(query: CallbackQuery, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    await _answer(query)
    msg = query.data.split(":", 1)[1]
    from bot.handlers.upload import commit_with_message
    await commit_with_message(query, state, session, telegram_id, msg)


@router.callback_query(F.data.startswith("commit_use_template:"))
async def cb_commit_use_template(query: CallbackQuery, state: FSMContext,
                                  session: Optional[dict], telegram_id: int):
    await _answer(query)
    tmpl_id = query.data.split(":", 1)[1]
    from bot.handlers.upload import use_template_message
    await use_template_message(query, state, session, telegram_id, tmpl_id)


@router.callback_query(F.data == "commit_sensitive_confirm")
async def cb_sensitive_confirm(query: CallbackQuery, state: FSMContext,
                                session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import sensitive_confirmed
    await sensitive_confirmed(query, state, session, telegram_id)


@router.callback_query(F.data == "commit_sensitive_skip")
async def cb_sensitive_skip(query: CallbackQuery, state: FSMContext,
                             telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import sensitive_skipped
    await sensitive_skipped(query, state)


@router.callback_query(F.data == "mismatch_use_path")
async def cb_mismatch_use_path(query: CallbackQuery, state: FSMContext,
                                session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import mismatch_use_path
    await mismatch_use_path(query, state, session, telegram_id)


@router.callback_query(F.data == "mismatch_use_file")
async def cb_mismatch_use_file(query: CallbackQuery, state: FSMContext,
                                session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import mismatch_use_file
    await mismatch_use_file(query, state, session, telegram_id)


@router.callback_query(F.data.startswith("batch_add_path:"))
async def cb_batch_add_path(query: CallbackQuery, state: FSMContext,
                             telegram_id: int):
    await _answer(query)
    path = query.data.split(":", 1)[1]
    from bot.handlers.upload import batch_add_path
    await batch_add_path(query, state, path)


@router.callback_query(F.data == "batch_paths_done")
async def cb_batch_paths_done(query: CallbackQuery, state: FSMContext,
                               telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import batch_paths_done
    await batch_paths_done(query, state)


@router.callback_query(F.data == "batch_review")
async def cb_batch_review(query: CallbackQuery, state: FSMContext,
                           session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.upload import batch_review
    await batch_review(query, state, session, telegram_id)


# ── Download ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("dl_repo:"))
async def cb_dl_repo(query: CallbackQuery, session: Optional[dict],
                      telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.explore import download_repo
    await download_repo(query, session, telegram_id, repo_name)


# ── Branches ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("branches:"))
async def cb_branches(query: CallbackQuery, session: Optional[dict],
                       telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.branches import show_branches
    await show_branches(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("branch_checkout:"))
async def cb_branch_checkout(query: CallbackQuery, session: Optional[dict],
                              telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.branches import checkout_branch
    await checkout_branch(query, session, telegram_id, repo_name, branch)


@router.callback_query(F.data.startswith("branch_create:"))
async def cb_branch_create(query: CallbackQuery, state: FSMContext,
                            session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.branches import start_create_branch
    await start_create_branch(query, state, repo_name)


@router.callback_query(F.data.startswith("branch_delete:"))
async def cb_branch_delete(query: CallbackQuery, session: Optional[dict],
                            telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.branches import confirm_delete_branch
    await confirm_delete_branch(query, session, telegram_id, repo_name, branch)


@router.callback_query(F.data.startswith("branch_delete_confirm:"))
async def cb_branch_delete_confirm(query: CallbackQuery, session: Optional[dict],
                                    telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.branches import do_delete_branch
    await do_delete_branch(query, session, telegram_id, repo_name, branch)


@router.callback_query(F.data.startswith("branch_merge:"))
async def cb_branch_merge(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.branches import confirm_merge_branch
    await confirm_merge_branch(query, session, telegram_id, repo_name, branch)


@router.callback_query(F.data.startswith("branch_merge_confirm:"))
async def cb_branch_merge_confirm(query: CallbackQuery, session: Optional[dict],
                                   telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.branches import do_merge_branch
    await do_merge_branch(query, session, telegram_id, repo_name, branch)


@router.callback_query(F.data.startswith("branch_rename:"))
async def cb_branch_rename(query: CallbackQuery, state: FSMContext,
                            session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.branches import start_rename_branch
    await start_rename_branch(query, state, repo_name, branch)


@router.callback_query(F.data.startswith("branch_protect:"))
async def cb_branch_protect(query: CallbackQuery, session: Optional[dict],
                             telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.branches import do_protect_branch
    await do_protect_branch(query, session, telegram_id, repo_name, branch)


@router.callback_query(F.data.startswith("branch_compare:"))
async def cb_branch_compare(query: CallbackQuery, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.branches import start_compare_branches
    await start_compare_branches(query, state, repo_name)


@router.callback_query(F.data.startswith("branch_set_default:"))
async def cb_branch_set_default(query: CallbackQuery, session: Optional[dict],
                                 telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.services.github import set_default_branch
    ok = await set_default_branch(session, telegram_id, repo_name, branch)
    await query.answer(
        f"✅ Default branch set to {branch}" if ok else "❌ Failed",
        show_alert=True,
    )


# ── Commits ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("commits:"))
async def cb_commits(query: CallbackQuery, session: Optional[dict],
                      telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.history import show_commits
    branch = session.get("active_branch", "main") if session else "main"
    await show_commits(query, session, telegram_id, repo_name, branch, page=0)


@router.callback_query(F.data.startswith("commits_page:"))
async def cb_commits_page(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, branch, page = query.data.split(":")
    from bot.handlers.history import show_commits
    await show_commits(query, session, telegram_id,
                        repo_name, branch, int(page))


@router.callback_query(F.data.startswith("commit_view:"))
async def cb_commit_view(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    _, repo_name, sha = query.data.split(":", 2)
    from bot.handlers.history import show_commit_detail
    await show_commit_detail(query, session, telegram_id, repo_name, sha)


@router.callback_query(F.data.startswith("commit_revert_last:"))
async def cb_commit_revert_last(query: CallbackQuery, state: FSMContext,
                                 session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, branch = query.data.split(":")
    from bot.handlers.history import confirm_revert_last
    await confirm_revert_last(query, session, telegram_id, repo_name, branch)


@router.callback_query(F.data.startswith("commit_revert:"))
async def cb_commit_revert(query: CallbackQuery, session: Optional[dict],
                            telegram_id: int):
    await _answer(query)
    _, repo_name, branch, sha = query.data.split(":")
    from bot.handlers.history import do_revert_commit
    await do_revert_commit(query, session, telegram_id, repo_name, branch, sha)


@router.callback_query(F.data.startswith("commit_reset:"))
async def cb_commit_reset(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, branch, sha = query.data.split(":")
    from bot.handlers.history import confirm_reset_to_commit
    await confirm_reset_to_commit(query, session, telegram_id,
                                   repo_name, branch, sha)


@router.callback_query(F.data.startswith("commit_reset_confirm:"))
async def cb_commit_reset_confirm(query: CallbackQuery, session: Optional[dict],
                                   telegram_id: int):
    await _answer(query)
    _, repo_name, branch, sha = query.data.split(":")
    from bot.handlers.history import do_reset_to_commit
    await do_reset_to_commit(query, session, telegram_id, repo_name, branch, sha)


# ── Pull Requests ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pulls:"))
async def cb_pulls(query: CallbackQuery, session: Optional[dict],
                    telegram_id: int):
    await _answer(query)
    parts = query.data.split(":")
    repo_name = parts[1]
    state_filter = parts[2] if len(parts) > 2 else "open"
    page = int(parts[3]) if len(parts) > 3 else 0
    from bot.handlers.pulls import show_pulls
    await show_pulls(query, session, telegram_id, repo_name, state_filter, page)


@router.callback_query(F.data.startswith("pull_view:"))
async def cb_pull_view(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    _, repo_name, pr_num = query.data.split(":")
    from bot.handlers.pulls import show_pull_detail
    await show_pull_detail(query, session, telegram_id, repo_name, int(pr_num))


@router.callback_query(F.data.startswith("pull_create:"))
async def cb_pull_create(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.pulls import start_create_pull
    await start_create_pull(query, state, session, repo_name)


@router.callback_query(F.data.startswith("pull_merge:"))
async def cb_pull_merge(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    _, repo_name, pr_num, method = query.data.split(":")
    from bot.handlers.pulls import do_merge_pull
    await do_merge_pull(query, session, telegram_id,
                         repo_name, int(pr_num), method)


@router.callback_query(F.data.startswith("pull_close:"))
async def cb_pull_close(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    _, repo_name, pr_num = query.data.split(":")
    from bot.handlers.pulls import do_close_pull
    await do_close_pull(query, session, telegram_id, repo_name, int(pr_num))


@router.callback_query(F.data.startswith("pull_approve:"))
async def cb_pull_approve(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, pr_num = query.data.split(":")
    from bot.handlers.pulls import do_approve_pull
    await do_approve_pull(query, session, telegram_id, repo_name, int(pr_num))


@router.callback_query(F.data.startswith("pull_diff:"))
async def cb_pull_diff(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    _, repo_name, pr_num = query.data.split(":")
    from bot.handlers.pulls import show_pull_diff
    await show_pull_diff(query, session, telegram_id, repo_name, int(pr_num))


@router.callback_query(F.data.startswith("pull_commits:"))
async def cb_pull_commits(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, pr_num = query.data.split(":")
    from bot.handlers.pulls import show_pull_commits
    await show_pull_commits(query, session, telegram_id, repo_name, int(pr_num))


# ── Issues ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("issues:"))
async def cb_issues(query: CallbackQuery, session: Optional[dict],
                     telegram_id: int):
    await _answer(query)
    parts = query.data.split(":")
    repo_name = parts[1]
    state_filter = parts[2] if len(parts) > 2 else "open"
    page = int(parts[3]) if len(parts) > 3 else 0
    from bot.handlers.issues import show_issues
    await show_issues(query, session, telegram_id, repo_name, state_filter, page)


@router.callback_query(F.data.startswith("issue_view:"))
async def cb_issue_view(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    _, repo_name, issue_num = query.data.split(":")
    from bot.handlers.issues import show_issue_detail
    await show_issue_detail(query, session, telegram_id,
                             repo_name, int(issue_num))


@router.callback_query(F.data.startswith("issue_create:"))
async def cb_issue_create(query: CallbackQuery, state: FSMContext,
                           session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.issues import start_create_issue
    await start_create_issue(query, state, repo_name)


@router.callback_query(F.data.startswith("issue_close:"))
async def cb_issue_close(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    _, repo_name, issue_num = query.data.split(":")
    from bot.handlers.issues import do_close_issue
    await do_close_issue(query, session, telegram_id, repo_name, int(issue_num))


@router.callback_query(F.data.startswith("issue_reopen:"))
async def cb_issue_reopen(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, issue_num = query.data.split(":")
    from bot.handlers.issues import do_reopen_issue
    await do_reopen_issue(query, session, telegram_id,
                           repo_name, int(issue_num))


@router.callback_query(F.data.startswith("issue_comment:"))
async def cb_issue_comment(query: CallbackQuery, state: FSMContext,
                            session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, issue_num = query.data.split(":")
    from bot.handlers.issues import start_comment_issue
    await start_comment_issue(query, state, repo_name, int(issue_num))


@router.callback_query(F.data.startswith("issue_label:"))
async def cb_issue_label(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    _, repo_name, issue_num = query.data.split(":")
    from bot.handlers.issues import show_label_picker
    await show_label_picker(query, session, telegram_id,
                             repo_name, int(issue_num))


# ── Releases ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("releases:"))
async def cb_releases(query: CallbackQuery, session: Optional[dict],
                       telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.releases import show_releases
    await show_releases(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("release_view:"))
async def cb_release_view(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    _, repo_name, release_id = query.data.split(":")
    from bot.handlers.releases import show_release_detail
    await show_release_detail(query, session, telegram_id,
                               repo_name, int(release_id))


@router.callback_query(F.data.startswith("release_create:"))
async def cb_release_create(query: CallbackQuery, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.releases import start_create_release
    await start_create_release(query, state, repo_name)


@router.callback_query(F.data.startswith("release_delete:"))
async def cb_release_delete(query: CallbackQuery, session: Optional[dict],
                             telegram_id: int):
    await _answer(query)
    _, repo_name, release_id = query.data.split(":")
    from bot.handlers.releases import do_delete_release
    await do_delete_release(query, session, telegram_id,
                             repo_name, int(release_id))


# ── Actions ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("actions:"))
async def cb_actions(query: CallbackQuery, session: Optional[dict],
                      telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.actions import show_workflows
    await show_workflows(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("action_workflow_view:"))
async def cb_action_workflow_view(query: CallbackQuery, session: Optional[dict],
                                   telegram_id: int):
    await _answer(query)
    _, repo_name, workflow_id = query.data.split(":")
    from bot.handlers.actions import show_workflow_detail
    await show_workflow_detail(query, session, telegram_id,
                                repo_name, int(workflow_id))


@router.callback_query(F.data.startswith("action_run:"))
async def cb_action_run(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    _, repo_name, workflow_id = query.data.split(":")
    from bot.handlers.actions import trigger_workflow
    await trigger_workflow(query, session, telegram_id,
                            repo_name, int(workflow_id))


@router.callback_query(F.data.startswith("action_cancel_run:"))
async def cb_action_cancel_run(query: CallbackQuery, session: Optional[dict],
                                telegram_id: int):
    await _answer(query)
    _, repo_name, run_id = query.data.split(":")
    from bot.handlers.actions import cancel_run
    await cancel_run(query, session, telegram_id, repo_name, int(run_id))


@router.callback_query(F.data.startswith("action_logs:"))
async def cb_action_logs(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    _, repo_name, run_id = query.data.split(":")
    await query.message.answer(
        f"🔗 View logs on GitHub:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="📜 Open Logs",
                url=f"https://github.com/{repo_name}/actions/runs/{run_id}",
            )
        ]]),
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("stats:"))
async def cb_stats(query: CallbackQuery, session: Optional[dict],
                    telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.stats import show_repo_stats
    await show_repo_stats(query, session, telegram_id, repo_name)


@router.callback_query(F.data == "stats")
async def cb_stats_active(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    if not session or not session.get("active_repo"):
        await query.answer("No active repository.", show_alert=True)
        return
    from bot.handlers.stats import show_repo_stats
    await show_repo_stats(query, session, telegram_id, session["active_repo"])


# ── Forks ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "forks")
async def cb_forks(query: CallbackQuery, session: Optional[dict],
                    telegram_id: int):
    await _answer(query)
    from bot.handlers.forks import show_forks
    await show_forks(query, session, telegram_id)


@router.callback_query(F.data.startswith("fork_view:"))
async def cb_fork_view(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.forks import show_fork_detail
    await show_fork_detail(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("fork_sync:"))
async def cb_fork_sync(query: CallbackQuery, session: Optional[dict],
                        telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.forks import do_sync_fork
    await do_sync_fork(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("fork_contribute:"))
async def cb_fork_contribute(query: CallbackQuery, state: FSMContext,
                              session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, fork_name, parent_name = query.data.split(":", 2)
    from bot.handlers.forks import start_contribute_pr
    await start_contribute_pr(query, state, session, telegram_id,
                               fork_name, parent_name)


@router.callback_query(F.data.startswith("fork_delete:"))
async def cb_fork_delete(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.repos import start_delete_repo
    await start_delete_repo(query, None, repo_name)


@router.callback_query(F.data.startswith("fork_to_personal:"))
async def cb_fork_to_personal(query: CallbackQuery, session: Optional[dict],
                               telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.forks import do_fork_repo
    await do_fork_repo(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("fork_to_org:"))
async def cb_fork_to_org(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    _, repo_name, org = query.data.split(":", 2)
    from bot.handlers.forks import do_fork_repo
    await do_fork_repo(query, session, telegram_id, repo_name, org=org)


# ── Notifications ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "notifs_all")
async def cb_notifs_all(query: CallbackQuery, session: Optional[dict],
                         telegram_id: int):
    await _answer(query)
    from bot.handlers.notifications import show_notifications
    await show_notifications(query, session, telegram_id, unread_only=False)


@router.callback_query(F.data.startswith("notifs_page:"))
async def cb_notifs_page(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    page = int(query.data.split(":", 1)[1])
    from bot.handlers.notifications import show_notifications
    await show_notifications(query, session, telegram_id,
                              unread_only=False, page=page)


@router.callback_query(F.data == "notifs_mark_all_read")
async def cb_notifs_mark_all(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from database.pool import mark_notifications_read
    await mark_notifications_read(telegram_id)
    await query.answer("✅ All marked as read.", show_alert=False)
    from bot.handlers.notifications import show_notifications
    from database.pool import get_active_session
    session = await get_active_session(telegram_id)
    await show_notifications(query, session, telegram_id, unread_only=False)


@router.callback_query(F.data.startswith("notif_read:"))
async def cb_notif_read(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    notif_id = int(query.data.split(":", 1)[1])
    from database.pool import mark_notifications_read
    await mark_notifications_read(telegram_id, notif_id)
    await query.answer("✅ Marked as read.", show_alert=False)


@router.callback_query(F.data == "notifs_settings")
async def cb_notifs_settings(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.notifications import show_notif_settings
    await show_notif_settings(query, telegram_id)


@router.callback_query(F.data.startswith("notif_toggle:"))
async def cb_notif_toggle(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    key = query.data.split(":", 1)[1]
    from database.pool import get_settings, update_settings
    s = await get_settings(telegram_id)
    current = s.get(key, False)
    await update_settings(telegram_id, **{key: not current})
    await query.answer(
        f"{'✅ Enabled' if not current else '🔕 Disabled'}",
        show_alert=False,
    )
    from bot.handlers.notifications import show_notif_settings
    await show_notif_settings(query, telegram_id)


@router.callback_query(F.data == "notifs_quiet_hours")
async def cb_notifs_quiet(query: CallbackQuery, state: FSMContext,
                           telegram_id: int):
    await _answer(query)
    from bot.handlers.notifications import setup_quiet_hours
    await setup_quiet_hours(query, state, telegram_id)


@router.callback_query(F.data == "notifs_mute_repo")
async def cb_notifs_mute_repo(query: CallbackQuery, state: FSMContext,
                               session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.notifications import start_mute_repo
    await start_mute_repo(query, state, session)


# ── Settings ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "settings_back")
async def cb_settings_back(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_settings_panel
    await show_settings_panel(query, telegram_id)


@router.callback_query(F.data == "settings_theme")
async def cb_settings_theme(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_theme_picker
    await show_theme_picker(query, telegram_id)


@router.callback_query(F.data.startswith("settings_set_theme:"))
async def cb_set_theme(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    theme = query.data.split(":", 1)[1]
    from database.pool import update_settings
    await update_settings(telegram_id, theme=theme)
    await query.answer(f"✅ Theme: {theme.title()}", show_alert=False)
    from bot.handlers.settings import show_theme_picker
    await show_theme_picker(query, telegram_id)


@router.callback_query(F.data == "settings_time")
async def cb_settings_time(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_time_picker
    await show_time_picker(query, telegram_id)


@router.callback_query(F.data.startswith("settings_set_time:"))
async def cb_set_time(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    fmt = query.data.split(":", 1)[1]
    from database.pool import update_settings
    await update_settings(telegram_id, time_format=fmt)
    await query.answer(f"✅ Time format: {fmt}", show_alert=False)
    from bot.handlers.settings import show_time_picker
    await show_time_picker(query, telegram_id)


@router.callback_query(F.data == "settings_date")
async def cb_settings_date(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_date_picker
    await show_date_picker(query, telegram_id)


@router.callback_query(F.data.startswith("settings_set_date:"))
async def cb_set_date(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    fmt = query.data.split(":", 1)[1]
    from database.pool import update_settings
    await update_settings(telegram_id, date_format=fmt)
    await query.answer(f"✅ Date format: {fmt}", show_alert=False)
    from bot.handlers.settings import show_date_picker
    await show_date_picker(query, telegram_id)


@router.callback_query(F.data == "settings_timezone")
async def cb_settings_timezone(query: CallbackQuery, state: FSMContext,
                                 telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import prompt_timezone
    await prompt_timezone(query, state)


@router.callback_query(F.data == "settings_pm")
async def cb_settings_pm(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_private_msg
    await show_private_msg(query, telegram_id)


@router.callback_query(F.data == "settings_aliases")
async def cb_settings_aliases(query: CallbackQuery, session: Optional[dict],
                                telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_aliases
    await show_aliases(query, session, telegram_id)


@router.callback_query(F.data == "settings_templates")
async def cb_settings_templates(query: CallbackQuery, session: Optional[dict],
                                  telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_templates
    await show_templates(query, session, telegram_id)


@router.callback_query(F.data == "settings_savedpaths")
async def cb_settings_savedpaths(query: CallbackQuery, session: Optional[dict],
                                   telegram_id: int):
    await _answer(query)
    from bot.handlers.settings import show_saved_paths
    await show_saved_paths(query, session, telegram_id)


@router.callback_query(F.data == "settings_reset")
async def cb_settings_reset(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    text = panel("↩️  Reset All Settings", [
        "---",
        "This resets all settings to defaults.",
        "Your GitHub data is NOT affected.",
    ])
    await query.message.edit_text(
        f"<pre>{text}</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yes, reset all",
                                  callback_data="settings_reset_confirm"),
            InlineKeyboardButton(text="❌ Cancel",
                                  callback_data="settings_back"),
        ]]),
    )


@router.callback_query(F.data == "settings_reset_confirm")
async def cb_settings_reset_confirm(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from database.pool import update_settings
    await update_settings(telegram_id,
                           theme="dark", time_format="24hr",
                           date_format="DD/MM/YYYY", timezone="UTC")
    await query.answer("✅ Settings reset.", show_alert=False)
    from bot.handlers.settings import show_settings_panel
    await show_settings_panel(query, telegram_id)


@router.callback_query(F.data.startswith("alias_remove:"))
async def cb_alias_remove(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    alias = query.data.split(":", 1)[1]
    from database.pool import remove_alias
    await remove_alias(telegram_id, alias)
    from bot.handlers.settings import show_aliases
    await show_aliases(query, session, telegram_id)


@router.callback_query(F.data.startswith("template_remove:"))
async def cb_template_remove(query: CallbackQuery, session: Optional[dict],
                               telegram_id: int):
    await _answer(query)
    tmpl_id = int(query.data.split(":", 1)[1])
    from database.pool import remove_template
    await remove_template(tmpl_id, telegram_id)
    from bot.handlers.settings import show_templates
    await show_templates(query, session, telegram_id)


@router.callback_query(F.data.startswith("savedpath_remove:"))
async def cb_savedpath_remove(query: CallbackQuery, session: Optional[dict],
                               telegram_id: int):
    await _answer(query)
    path = query.data.split(":", 1)[1]
    if session:
        from database.pool import remove_saved_path
        await remove_saved_path(telegram_id, session["github_username"],
                                 session["active_repo"], path)
    from bot.handlers.settings import show_saved_paths
    await show_saved_paths(query, session, telegram_id)


@router.callback_query(F.data.startswith("savedpath_use:"))
async def cb_savedpath_use(query: CallbackQuery, state: FSMContext,
                            session: Optional[dict], telegram_id: int):
    await _answer(query)
    path = query.data.split(":", 1)[1]
    from bot.handlers.upload import start_single_commit_at_path
    await start_single_commit_at_path(query, state, session, telegram_id, path)


# ── Profile ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "account_profile")
async def cb_account_profile(query: CallbackQuery, session: Optional[dict],
                               telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_profile
    await show_profile(query, session, telegram_id)


@router.callback_query(F.data == "profile_edit")
async def cb_profile_edit(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_edit_profile
    await show_edit_profile(query, telegram_id)


@router.callback_query(F.data.startswith("profile_edit_"))
async def cb_profile_edit_field(query: CallbackQuery, state: FSMContext,
                                 session: Optional[dict], telegram_id: int):
    await _answer(query)
    field = query.data[len("profile_edit_"):]
    from bot.handlers.account import start_edit_profile_field
    await start_edit_profile_field(query, state, session, telegram_id, field)


@router.callback_query(F.data == "profile_hireable")
async def cb_profile_hireable(query: CallbackQuery, session: Optional[dict],
                               telegram_id: int):
    await _answer(query)
    from bot.handlers.account import toggle_hireable
    await toggle_hireable(query, session, telegram_id)


@router.callback_query(F.data == "profile_pinned")
async def cb_profile_pinned(query: CallbackQuery, session: Optional[dict],
                             telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_pinned_manager
    await show_pinned_manager(query, session, telegram_id)


@router.callback_query(F.data.startswith("profile_pin_remove:"))
async def cb_profile_pin_remove(query: CallbackQuery, session: Optional[dict],
                                 telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from database.pool import update_session
    s = session
    if s:
        pinned = [r for r in (s.get("pinned_repos") or []) if r != repo_name]
        await update_session(telegram_id, pinned_repos=pinned)
    from bot.handlers.account import show_pinned_manager
    await show_pinned_manager(query, session, telegram_id)


@router.callback_query(F.data == "profile_following")
async def cb_profile_following(query: CallbackQuery, session: Optional[dict],
                                telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_following
    await show_following(query, session, telegram_id)


@router.callback_query(F.data == "profile_followers")
async def cb_profile_followers(query: CallbackQuery, session: Optional[dict],
                                telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_followers
    await show_followers(query, session, telegram_id)


@router.callback_query(F.data == "profile_orgs")
async def cb_profile_orgs(query: CallbackQuery, session: Optional[dict],
                           telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_orgs
    await show_orgs(query, session, telegram_id)


# ── Explore ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "explore_search")
async def cb_explore_search(query: CallbackQuery, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.explore import start_search
    await start_search(query, state)


@router.callback_query(F.data == "explore_download_url")
async def cb_explore_dl_url(query: CallbackQuery, state: FSMContext,
                             session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.explore import start_download_url
    await start_download_url(query, state)


@router.callback_query(F.data == "explore_find_user")
async def cb_explore_find_user(query: CallbackQuery, state: FSMContext,
                                session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.explore import start_find_user
    await start_find_user(query, state)


@router.callback_query(F.data == "explore_search_code")
async def cb_explore_search_code(query: CallbackQuery, state: FSMContext,
                                  session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.explore import start_search_code
    await start_search_code(query, state, session)


# ── Projects ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "projects")
async def cb_projects(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.projects import show_projects
    await show_projects(query, telegram_id)


@router.callback_query(F.data == "project_create")
async def cb_project_create(query: CallbackQuery, state: FSMContext,
                             telegram_id: int):
    await _answer(query)
    from bot.handlers.projects import start_create_project
    await start_create_project(query, state)


@router.callback_query(F.data.startswith("project_open:"))
async def cb_project_open(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    name = query.data.split(":", 1)[1]
    from bot.handlers.projects import show_project_detail
    await show_project_detail(query, telegram_id, name)


@router.callback_query(F.data.startswith("project_add_file:"))
async def cb_project_add_file(query: CallbackQuery, state: FSMContext,
                               telegram_id: int):
    await _answer(query)
    name = query.data.split(":", 1)[1]
    from bot.handlers.projects import start_add_project_file
    await start_add_project_file(query, state, name)


@router.callback_query(F.data.startswith("project_view_files:"))
async def cb_project_view_files(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    name = query.data.split(":", 1)[1]
    from bot.handlers.projects import show_project_files
    await show_project_files(query, telegram_id, name)


@router.callback_query(F.data.startswith("project_push:"))
async def cb_project_push(query: CallbackQuery, state: FSMContext,
                           session: Optional[dict], telegram_id: int):
    await _answer(query)
    name = query.data.split(":", 1)[1]
    from bot.handlers.projects import start_push_project
    await start_push_project(query, state, session, telegram_id, name)


@router.callback_query(F.data.startswith("project_delete:"))
async def cb_project_delete(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    name = query.data.split(":", 1)[1]
    from bot.handlers.projects import confirm_delete_project
    await confirm_delete_project(query, telegram_id, name)


@router.callback_query(F.data.startswith("project_delete_confirm:"))
async def cb_project_delete_confirm(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    name = query.data.split(":", 1)[1]
    from bot.handlers.projects import do_delete_project
    await do_delete_project(query, telegram_id, name)


# ── Health ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "health")
async def cb_health(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from bot.handlers.system import show_health
    await show_health(query, telegram_id)


@router.callback_query(F.data == "health_logs")
async def cb_health_logs(query: CallbackQuery, telegram_id: int, is_admin: bool):
    await _answer(query)
    if not is_admin:
        await query.answer("❌ Admin only.", show_alert=True)
        return
    await query.message.answer("📜 Logs are available via Railway dashboard.")


@router.callback_query(F.data == "health_clear_queue")
async def cb_health_clear_queue(query: CallbackQuery, telegram_id: int,
                                 is_admin: bool):
    await _answer(query)
    if not is_admin:
        await query.answer("❌ Admin only.", show_alert=True)
        return
    from bot.services.cache import r
    await r().delete("webhook_queue")
    await query.answer("✅ Queue cleared.", show_alert=True)


# ── Security ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "security")
async def cb_security(query: CallbackQuery, session: Optional[dict],
                       telegram_id: int):
    await _answer(query)
    if not session or not session.get("active_repo"):
        await query.answer("Select a repository first.", show_alert=True)
        return
    from bot.handlers.security import show_security
    await show_security(query, session, telegram_id, session["active_repo"])


@router.callback_query(F.data.startswith("security_alerts:"))
async def cb_security_alerts(query: CallbackQuery, session: Optional[dict],
                               telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.security import show_dependabot_alerts
    await show_dependabot_alerts(query, session, telegram_id, repo_name)


@router.callback_query(F.data.startswith("security_webhooks:"))
async def cb_security_webhooks(query: CallbackQuery, session: Optional[dict],
                                telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.handlers.security import show_webhooks
    await show_webhooks(query, session, telegram_id, repo_name)


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "user_invite")
async def cb_user_invite(query: CallbackQuery, state: FSMContext,
                          telegram_id: int, is_admin: bool):
    await _answer(query)
    if not is_admin:
        await query.answer("❌ Admin only.", show_alert=True)
        return
    from bot.handlers.admin import handle_create_invite as create_invite
    await create_invite(query, telegram_id)


@router.callback_query(F.data.startswith("user_revoke:"))
async def cb_user_revoke(query: CallbackQuery, telegram_id: int,
                          is_admin: bool):
    await _answer(query)
    if not is_admin:
        await query.answer("❌ Admin only.", show_alert=True)
        return
    target_id = int(query.data.split(":", 1)[1])
    from bot.handlers.admin import revoke_user_access
    await revoke_user_access(query, telegram_id, target_id)


@router.callback_query(F.data == "user_stats")
async def cb_user_stats(query: CallbackQuery, telegram_id: int,
                         is_admin: bool):
    await _answer(query)
    if not is_admin:
        await query.answer("❌ Admin only.", show_alert=True)
        return
    from bot.handlers.admin import show_usage_stats
    await show_usage_stats(query, telegram_id)


@router.callback_query(F.data.startswith("invite_cancel:"))
async def cb_invite_cancel(query: CallbackQuery, telegram_id: int,
                            is_admin: bool):
    await _answer(query)
    token = query.data.split(":", 1)[1]
    from database.pool import cancel_invite
    await cancel_invite(token, telegram_id)
    await query.answer("✅ Invite cancelled.", show_alert=False)
    from bot.handlers.admin import show_users
    await show_users(query, telegram_id)


# ── Gists ─────────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "gist_list")
async def cb_gist_list(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.gists import show_gists
    await show_gists(query, session, telegram_id)

@router.callback_query(F.data == "gist_create")
async def cb_gist_create(query: CallbackQuery, state: FSMContext,
                          session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.gists import start_create_gist
    await start_create_gist(query, state)


@router.callback_query(F.data.startswith("gist_delete:"))
async def cb_gist_delete(query: CallbackQuery, session: Optional[dict],
                          telegram_id: int):
    await _answer(query)
    gist_id = query.data.split(":", 1)[1]
    from bot.handlers.gists import confirm_delete_gist
    await confirm_delete_gist(query, session, telegram_id, gist_id)


@router.callback_query(F.data.startswith("gist_delete_confirm:"))
async def cb_gist_delete_confirm(query: CallbackQuery, session: Optional[dict],
                                  telegram_id: int):
    await _answer(query)
    gist_id = query.data.split(":", 1)[1]
    from bot.services.github import delete_gist
    ok = await delete_gist(session, telegram_id, gist_id)
    await query.answer("🗑️ Gist deleted." if ok else "❌ Failed",
                        show_alert=True)
    from bot.handlers.gists import show_gists
    await show_gists(query, session, telegram_id)

# ── Additional missing static callbacks ──────────────────────────────────────

@router.callback_query(F.data == "branches")
async def cb_branches_active(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    if not session or not session.get("active_repo"):
        await query.answer("No active repository.", show_alert=True)
        return
    from bot.handlers.branches import show_branches
    await show_branches(query, session, telegram_id, session["active_repo"])


@router.callback_query(F.data == "commits")
async def cb_commits_active(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    if not session or not session.get("active_repo"):
        await query.answer("No active repository.", show_alert=True)
        return
    from bot.handlers.history import show_commits
    branch = session.get("active_branch", "main")
    await show_commits(query, session, telegram_id, session["active_repo"], branch, 0)


@router.callback_query(F.data.startswith("profile_edit_"))
async def cb_profile_edit_field_generic(query: CallbackQuery, state: FSMContext,
                                         session: Optional[dict], telegram_id: int):
    await _answer(query)
    field = query.data[len("profile_edit_"):]
    from bot.handlers.account import start_edit_profile_field
    await start_edit_profile_field(query, state, session, telegram_id, field)


@router.callback_query(F.data == "unfollow")
async def cb_unfollow_noop(query: CallbackQuery):
    await query.answer()


@router.callback_query(F.data.startswith("unfollow:"))
async def cb_unfollow_user(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    username = query.data.split(":", 1)[1]
    from bot.services.github import unfollow_user
    ok = await unfollow_user(session, username)
    await query.answer("✅ Unfollowed." if ok else "❌ Failed", show_alert=True)


@router.callback_query(F.data.startswith("follow_user:"))
async def cb_follow_user(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    username = query.data.split(":", 1)[1]
    from bot.services.github import follow_user
    ok = await follow_user(session, username)
    await query.answer("✅ Following!" if ok else "❌ Failed", show_alert=True)


@router.callback_query(F.data == "show_saved_paths")
async def cb_show_saved_paths(query: CallbackQuery, state: FSMContext,
                               session: Optional[dict], telegram_id: int):
    await _answer(query)
    if not session or not session.get("active_repo"):
        await query.answer("No active repository.", show_alert=True)
        return
    from database.pool import get_saved_paths
    paths = await get_saved_paths(telegram_id, session["github_username"], session["active_repo"])
    if not paths:
        await query.answer("No saved paths yet. Use Settings → Saved Paths.", show_alert=True)
        return
    from utils.formatters import h
    kb = [[InlineKeyboardButton(text=p, callback_data=f"batch_add_path:{p}")] for p in paths]
    kb.append([InlineKeyboardButton(text="✅ Done", callback_data="batch_paths_done"),
               InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")])
    await query.message.edit_text(
        "<pre>⭐  Select a saved path:</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )


@router.callback_query(F.data == "alias_add")
async def cb_alias_add(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import SettingsFlow
    await state.set_state(SettingsFlow.adding_alias_shortcut)
    from utils.formatters import h, panel
    text = panel("⌨️  New Alias", ["---", "  Type the shortcut:", "  e.g.  /up"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="❌ Cancel", callback_data="settings_aliases")]]))


@router.callback_query(F.data == "template_add")
async def cb_template_add(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import SettingsFlow
    await state.set_state(SettingsFlow.adding_template)
    from utils.formatters import h, panel
    text = panel("📝  New Template", ["---", "  Type the commit template:", "  e.g.  feat: {description}"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="❌ Cancel", callback_data="settings_templates")]]))


@router.callback_query(F.data == "savedpath_add")
async def cb_savedpath_add(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import SettingsFlow
    await state.set_state(SettingsFlow.adding_savedpath)
    from utils.formatters import h, panel
    text = panel("⭐  Save a Path", ["---", "  Type the file path:", "  e.g.  src/app.py"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="❌ Cancel", callback_data="settings_savedpaths")]]))


@router.callback_query(F.data == "pm_edit_message")
async def cb_pm_edit_message(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import SettingsFlow
    await state.set_state(SettingsFlow.editing_pm_message)
    from utils.formatters import panel
    text = panel("💬  Edit Private Message", ["---",
        "  Type your custom message:", "---",
        "  Variables you can use:", "  {owner} {botname} {date} {link}"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="❌ Cancel", callback_data="settings_pm")]]))


@router.callback_query(F.data == "pm_edit_owner")
async def cb_pm_edit_owner(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import SettingsFlow
    await state.set_state(SettingsFlow.editing_pm_owner)
    from utils.formatters import panel
    text = panel("👤  Edit Owner", ["---", "  Type the owner username:","  e.g.  @yourhandle"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="❌ Cancel", callback_data="settings_pm")]]))


@router.callback_query(F.data == "pm_edit_link")
async def cb_pm_edit_link(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import SettingsFlow
    await state.set_state(SettingsFlow.editing_pm_link)
    from utils.formatters import panel
    text = panel("🔗  Set Link", ["---", "  Type the URL to include:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="❌ Cancel", callback_data="settings_pm")]]))


@router.callback_query(F.data == "pm_preview")
async def cb_pm_preview(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from database.pool import get_settings
    from datetime import datetime
    from utils.formatters import h
    s = await get_settings(telegram_id)
    custom = s.get("private_message")
    owner = s.get("pm_owner") or "@GitroHubBot"
    link = s.get("pm_link") or ""
    if custom:
        msg = custom.replace("{owner}", owner).replace("{botname}", "GitroHub")\
                    .replace("{date}", datetime.now().strftime("%b %d %Y")).replace("{link}", link)
    else:
        msg = f"🔒 GitroHub — Private Bot\n\nOwner: {owner}\n\nThis bot is privately owned."
    await query.message.edit_text(
        f"<pre>👁  Preview:\n\n{h(msg)}</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⬅️ Back", callback_data="settings_pm")]])
    )


@router.callback_query(F.data == "pm_reset")
async def cb_pm_reset(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    from database.pool import update_settings
    await update_settings(telegram_id, private_message=None, pm_owner=None, pm_link=None)
    await query.answer("✅ Private message reset to default.", show_alert=True)
    from bot.handlers.settings import show_private_msg
    await show_private_msg(query, telegram_id)


@router.callback_query(F.data.startswith("repo_archive_confirm:"))
async def cb_repo_archive_confirm(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.services.github import archive_repo
    ok = await archive_repo(session, telegram_id, repo_name)
    await query.answer("✅ Repository archived." if ok else "❌ Failed", show_alert=True)


@router.callback_query(F.data.startswith("webhook_delete:"))
async def cb_webhook_delete(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, hook_id = query.data.split(":")
    from bot.services.github import delete_repo_webhook
    ok = await delete_repo_webhook(session, repo_name, int(hook_id))
    await query.answer("✅ Webhook deleted." if ok else "❌ Failed", show_alert=True)


@router.callback_query(F.data.startswith("webhook_add:"))
async def cb_webhook_add(query: CallbackQuery, telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from config import settings as cfg
    from utils.formatters import h, panel
    webhook_url = f"{cfg.webhook_url}/github-events" if cfg.webhook_url else "Set WEBHOOK_URL in env"
    text = panel("🔗  Add Webhook", [
        "---", f"  Repository: {h(repo_name)}", "---",
        "  Add this URL to your GitHub repo:", "···",
        f"  {h(webhook_url)}", "---",
        "  Go to: Repo → Settings → Webhooks", "  → Add webhook → paste URL above",
        "  → Content type: application/json",
        "  → Select events you want",
    ])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="🌐 Open GitHub Webhooks",
                                           url=f"https://github.com/{repo_name}/settings/hooks"),
                                       InlineKeyboardButton(text="⬅️ Back",
                                           callback_data=f"security_webhooks:{repo_name}"),
                                   ]]))


@router.callback_query(F.data.startswith("stats_traffic:"))
async def cb_stats_traffic(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.services.github import get_repo_traffic
    from utils.formatters import h, panel
    data = await get_repo_traffic(session, telegram_id, repo_name)
    lines = ["---", f"  {h(repo_name.split('/')[-1])}", "---",
             f"  👁  Views    {data.get('views_count',0)} total  ·  {data.get('views_uniques',0)} unique",
             f"  📦  Clones   {data.get('clones_count',0)} total  ·  {data.get('clones_uniques',0)} unique"]
    text = panel("👁  Traffic", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬅️ Back", callback_data=f"stats:{repo_name}"),
                                       InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                                   ]]))


@router.callback_query(F.data.startswith("stats_stargazers:"))
async def cb_stats_stargazers(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.services.github import get_stargazers
    from utils.formatters import h, panel
    data = await get_stargazers(session, telegram_id, repo_name)
    total = data.get("total", 0)
    users = data.get("users", [])
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  ⭐ {total}", "---"]
    for u in users:
        lines.append(f"  ⭐  {h(u['login'])}")
    if total > 10:
        lines.append(f"  ... and {total - 10} more")
    text = panel("⭐  Stargazers", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬅️ Back", callback_data=f"stats:{repo_name}"),
                                       InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                                   ]]))


@router.callback_query(F.data.startswith("stats_contributors:"))
async def cb_stats_contributors(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    repo_name = query.data.split(":", 1)[1]
    from bot.services.github import get_contributors
    from utils.formatters import h, panel
    contribs = await get_contributors(session, telegram_id, repo_name)
    lines = ["---", f"  {h(repo_name.split('/')[-1])}", "---"]
    for i, c in enumerate(contribs, 1):
        lines.append(f"  {i}.  {h(c['login'])}   {c['contributions']} commits")
    text = panel("👥  Contributors", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬅️ Back", callback_data=f"stats:{repo_name}"),
                                       InlineKeyboardButton(text="🏠 Home", callback_data="home"),
                                   ]]))


@router.callback_query(F.data.startswith("release_delete_confirm:"))
async def cb_release_delete_confirm(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, release_id = query.data.split(":")
    from bot.services.github import delete_release
    ok = await delete_release(session, telegram_id, repo_name, int(release_id))
    await query.answer("🗑️ Release deleted." if ok else "❌ Failed", show_alert=True)
    if ok:
        from bot.handlers.releases import show_releases
        await show_releases(query, session, telegram_id, repo_name)


@router.callback_query(F.data == "gist_skip_desc")
async def cb_gist_skip_desc(query: CallbackQuery, state: FSMContext):
    await _answer(query)
    from bot.states.flow import GistFlow
    await state.update_data(description="")
    await state.set_state(GistFlow.creating_content)
    from utils.formatters import panel
    text = panel("📄  Gist Content", ["---", "  Type or paste the content:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]]))


@router.callback_query(F.data == "project_skip_desc")
async def cb_project_skip_desc(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import ProjectFlow
    data = await state.get_data()
    await state.clear()
    from database.pool import create_project
    await create_project(telegram_id, data.get("name", "project"), "")
    await query.message.edit_text(
        f"<pre>✅  Project created!</pre>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📂 Open", callback_data=f"project_open:{data.get('name','')}"),
            InlineKeyboardButton(text="🗂️ Projects", callback_data="projects"),
        ]])
    )


@router.callback_query(F.data == "project_empty_file")
async def cb_project_empty_file(query: CallbackQuery, state: FSMContext, telegram_id: int):
    await _answer(query)
    from bot.states.flow import ProjectFlow
    data = await state.get_data()
    await state.clear()
    from database.pool import get_project, update_project_files
    project = await get_project(telegram_id, data.get("project_name", ""))
    if project:
        files = dict(project.get("files") or {})
        files[data.get("file_name", "file.txt")] = ""
        await update_project_files(telegram_id, data["project_name"], files)
    await query.answer("✅ Empty file added.", show_alert=False)
    from bot.handlers.projects import show_project_detail
    await show_project_detail(query, telegram_id, data.get("project_name", ""))


@router.callback_query(F.data == "pull_skip_body")
async def cb_pull_skip_body(query: CallbackQuery, state: FSMContext, session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.states.flow import PullFlow
    data = await state.get_data()
    await state.clear()
    from bot.services.github import create_pull
    branch = session.get("active_branch", "main") if session else "main"
    result = await create_pull(session, telegram_id, data.get("repo_name", ""), data.get("title", ""), branch, "main", "")
    ok = "error" not in result
    from utils.formatters import h, panel
    text = panel("✅  Pull Request Created" if ok else "❌  Failed", [
        "---", f"  #{result.get('number','')} {h(data.get('title',''))}" if ok else f"  Error {result.get('error','')}"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬅️ Back", callback_data=f"pulls:{data.get('repo_name','')}:open:0"),
                                   ]]))


@router.callback_query(F.data == "issue_skip_body")
async def cb_issue_skip_body(query: CallbackQuery, state: FSMContext, session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.states.flow import IssueFlow
    data = await state.get_data()
    await state.clear()
    from bot.services.github import create_issue
    result = await create_issue(session, telegram_id, data.get("repo_name", ""), data.get("title", ""), "")
    ok = "error" not in result
    from utils.formatters import h, panel
    text = panel("✅  Issue Created" if ok else "❌  Failed", [
        "---", f"  #{result.get('number','')} {h(data.get('title',''))}" if ok else f"  Error {result.get('error','')}"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬅️ Back", callback_data=f"issues:{data.get('repo_name','')}:open:0"),
                                   ]]))


@router.callback_query(F.data == "release_skip_notes")
async def cb_release_skip_notes(query: CallbackQuery, state: FSMContext, session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.states.flow import ReleaseFlow
    data = await state.get_data()
    await state.clear()
    from bot.services.github import create_release
    result = await create_release(session, telegram_id, data.get("repo_name", ""), data.get("tag", ""), data.get("title", ""), "")
    ok = "error" not in result
    from utils.formatters import h, panel
    text = panel("🚀  Release Published!" if ok else "❌  Failed", [
        "---", f"  {h(data.get('tag',''))}  {h(data.get('title',''))}" if ok else f"  Error {result.get('error','')}"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                       InlineKeyboardButton(text="⬅️ Back", callback_data=f"releases:{data.get('repo_name','')}"),
                                   ]]))


@router.callback_query(F.data.startswith("issue_apply_label:"))
async def cb_issue_apply_label(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    _, repo_name, issue_num, label = query.data.split(":", 3)
    from bot.services.github import _http, _token_from_session
    token = _token_from_session(session)
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/issues/{issue_num}/labels",
        headers={"Authorization": f"token {token}"},
        json={"labels": [label]},
    ) as resp:
        ok = resp.status in (200, 201)
    await query.answer(f"✅ Label '{label}' applied." if ok else "❌ Failed", show_alert=True)


@router.callback_query(F.data == "profile_following")
async def cb_profile_following_dup(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_following
    await show_following(query, session, telegram_id)


@router.callback_query(F.data == "profile_followers")
async def cb_profile_followers_dup(query: CallbackQuery, session: Optional[dict], telegram_id: int):
    await _answer(query)
    from bot.handlers.account import show_followers
    await show_followers(query, session, telegram_id)

