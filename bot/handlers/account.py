
from bot.services.github import get_profile, update_profile, get_social_links, update_social_links, get_followers, get_orgs
from bot.states.flow import ProfileFlow
from bot.ui.keyboards import profile_kb, profile_edit_kb, accounts_kb
from bot.ui.panel import CTX_ACCOUNT, CTX_PROFILE, PanelManager
from utils.formatters import time_ago

async def show_accounts(msg_or_query, telegram_id):
    """Show accounts panel — callable from menu buttons."""
    from bot.handlers.auth import show_accounts as auth_show_accounts
    if isinstance(msg_or_query, Message):
        await auth_show_accounts(msg_or_query, telegram_id)
    else:
        from bot.handlers.auth import show_accounts_edit
        await show_accounts_edit(msg_or_query, telegram_id)


async def show_profile(msg_or_query, session, telegram_id):
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    if not session:
        await msg_or_query.message.answer("❌ Not logged in.")
        return
    try: await msg_or_query.message.edit_text("<pre>⏳  Loading profile...</pre>", parse_mode="HTML")
    except: pass
    data = await get_profile(session, telegram_id)
    if not data:
        await msg_or_query.message.answer("❌ Failed to load profile.")
        return
    lines = ["---", f"  {h(data['login'])}", f"  {h(data.get('name') or '')}", "---"]
    if data.get("bio"): lines += [f"  📝  {h(data['bio'][:80])}", "···"]
    lines += [
        f"  🏢  {h(data.get('company') or 'Not set')}",
        f"  📍  {h(data.get('location') or 'Not set')}",
        f"  🌐  {h(data.get('blog') or 'Not set')}",
        f"  🐦  {h(data.get('twitter_username') or 'Not set')}",
        "---",
        f"  📁  {data['public_repos']} repos",
        f"  ⭐  {data['total_stars']} stars received",
        f"  👥  {data['followers']} followers  ·  {data['following']} following",
        f"  🏆  Top: {h(data.get('top_language') or '?')}",
        f"  📋  Plan: {h(data.get('plan','free').title())}",
        f"  💼  Hireable: {'✅' if data.get('hireable') else '❌'}",
        f"  📅  Joined: {data['created_at'][:7] if data.get('created_at') else '?'}",
    ]
    text = panel(f"👤  Profile  ·  {h(data['login'])}", lines)
    await pm.update(telegram_id, chat_id, CTX_PROFILE, f"<pre>{text}</pre>", profile_kb())

async def show_edit_profile(msg_or_query, telegram_id):
    text = panel("✏️  Edit Profile", ["---", "  Tap any field to change it:", "---", "  All fields match GitHub's profile settings."])
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_PROFILE, f"<pre>{text}</pre>", profile_edit_kb())

FIELD_PROMPTS = {
    "name": ("👤  Edit Name", "Type your full name:", ProfileFlow.editing_name),
    "bio": ("📝  Edit Bio", "Type your bio (max 160 chars):", ProfileFlow.editing_bio),
    "company": ("🏢  Edit Company", "Type company name (use @ for orgs):", ProfileFlow.editing_company),
    "location": ("📍  Edit Location", "Type your location:", ProfileFlow.editing_location),
    "website": ("🌐  Edit Website", "Type your website URL:", ProfileFlow.editing_website),
    "twitter": ("🐦  Edit Twitter", "Type your Twitter username (without @):", ProfileFlow.editing_twitter),
    "pronouns": ("⚠️  Edit Pronouns", "Type your pronouns (e.g. he/him):", ProfileFlow.editing_pronouns),
    "learning": ("🎓  Currently Learning", "Type what you're currently learning:", ProfileFlow.editing_learning),
    "links": ("🔗  Social Links", "Type a URL to add (GitHub allows up to 4):", ProfileFlow.editing_link),
}

async def start_edit_profile_field(query, state, session, telegram_id, field):
    if field not in FIELD_PROMPTS:
        await query.answer("Unknown field.", show_alert=True)
        return
    title, prompt, fsm_state = FIELD_PROMPTS[field]
    await state.set_state(fsm_state)
    await state.update_data(field=field)
    text = panel(title, ["---", f"  {prompt}", "---"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="profile_edit")]]))

