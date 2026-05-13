from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext
from aiogram import Router

from bot.services.cache import cache_delete_pattern
from bot.states.flow import SettingsFlow
from bot.ui.keyboards import settings_kb, theme_kb
from bot.ui.panel import CTX_SETTINGS, PanelManager
from database.pool import (add_alias, add_saved_path, add_template, get_aliases, get_saved_paths, get_settings, get_templates, update_settings)
from utils.formatters import on_off

async def show_settings_panel(msg_or_query, telegram_id):
    s = await get_settings(telegram_id)
    lines = ["---",
             f"  🎨  Theme         {h(s.get('theme','dark').title())}",
             f"  🕐  Time          {h(s.get('time_format','24hr'))}",
             f"  📅  Date          {h(s.get('date_format','DD/MM/YYYY'))}",
             f"  🌐  Timezone      {h(s.get('timezone','UTC'))}",
             "---",
             f"  💬  Private msg   {'Custom' if s.get('private_message') else 'Default'}",
             f"  ⌨️  Aliases       set",
             f"  📝  Templates     set",
             f"  ⭐  Saved paths   set",
    ]
    text = panel("⚙️  Settings", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_SETTINGS, f"<pre>{text}</pre>", settings_kb())

async def show_theme_picker(msg_or_query, telegram_id):
    s = await get_settings(telegram_id)
    text = panel("🎨  Choose Theme", ["---","  Select your preferred theme:"])
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_SETTINGS, f"<pre>{text}</pre>", theme_kb(s.get("theme","dark")))

async def show_time_picker(msg_or_query, telegram_id):
    s = await get_settings(telegram_id)
    cur = s.get("time_format","24hr")
    text = panel("🕐  Time Format", ["---","  Choose time format:"])
    await msg_or_query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                              InlineKeyboardButton(text="🕐 12hr"+(" ✓" if cur=="12hr" else ""),callback_data="settings_set_time:12hr"),
                                              InlineKeyboardButton(text="🕑 24hr"+(" ✓" if cur=="24hr" else ""),callback_data="settings_set_time:24hr"),
                                              InlineKeyboardButton(text="⬅️ Back",callback_data="settings_back"),
                                          ]]))

async def show_date_picker(msg_or_query, telegram_id):
    s = await get_settings(telegram_id)
    cur = s.get("date_format","DD/MM/YYYY")
    text = panel("📅  Date Format", ["---","  Choose date format:"])
    await msg_or_query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                              InlineKeyboardButton(text="DD/MM/YYYY"+(" ✓" if cur=="DD/MM/YYYY" else ""),callback_data="settings_set_date:DD/MM/YYYY"),
                                              InlineKeyboardButton(text="MM/DD/YYYY"+(" ✓" if cur=="MM/DD/YYYY" else ""),callback_data="settings_set_date:MM/DD/YYYY"),
                                              InlineKeyboardButton(text="YYYY-MM-DD"+(" ✓" if cur=="YYYY-MM-DD" else ""),callback_data="settings_set_date:YYYY-MM-DD"),
                                          ],[InlineKeyboardButton(text="⬅️ Back",callback_data="settings_back")]]))

async def prompt_timezone(query, state):
    await state.set_state(SettingsFlow.editing_timezone)
    text = panel("🌐  Timezone", ["---","  Type your timezone:","  e.g.  Africa/Nairobi  UTC+3  EST"])
    await query.message.edit_text(f"<pre>{text}</pre>", parse_mode="HTML",
                                   reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="settings_back")]]))

@router.message(SettingsFlow.editing_timezone)
async def timezone_received(message: Message, state: FSMContext, telegram_id: int):
    await state.clear()
    await update_settings(telegram_id, timezone=message.text.strip())
    await message.answer(f"✅ Timezone set to <code>{h(message.text.strip())}</code>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Settings",callback_data="settings_back")]]))

async def show_private_msg(msg_or_query, telegram_id):
    s = await get_settings(telegram_id)
    owner = s.get("pm_owner") or "Not set"
    link = s.get("pm_link") or "Not set"
    lines = ["---",f"  Owner: {h(owner)}",f"  Link: {h(link)}","---","  Variables: {owner} {botname} {date} {link}"]
    text = panel("💬  Private Message", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    await pm.update(telegram_id, chat_id, CTX_SETTINGS, f"<pre>{text}</pre>",
                    InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✏️ Edit message",callback_data="pm_edit_message"), InlineKeyboardButton(text="👁 Preview",callback_data="pm_preview")],
                        [InlineKeyboardButton(text="👤 Change owner",callback_data="pm_edit_owner"), InlineKeyboardButton(text="🔗 Set link",callback_data="pm_edit_link")],
                        [InlineKeyboardButton(text="↩️ Reset",callback_data="pm_reset"), InlineKeyboardButton(text="⬅️ Back",callback_data="settings_back")],
                    ]))

