
from bot.services.github import get_workflows, get_workflow_runs, trigger_workflow as gh_trigger, cancel_workflow_run
from bot.ui.keyboards import actions_kb, workflow_detail_kb
from bot.ui.panel import CTX_ACTIONS, PanelManager
from utils.formatters import time_ago, workflow_state, format_duration

def _dt(s):
    if not s: return None
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s.replace("Z","+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except: return None

async def show_workflows(msg_or_query, session, telegram_id, repo_name):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    try: await msg_or_query.message.edit_text("<pre>⏳  Loading GitHub Actions...</pre>", parse_mode="HTML")
    except: pass
    workflows = await get_workflows(session, telegram_id, repo_name)
    runs = await get_workflow_runs(session, telegram_id, repo_name)
    lines = ["---", f"  {h(repo_name.split('/')[-1])}  ·  {len(workflows)} workflows", "---"]
    for wf in workflows:
        state_icon = "🟢" if wf["state"]=="active" else "⚫"
        lines += [f"  {state_icon}  {h(wf['name'])}", f"       {h(wf['path'])}","···"]
    if runs:
        lines += ["---", "  RECENT RUNS","···"]
        for r in runs[:3]:
            icon = workflow_state(r["conclusion"] or r["status"])
            lines += [f"  {icon}  {h(r['name'][:30])}  #{r['run_number']}", f"       🌿 {h(r['head_branch'])}  ·  {h(time_ago(_dt(r['created_at'])))}"]
    text = panel("⚙️  GitHub Actions", lines)
    await pm.update(telegram_id, chat_id, CTX_ACTIONS, f"<pre>{text}</pre>", actions_kb(repo_name, workflows))

async def show_workflow_detail(msg_or_query, session, telegram_id, repo_name, workflow_id):
    runs = await get_workflow_runs(session, telegram_id, repo_name, workflow_id)
    lines = ["---"]
    last_run_id = None
    for r in runs[:5]:
        icon = workflow_state(r["conclusion"] or r["status"])
        lines += [f"  {icon}  Run #{r['run_number']}  {h(r['status'])}", f"       🌿 {h(r['head_branch'])}  ·  {h(time_ago(_dt(r['created_at'])))}","···"]
        if not last_run_id: last_run_id = r["id"]
    text = panel(f"⚙️  Workflow Runs", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_ACTIONS, f"<pre>{text}</pre>", workflow_detail_kb(repo_name, workflow_id, last_run_id))

async def trigger_workflow(query, session, telegram_id, repo_name, workflow_id):
    branch = session.get("active_branch","main") if session else "main"
    ok = await gh_trigger(session, telegram_id, repo_name, workflow_id, branch)
    await query.answer("▶️ Workflow triggered!" if ok else "❌ Failed to trigger", show_alert=True)
    if ok: await show_workflow_detail(query, session, telegram_id, repo_name, workflow_id)

async def cancel_run(query, session, telegram_id, repo_name, run_id):
    ok = await cancel_workflow_run(session, telegram_id, repo_name, run_id)
    await query.answer("⛔ Run cancelled." if ok else "❌ Failed", show_alert=True)
