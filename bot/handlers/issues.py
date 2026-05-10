
from bot.services.github import get_issues, create_issue, close_issue, reopen_issue, comment_on_issue, get_labels
from bot.states.flow import IssueFlow
from bot.ui.keyboards import issues_kb, issue_detail_kb
from bot.ui.panel import CTX_ISSUES, PanelManager
from utils.formatters import time_ago, issue_state

def _dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_issues(msg_or_query, session, telegram_id, repo_name, state_filter="open", page=0):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    try: await msg_or_query.message.edit_text("<pre>⏳  Loading issues...</pre>", parse_mode="HTML")
    except: pass
    data = await get_issues(session, telegram_id, repo_name, state_filter, page)
    if "error" in data:
        await msg_or_query.message.answer("❌ Failed to load issues.")
        return
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  {data['total']} {state_filter}", "---"]
    kb_rows = []
    for issue in data["issues"]:
        labels = "  ".join(f"[{h(l)}]" for l in issue["labels"][:3])
        lines += [f"  #{issue['number']}  {h(issue['title'][:40])}", f"  {issue_state(issue['state'])}  ·  {h(time_ago(_dt(issue['created_at'])))}  {labels}", "···"]
        kb_rows.append([InlineKeyboardButton(text=f"#{issue['number']} {issue['title'][:35]}", callback_data=f"issue_view:{repo_name}:{issue['number']}")])
    text = panel("📝  Issues", lines)
    full_kb = InlineKeyboardMarkup(inline_keyboard=kb_rows + issues_kb(repo_name, state_filter, page, data["total_pages"]).inline_keyboard)
    await pm.update(telegram_id, chat_id, CTX_ISSUES, f"<pre>{text}</pre>", full_kb)

async def show_issue_detail(msg_or_query, session, telegram_id, repo_name, issue_number):
    from bot.services.github import get_issues
    for state_filter in ("open","closed"):
        data = await get_issues(session, telegram_id, repo_name, state_filter, 0)
        issue = next((i for i in data.get("issues",[]) if i["number"]==issue_number), None)
        if issue: break
    if not issue:
        await msg_or_query.message.answer("❌ Issue not found.")
        return
    labels = ", ".join(issue["labels"]) or "None"
    assignees = ", ".join(issue["assignees"]) or "None"
    lines = ["---", f"  #{issue['number']}  {h(issue['title'])}", "---",
             f"  {issue_state(issue['state'])}", f"  👤  {h(issue['user'])}  ·  {h(time_ago(_dt(issue['created_at'])))}",
             f"  🏷️  Labels: {h(labels)}", f"  👤  Assignees: {h(assignees)}", f"  💬  {issue['comments']} comments"]
    text = panel(f"📝  Issue #{issue_number}", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_ISSUES, f"<pre>{text}</pre>", issue_detail_kb(repo_name, issue_number, issue["state"]))

async def start_create_issue(query, state, repo_name):
    await state.set_state(IssueFlow.creating_title)
    await state.update_data(repo_name=repo_name)
    text = panel("➕  New Issue", ["---", f"  {h(repo_name.split('/')[-1])}", "---", "  Type the issue title:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"issues:{repo_name}:open:0")]]))

@router.message(IssueFlow.creating_title)
async def issue_title_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.update_data(title=message.text.strip())
    await state.set_state(IssueFlow.creating_body)
    await message.answer("<pre>" + panel("📝  Issue Body",["---","  Type description (or send /skip):","  What is the expected behavior?","  What actually happened?"]) + "</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⏭️ Skip",callback_data="issue_skip_body"), InlineKeyboardButton(text="❌ Cancel",callback_data="cancel")]]))

@router.message(IssueFlow.creating_body)
async def issue_body_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    result = await create_issue(session, telegram_id, data["repo_name"], data.get("title",""), message.text.strip())
    ok = "error" not in result
    text = panel("✅  Issue Created" if ok else "❌  Failed", ["---", f"  #{result.get('number','')}  {h(data.get('title',''))}" if ok else f"  Error {result.get('error','')}", f"  🔗  {h(result.get('url',''))}" if ok else ""])
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"issues:{data['repo_name']}:open:0"), InlineKeyboardButton(text="🏠 Home",callback_data="home")]]))

async def do_close_issue(query, session, telegram_id, repo_name, issue_number):
    result = await close_issue(session, telegram_id, repo_name, issue_number)
    await query.answer("✅ Issue closed." if "error" not in result else "❌ Failed", show_alert=True)
    if "error" not in result:
        await show_issues(query, session, telegram_id, repo_name, "open", 0)

async def do_reopen_issue(query, session, telegram_id, repo_name, issue_number):
    result = await reopen_issue(session, telegram_id, repo_name, issue_number)
    await query.answer("✅ Issue reopened." if "error" not in result else "❌ Failed", show_alert=True)
    if "error" not in result:
        await show_issue_detail(query, session, telegram_id, repo_name, issue_number)

async def start_comment_issue(query, state, repo_name, issue_number):
    await state.set_state(IssueFlow.commenting)
    await state.update_data(repo_name=repo_name, issue_number=issue_number)
    text = panel("💬  Add Comment", ["---", f"  Issue #{issue_number}", "---", "  Type your comment:"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data=f"issue_view:{repo_name}:{issue_number}")]]))

@router.message(IssueFlow.commenting)
async def issue_comment_received(message: Message, state: FSMContext, session, telegram_id):
    data = await state.get_data()
    await state.clear()
    result = await comment_on_issue(session, telegram_id, data["repo_name"], data["issue_number"], message.text.strip())
    await message.answer("✅ Comment posted." if "error" not in result else "❌ Failed to post comment.",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data=f"issue_view:{data['repo_name']}:{data['issue_number']}")]]))

async def show_label_picker(query, session, telegram_id, repo_name, issue_number):
    labels = await get_labels(session, telegram_id, repo_name)
    lines = ["---", f"  Issue #{issue_number}", "---"]
    kb = [[InlineKeyboardButton(text=f"🏷️ {l['name'][:30]}", callback_data=f"issue_apply_label:{repo_name}:{issue_number}:{l['name']}")] for l in labels[:15]]
    kb.append([InlineKeyboardButton(text="⬅️ Back",callback_data=f"issue_view:{repo_name}:{issue_number}")])
    for l in labels: lines.append(f"  🏷️  {h(l['name'])}  #{l['color']}")
    text = panel("🏷️  Labels", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
