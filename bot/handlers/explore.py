from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext
from aiogram import Router

from bot.services.github import search_users
from bot.states.flow import ExploreFlow
from bot.ui.panel import CTX_EXPLORE, PanelManager
from utils.formatters import h, panel, format_size
from utils.formatters import h, panel

async def start_search(msg_or_query, state):
    await state.set_state(ExploreFlow.searching)
    text = panel("🔍  Search Repositories", ["---","  Type your search query:","  e.g.  telegram bot python"])
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))

@router.message(ExploreFlow.searching)
async def search_received(message: Message, state: FSMContext, session: dict, telegram_id: int):
    await state.clear()
    from bot.services.github import _http, _token_from_session
    token = _token_from_session(session) if session else None
    headers = {"Authorization":f"token {token}"} if token else {}
    async with _http().get("https://api.github.com/search/repositories", headers=headers,
                            params={"q":message.text.strip(),"sort":"stars","per_page":8}) as resp:
        data = await resp.json(content_type=None) if resp.status==200 else {}
    items = data.get("items",[])
    lines = ["---", "  Query: " + h(message.text.strip()), "  Found: " + str(data.get("total_count",0)) + " results", "---"]
    kb = []
    for item in items:
        vis = "🔒" if item.get("private") else "🌍"
        lang = item.get("language") or "?"
        stars = item.get("stargazers_count",0)
        lines += [f"  {vis}  {h(item['full_name'])}", f"       ⭐{stars}  ·  {h(lang)}", f"       {h((item.get('description') or '')[:50])}","···"]
        kb.append([
            InlineKeyboardButton(text=f"📁 Open",callback_data=f"repo_open:{item['full_name']}"),
            InlineKeyboardButton(text="⬇️ Download",callback_data=f"dl_repo:{item['full_name']}"),
            InlineKeyboardButton(text="🍴 Fork",callback_data=f"repo_fork:{item['full_name']}"),
        ])
    kb.append([InlineKeyboardButton(text="🔍 Search again",callback_data="explore_search"), InlineKeyboardButton(text="🏠 Home",callback_data="home")])
    text = panel("🔍  Search Results", lines)
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def start_download_url(msg_or_query, state):
    await state.set_state(ExploreFlow.downloading)
    text = panel("⬇️  Download by URL", ["---","  Paste a GitHub URL or repo name:","---","  github.com/user/repo","  user/repo"])
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))

@router.message(ExploreFlow.downloading)
async def download_url_received(message: Message, state: FSMContext, session: dict, telegram_id: int):
    await state.clear()
    url = message.text.strip()
    repo_name = url.replace("https://github.com/","").replace("http://github.com/","").rstrip("/")
    await download_repo(message, session, telegram_id, repo_name)

async def download_repo(msg_or_query, session, telegram_id, repo_name):
    import io
    import aiohttp as aio
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    status = await msg.answer("<pre>⏳  Fetching repository...</pre>", parse_mode="HTML")
    from bot.services.github import get_repo_detail, _http, _token_from_session
    data = await get_repo_detail(session, telegram_id, repo_name)
    if not data or "error" in data:
        await status.edit_text(f"❌ Repository not found: <code>{h(repo_name)}</code>", parse_mode="HTML")
        return
    size_mb = data["size"] / 1024
    if size_mb > 500:
        await status.edit_text(
            f"<pre>" + panel("⚠️  Large Repository", ["---",f"  Size: {size_mb:.0f} MB","---","  This may exceed Telegram's 50MB limit."]) + "</pre>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Try anyway",callback_data=f"dl_repo:{repo_name}"),
                InlineKeyboardButton(text="📂 Browse instead",callback_data=f"browse:{repo_name}:"),
            ]]))
        return
    await status.edit_text("<pre>📦  Packaging files...</pre>", parse_mode="HTML")
    token = _token_from_session(session) if session else None
    headers = {"Authorization":f"token {token}","Accept":"application/vnd.github.v3+json"} if token else {}
    branch = data.get("default_branch","main")
    zip_url = f"https://api.github.com/repos/{repo_name}/zipball/{branch}"
    async with _http().get(zip_url, headers=headers) as resp:
        if resp.status != 200:
            await status.edit_text(f"❌ Download failed (status {resp.status}).")
            return
        content = await resp.read()
    size_actual = len(content)/(1024*1024)
    if size_actual > 50:
        await status.edit_text(f"❌ ZIP too large ({size_actual:.1f}MB). Telegram limit is 50MB.")
        return
    await status.edit_text("<pre>📤  Sending to Telegram...</pre>", parse_mode="HTML")
    zip_bytes = io.BytesIO(content)
    zip_name = f"{repo_name.replace('/','_')}.zip"
    vis = "🔒 Private" if data.get("private") else "🌍 Public"
    caption = f"<pre>" + panel("📦  Downloaded", ["---",f"  {h(data['name'])}",f"  {vis}  ·  {h(data.get('language') or '?')}  ·  ⭐{data.get('stars',0)}",f"  {size_actual:.1f} MB"]) + "</pre>"
    await msg.answer_document(document=zip_bytes, filename=zip_name, caption=caption, parse_mode="HTML",
                               reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                   InlineKeyboardButton(text="📂 Browse",callback_data=f"browse:{repo_name}:"),
                                   InlineKeyboardButton(text="🍴 Fork",callback_data=f"repo_fork:{repo_name}"),
                               ]]))
    await status.delete()