async def show_aliases(msg_or_query, session, telegram_id):
    aliases = await get_aliases(telegram_id)
    lines = ["---"]
    if aliases:
        for a in aliases: lines += [f"  {h(a['alias'])} → {h(a['command'])}","···"]
    else: lines.append("  No aliases yet.")
    lines += ["---","  Create shortcuts for long commands.","  e.g. /up → /upload src/app.py"]
    text = panel("⌨️  Aliases", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    kb = [[InlineKeyboardButton(text=f"🗑️ {a['alias']}",callback_data=f"alias_remove:{a['alias']}")] for a in aliases]
    kb += [[InlineKeyboardButton(text="➕ Add alias",callback_data="alias_add"), InlineKeyboardButton(text="⬅️ Back",callback_data="settings_back")]]
    await pm.update(telegram_id, chat_id, CTX_SETTINGS, f"<pre>{text}</pre>", InlineKeyboardMarkup(inline_keyboard=kb))

async def show_templates(msg_or_query, session, telegram_id):
    if not session: return
    templates = await get_templates(telegram_id, session["github_username"], session.get("active_repo",""))
    lines = ["---"]
    if templates:
        for t in templates: lines += [f"  {h(t['template'][:50])}","···"]
    else: lines.append("  No templates yet.")
    text = panel("📝  Commit Templates", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    kb = [[InlineKeyboardButton(text=f"🗑️ {t['template'][:30]}",callback_data=f"template_remove:{t['id']}")] for t in templates]
    kb += [[InlineKeyboardButton(text="➕ Add template",callback_data="template_add"), InlineKeyboardButton(text="⬅️ Back",callback_data="settings_back")]]
    await pm.update(telegram_id, chat_id, CTX_SETTINGS, f"<pre>{text}</pre>", InlineKeyboardMarkup(inline_keyboard=kb))

async def show_saved_paths(msg_or_query, session, telegram_id):
    if not session: return
    paths = await get_saved_paths(telegram_id, session["github_username"], session.get("active_repo",""))
    lines = ["---"]
    if paths:
        for p in paths: lines += [f"  ⭐  {h(p)}","···"]
    else: lines.append("  No saved paths yet.")
    text = panel("⭐  Saved Paths", lines)
    pm = PanelManager(msg_or_query.bot)
    chat_id = msg_or_query.message.chat.id if isinstance(msg_or_query, CallbackQuery) else msg_or_query.chat.id
    kb = [[InlineKeyboardButton(text=f"⬆️ {p.split('/')[-1]}",callback_data=f"savedpath_use:{p}"), InlineKeyboardButton(text="🗑️",callback_data=f"savedpath_remove:{p}")] for p in paths]
    kb += [[InlineKeyboardButton(text="➕ Add path",callback_data="savedpath_add"), InlineKeyboardButton(text="⬅️ Back",callback_data="settings_back")]]
    await pm.update(telegram_id, chat_id, CTX_SETTINGS, f"<pre>{text}</pre>", InlineKeyboardMarkup(inline_keyboard=kb))

async def show_display_settings(msg_or_query, telegram_id):
    await show_settings_panel(msg_or_query, telegram_id)

# FSM handlers for add flows
@router.message(SettingsFlow.adding_alias_shortcut)
async def alias_shortcut(message: Message, state: FSMContext, telegram_id: int):
    await state.update_data(alias=message.text.strip())
    await state.set_state(SettingsFlow.adding_alias_command)
    await message.answer(f"✅ Shortcut: <code>{h(message.text.strip())}</code>\n\nNow type the full command:", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel",callback_data="settings_aliases")]]))

@router.message(SettingsFlow.adding_alias_command)
async def alias_command(message: Message, state: FSMContext, telegram_id: int):
    data = await state.get_data()
    await state.clear()
    await add_alias(telegram_id, data["alias"], message.text.strip())
    await message.answer(f"✅ Alias saved: <code>{h(data['alias'])}</code> → <code>{h(message.text.strip())}</code>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Aliases",callback_data="settings_aliases")]]))

@router.message(SettingsFlow.adding_template)
async def template_text(message: Message, state: FSMContext, session: dict, telegram_id: int):
    await state.clear()
    if session:
        await add_template(telegram_id, session["github_username"], session.get("active_repo",""), message.text.strip())
    await message.answer("✅ Template saved!",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Templates",callback_data="settings_templates")]]))

@router.message(SettingsFlow.adding_savedpath)
async def savedpath_text(message: Message, state: FSMContext, session: dict, telegram_id: int):
    await state.clear()
    if session:
        clean = message.text.strip().lstrip("/")
        await add_saved_path(telegram_id, session["github_username"], session.get("active_repo",""), clean)
    await message.answer("✅ Path saved!",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Saved Paths",callback_data="settings_savedpaths")]]))

@router.message(SettingsFlow.editing_pm_message)
async def pm_message_text(message: Message, state: FSMContext, telegram_id: int):
    await state.clear()
    await update_settings(telegram_id, private_message=message.text.strip())
    await message.answer("✅ Private message updated!",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data="settings_pm")]]))

@router.message(SettingsFlow.editing_pm_owner)
async def pm_owner_text(message: Message, state: FSMContext, telegram_id: int):
    await state.clear()
    await update_settings(telegram_id, pm_owner=message.text.strip())
    await message.answer(f"✅ Owner set to <code>{h(message.text.strip())}</code>", parse_mode="HTML",
                          reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data="settings_pm")]]))

@router.message(SettingsFlow.editing_pm_link)
async def pm_link_text(message: Message, state: FSMContext, telegram_id: int):
    await state.clear()
    await update_settings(telegram_id, pm_link=message.text.strip())
    await message.answer(f"✅ Link set!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Back",callback_data="settings_pm")]]))

router = Router()