async def _save_profile_field(message, state, session, telegram_id, github_field):
    await state.clear()
    ok = await update_profile(session, telegram_id, **{github_field: message.text.strip()})
    await message.answer("✅ Profile updated!" if ok else "❌ Update failed.",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back to Edit",callback_data="profile_edit"), InlineKeyboardButton(text="👤 Profile",callback_data="account_profile")]]))

@router.message(ProfileFlow.editing_name)
async def profile_name(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "name")

@router.message(ProfileFlow.editing_bio)
async def profile_bio(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "bio")

@router.message(ProfileFlow.editing_company)
async def profile_company(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "company")

@router.message(ProfileFlow.editing_location)
async def profile_location(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "location")

@router.message(ProfileFlow.editing_website)
async def profile_website(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "blog")

@router.message(ProfileFlow.editing_twitter)
async def profile_twitter(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "twitter_username")

@router.message(ProfileFlow.editing_pronouns)
async def profile_pronouns(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "pronouns")

@router.message(ProfileFlow.editing_learning)
async def profile_learning(message, state, session, telegram_id): await _save_profile_field(message, state, session, telegram_id, "learning")

@router.message(ProfileFlow.editing_link)
async def profile_link(message, state, session, telegram_id):
    await state.clear()
    links = await get_social_links(session, telegram_id)
    current_urls = [l["value"] for l in links]
    if len(current_urls) >= 4:
        await message.answer("❌ Maximum 4 social links allowed. Remove one first.",
                              reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Manage Links",callback_data="profile_edit_links")]]))
        return
    current_urls.append(message.text.strip())
    ok = await update_social_links(session, telegram_id, current_urls)
    await message.answer("✅ Link added!" if ok else "❌ Failed.",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data="profile_edit")]]))

async def toggle_hireable(query, session, telegram_id):
    data = await get_profile(session, telegram_id)
    current = data.get("hireable", False) if data else False
    ok = await update_profile(session, telegram_id, hireable=not current)
    await query.answer(f"✅ Hireable: {'Yes' if not current else 'No'}" if ok else "❌ Failed", show_alert=True)
    await show_edit_profile(query, telegram_id)

async def show_pinned_manager(query, session, telegram_id):
    from database.pool import get_active_session
    s = await get_active_session(telegram_id)
    pinned = s.get("pinned_repos",[]) if s else []
    lines = ["---", f"  Up to 6 repos pinned  ({len(pinned)}/6)", "---"]
    kb = []
    for repo in pinned:
        name = repo.split("/")[-1]
        lines.append(f"  ⭐  {h(name)}")
        kb.append([InlineKeyboardButton(text=f"🗑️ Unpin {name}",callback_data=f"profile_pin_remove:{repo}")])
    if len(pinned) < 6:
        kb.append([InlineKeyboardButton(text="➕ Pin a repo",callback_data="repos:0:pushed")])
    kb.append([InlineKeyboardButton(text="⬅️ Back",callback_data="account_profile")])
    text = panel("⭐  Pinned Repositories", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_following(query, session, telegram_id):
    from bot.services.github import _http, _token_from_session
    token = _token_from_session(session)
    async with _http().get("https://api.github.com/user/following", headers={"Authorization":f"token {token}"}, params={"per_page":20}) as resp:
        following = await resp.json(content_type=None) if resp.status==200 else []
    lines = ["---", f"  {len(following)} following", "---"]
    kb = []
    for u in following:
        lines.append(f"  👤  {h(u['login'])}")
        kb.append([InlineKeyboardButton(text=f"👤 {u['login']}",url=f"https://github.com/{u['login']}"),
                   InlineKeyboardButton(text="➖ Unfollow",callback_data=f"unfollow:{u['login']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Back",callback_data="account_profile")])
    text = panel("👥  Following", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_followers(query, session, telegram_id):
    followers = await get_followers(session, telegram_id)
    lines = ["---", f"  {len(followers)} followers", "---"]
    kb = []
    for u in followers:
        lines.append(f"  👤  {h(u['login'])}")
        kb.append([InlineKeyboardButton(text=f"👤 {u['login']}",url=f"https://github.com/{u['login']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Back",callback_data="account_profile")])
    text = panel("👥  Followers", lines)
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

async def show_orgs(msg_or_query, session, telegram_id):
    orgs = await get_orgs(session, telegram_id)
    lines = ["---", f"  {len(orgs)} organizations", "---"]
    kb = []
    for org in orgs:
        lines += [f"  🏢  {h(org['login'])}", f"       {h(org.get('description','')[:50])}", f"       📁  {org['public_repos']} public repos","···"]
        kb.append([InlineKeyboardButton(text=f"🏢 {org['login']}",url=f"https://github.com/{org['login']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Back",callback_data="account_profile")])
    if not orgs: lines.append("  No organizations.")
    text = panel("🏢  Organizations", lines)
    msg = msg_or_query.message if isinstance(msg_or_query, CallbackQuery) else msg_or_query
    try: await msg.edit_text(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    except: await msg.answer(f"<pre>{text}</pre>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