async def start_find_user(msg_or_query, state):
    await state.set_state(ExploreFlow.finding_user)
    text = panel("👤  Find GitHub User", ["---","  Type the GitHub username:"])
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))

@router.message(ExploreFlow.finding_user)
async def find_user_received(message: Message, state: FSMContext, session: dict, telegram_id: int):
    await state.clear()
    results = await search_users(session, message.text.strip())
    lines = ["---", f"  Results for: {h(message.text.strip())}", "---"]
    kb = []
    for u in results:
        lines += [f"  👤  {h(u['login'])}", f"       {h(u.get('name',''))}  ·  📁 {u.get('public_repos',0)} repos  ·  👥 {u.get('followers',0)}"]
        if u.get("bio"): lines.append(f"       {h(u['bio'][:50])}")
        lines.append("···")
        kb.append([
            InlineKeyboardButton(text=f"👤 {u['login']}",url=f"https://github.com/{u['login']}"),
            InlineKeyboardButton(text="➕ Follow",callback_data=f"follow_user:{u['login']}"),
        ])
    if not results: lines.append("  No users found.")
    kb.append([InlineKeyboardButton(text="🔍 Search again",callback_data="explore_find_user"), InlineKeyboardButton(text="🏠 Home",callback_data="home")])
    text = panel("👤  User Search Results", lines)
    await message.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_starred(msg_or_query, session, telegram_id):
    from bot.services.github import get_starred_repos
    starred = await get_starred_repos(session, telegram_id)
    lines = ["---", f"  {len(starred)} starred repos", "---"]
    kb = []
    for r in starred:
        lines += [f"  ⭐  {h(r['full_name'])}", f"       {h(r.get('language',''))}  ·  ⭐{r.get('stars',0)}","···"]
        kb.append([InlineKeyboardButton(text=f"📁 {r['name']}",callback_data=f"repo_open:{r['full_name']}"), InlineKeyboardButton(text="⬇️",callback_data=f"dl_repo:{r['full_name']}")])
    kb.append([InlineKeyboardButton(text="🏠 Home",callback_data="home")])
    text = panel("⭐  Starred Repositories", lines)
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_trending(msg_or_query, session, telegram_id):
    from bot.services.github import _http, _token_from_session
    token = _token_from_session(session) if session else None
    headers = {"Authorization":f"token {token}"} if token else {}
    async with _http().get("https://api.github.com/search/repositories", headers=headers,
                            params={"q":"stars:>100","sort":"stars","order":"desc","per_page":8}) as resp:
        data = await resp.json(content_type=None) if resp.status==200 else {}
    items = data.get("items",[])
    lines = ["---","  Trending on GitHub","---"]
    kb = []
    for item in items:
        lang = item.get("language") or "?"
        stars = item.get("stargazers_count",0)
        lines += [f"  📈  {h(item['full_name'])}", f"       ⭐{stars}  ·  {h(lang)}","···"]
        kb.append([InlineKeyboardButton(text=f"📁 {item['name'][:25]}",callback_data=f"repo_open:{item['full_name']}"), InlineKeyboardButton(text="⭐ Star",callback_data=f"repo_star:{item['full_name']}")])
    kb.append([InlineKeyboardButton(text="🏠 Home",callback_data="home")])
    text = panel("📈  Trending", lines)
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def start_search_code(msg_or_query, state, session):
    await state.set_state(ExploreFlow.searching)
    await state.update_data(code_search=True, repo=session.get("active_repo","") if session else "")
    text = panel("🔎  Search Code", ["---","  Type code or filename to search:"])
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="home")]]))

router = Router()
