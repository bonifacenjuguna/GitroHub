
from bot.services.github import get_pulls, create_pull, merge_pull, close_pull
from bot.states.flow import PullFlow
from bot.ui.keyboards import pulls_kb, pull_detail_kb
from bot.ui.panel import CTX_PULLS, PanelManager
from utils.formatters import time_ago, pr_state

def _dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_pulls(msg_or_query, session, telegram_id, repo_name, state_filter="open", page=0):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    try: await msg_or_query.message.edit_text("<pre>⏳  Loading pull requests...</pre>", parse_mode="HTML")
    except: pass
    data = await get_pulls(session, telegram_id, repo_name, state_filter, page)
    if "error" in data:
        await msg_or_query.message.answer("❌ Failed to load pull requests.")
        return
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  {data['total']} {state_filter}", "---"]
    kb_rows = []
    for pr in data["pulls"]:
        state_label = pr_state(pr["state"], pr["draft"])
        lines += [f"  #{pr['number']}  {h(pr['title'][:40])}", f"  {state_label}  ·  🌿 {h(pr['head_ref'])} → {h(pr['base_ref'])}", f"  👤 {h(pr['user'])}  ·  {h(time_ago(_dt(pr['created_at'])))}", "···"]
        kb_rows.append([InlineKeyboardButton(text=f"#{pr['number']} {pr['title'][:35]}", callback_data=f"pull_view:{repo_name}:{pr['number']}")])
    text = panel("🔀  Pull Requests", lines)
    full_kb = InlineKeyboardMarkup(inline_keyboard=kb_rows + pulls_kb(repo_name, state_filter, page, data["total_pages"]).inline_keyboard)
    await pm.update(telegram_id, chat_id, CTX_PULLS, f"<pre>{text}</pre>", full_kb)

async def show_pull_detail(msg_or_query, session, telegram_id, repo_name, pr_number):
    from bot.services.github import get_pulls
    data = await get_pulls(session, telegram_id, repo_name, "open", 0)
    pr = next((p for p in data.get("pulls",[]) if p["number"]==pr_number), None)
    if not pr:
        closed = await get_pulls(session, telegram_id, repo_name, "closed", 0)
        pr = next((p for p in closed.get("pulls",[]) if p["number"]==pr_number), None)
    if not pr:
        await msg_or_query.message.answer("❌ Pull request not found.")
        return
    lines = ["---", f"  #{pr['number']}  {h(pr['title'])}", "---", f"  {pr_state(pr['state'],pr['draft'])}", f"  🌿  {h(pr['head_ref'])} → {h(pr['base_ref'])}", f"  👤  {h(pr['user'])}", f"  🕐  {h(time_ago(_dt(pr['created_at'])))}", "---",
             f"  💬  {pr['comments']} comments  ·  📋  {pr['review_comments']} reviews", f"  Mergeable: {'✅' if pr['mergeable'] else '❌' if pr['mergeable']==False else '?'}"]
    text = panel(f"🔀  Pull Request #{pr_number}", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_PULLS, f"<pre>{text}</pre>", pull_detail_kb(repo_name, pr_number, pr["state"], bool(pr["mergeable"])))

async def start_create_pull(query, state, session, repo_name):
    await state.set_state(PullFlow.creating_title)
    await state.update_data(repo_name=repo_name)
    branch = session.get("active_branch","main") if session else "main"
    text = panel("➕  New Pull Request", ["---", f"  From: {h(branch)}", "---", "  Type the pull request title:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"pulls:{repo_name}:open:0")]]))

@router.message(PullFlow.creating_title)
async def pull_title_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.update_data(title=message.text.strip())
    await state.set_state(PullFlow.creating_body)
    await message.answer("<pre>" + panel("📝  Pull Request Body",["---","  Type description (or send /skip):","---","  What does this PR change?"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip body",callback_data="pull_skip_body"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(PullFlow.creating_body)
async def pull_body_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    branch = session.get("active_branch","main") if session else "main"
    result = await create_pull(session, telegram_id, data["repo_name"], data.get("title",""), branch, "main", message.text.strip())
    ok = "error" not in result
    text = panel("✅  Pull Request Created" if ok else "❌  Failed", ["---", f"  #{result.get('number','')}  {h(data.get('title',''))}" if ok else f"  Error {result.get('error','')}", f"  🔗  {h(result.get('url',''))}" if ok else ""])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                              InlineKeyboardButton(text="🔗 View PR",url=result["url"]) if ok else InlineKeyboardButton(text="🔄 Retry",callback_data=f"pull_create:{data['repo_name']}"),
                              InlineKeyboardButton(text="⬅️ Back",callback_data=f"pulls:{data['repo_name']}:open:0"),
                          ]]))

async def do_merge_pull(query, session, telegram_id, repo_name, pr_number, method):
    method_labels = {"merge":"Merge","squash":"Squash and merge","rebase":"Rebase and merge"}
    try: await query.message.edit_text(f"<pre>🔀  {method_labels.get(method,'Merging')}...</pre>", parse_mode="HTML")
    except: pass
    result = await merge_pull(session, telegram_id, repo_name, pr_number, method)
    ok = result.get("success")
    text = panel("✅  Merged!" if ok else "❌  Merge Failed", ["---", f"  {h(result.get('message',''))}"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Pull Requests",callback_data=f"pulls:{repo_name}:open:0"), InlineKeyboardButton(text="📜 Commits",callback_data=f"commits:{repo_name}")]]))

async def do_close_pull(query, session, telegram_id, repo_name, pr_number):
    result = await close_pull(session, telegram_id, repo_name, pr_number)
    await query.answer("✅ Pull request closed." if "error" not in result else "❌ Failed", show_alert=True)
    if "error" not in result:
        await show_pulls(query, session, telegram_id, repo_name, "open", 0)

async def do_approve_pull(query, session, telegram_id, repo_name, pr_number):
    from utils.crypto import decrypt
    from bot.services.github import _http, _token_from_session
    token = _token_from_session(session)
    async with _http().post(f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/reviews",
                             headers={"Authorization":f"token {token}"}, json={"event":"APPROVE"}) as resp:
        ok = resp.status in (200,201)
    await query.answer("✅ Approved!" if ok else "❌ Failed", show_alert=True)

async def show_pull_diff(query, session, telegram_id, repo_name, pr_number):
    await query.message.edit_text(
        f"<pre>" + panel("🔍  View PR Diff",["---","  Full diff available on GitHub:","---"]) + "</pre>", parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🌐 View Diff on GitHub", url=f"https://github.com/{repo_name}/pull/{pr_number}/files"),
            InlineKeyboardButton(text="⬅️ Back",callback_data=f"pull_view:{repo_name}:{pr_number}"),
        ]]))

async def show_pull_commits(query, session, telegram_id, repo_name, pr_number):
    from bot.services.github import _http, _token_from_session
    token = _token_from_session(session)
    async with _http().get(f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/commits",
                            headers={"Authorization":f"token {token}"}) as resp:
        commits = await resp.json(content_type=None) if resp.status==200 else []
    lines = ["---", f"  PR #{pr_number}  ·  {len(commits)} commits", "---"]
    for c in commits[:8]:
        sha = c["sha"][:7]
        msg = c["commit"]["message"].split("\n")[0][:40]
        lines += [f"  {h(sha)}  \"{h(msg)}\"","···"]
    text = panel("📜  PR Commits", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back to PR",callback_data=f"pull_view:{repo_name}:{pr_number}"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))
