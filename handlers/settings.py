"""Settings, aliases, templates, saved paths — GitroHub v1.2"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import (
    add_alias, add_saved_path, add_template,
    get_active_session, get_aliases, get_saved_paths,
    get_settings, get_templates, remove_alias,
    remove_saved_path, remove_template, update_settings,
)
from utils.github_helper import h

logger = logging.getLogger(__name__)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_settings(update.message, update.effective_user.id, send_new=True)


async def show_settings(msg_or_query, telegram_id: int, send_new: bool = False):
    settings = get_settings(telegram_id)
    text = (
        f"⚙️ <b>GitroHub — Settings</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎨 Theme:     {settings.get('theme', 'dark').title()}\n"
        f"🕐 Time:      {settings.get('time_format', '24hr')}\n"
        f"📅 Date:      {settings.get('date_format', 'DD/MM/YYYY')}\n"
        f"🌐 Timezone:  {settings.get('timezone', 'UTC')}\n"
        f"🌍 Language:  English\n"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Theme", callback_data="settings_theme"),
         InlineKeyboardButton("🕐 Time", callback_data="settings_time")],
        [InlineKeyboardButton("📅 Date", callback_data="settings_date"),
         InlineKeyboardButton("🌐 Timezone", callback_data="settings_timezone")],
        [InlineKeyboardButton("💬 Private Msg", callback_data="privatemsg_menu"),
         InlineKeyboardButton("↩️ Reset All", callback_data="settings_reset")],
        [InlineKeyboardButton("🏠 Home", callback_data="home")],
    ])
    if send_new:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def cmd_privatemsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_privatemsg(update.message, update.effective_user.id, send_new=True)


async def show_privatemsg(msg_or_query, telegram_id: int, send_new: bool = False):
    settings = get_settings(telegram_id)
    owner = settings.get("private_message_owner") or "not set"
    link = settings.get("private_message_link") or "not set"
    text = (
        f"💬 <b>Private Message Settings</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Owner: <code>{h(owner)}</code>\n"
        f"Link: <code>{h(link)}</code>\n\n"
        f"<b>Variables you can use:</b>\n"
        f"<code>{{owner}}</code> <code>{{botname}}</code> <code>{{date}}</code> <code>{{link}}</code>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Edit message", callback_data="pm_edit_full"),
         InlineKeyboardButton("👁 Preview", callback_data="pm_preview")],
        [InlineKeyboardButton("👤 Change owner", callback_data="pm_edit_owner"),
         InlineKeyboardButton("🔗 Set link", callback_data="pm_edit_link")],
        [InlineKeyboardButton("↩️ Reset to default", callback_data="pm_reset"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])
    if send_new:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
    else:
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)


async def cmd_savedpaths(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_savedpaths(update.message, update.effective_user.id, send_new=True)


async def show_savedpaths(msg_or_query, telegram_id: int, send_new: bool = False):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        txt = "❌ No active repo. Use /use first."
        if send_new:
            await msg_or_query.reply_text(txt, parse_mode="HTML")
        else:
            await msg_or_query.edit_message_text(txt, parse_mode="HTML")
        return
    paths = get_saved_paths(telegram_id, session["github_username"], session["active_repo"])
    if not paths:
        text = (
            f"⭐ <b>No saved paths yet</b>\n"
            f"Repo: <code>{h(session['active_repo'])}</code>\n\n"
            f"Browse files and tap ⭐ to save paths for quick upload."
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("📂 Browse", callback_data="browse"),
            InlineKeyboardButton("➕ Add manually", callback_data="add_saved_path"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ]])
        if send_new:
            await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        return
    text = f"⭐ <b>Saved Paths — {h(session['active_repo'].split('/')[-1])}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []
    for i, path in enumerate(paths):
        text += f"{i+1}. <code>{h(path)}</code>\n"
        keyboard.append([
            InlineKeyboardButton(f"⬆️ Upload to {path.split('/')[-1]}", callback_data=f"upload_saved_{path}"),
            InlineKeyboardButton("🗑️ Remove", callback_data=f"remove_saved_{path}"),
        ])
    keyboard.append([
        InlineKeyboardButton("➕ Add path", callback_data="add_saved_path"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])
    if send_new:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_aliases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_aliases(update.message, update.effective_user.id, send_new=True)


async def show_aliases(msg_or_query, telegram_id: int, send_new: bool = False):
    aliases = get_aliases(telegram_id)
    if not aliases:
        text = (
            "⌨️ <b>No aliases set</b>\n\n"
            "Create shortcuts for long commands.\n"
            "Example: <code>/up</code> → <code>/upload src/app.py</code>"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Add alias", callback_data="add_alias"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ]])
        if send_new:
            await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        return
    text = "⌨️ <b>Your Aliases</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []
    for row in aliases:
        text += f"<code>{h(row['alias'])}</code> → <code>{h(row['command'])}</code>\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ Remove {row['alias']}", callback_data=f"remove_alias_{row['alias']}")])
    keyboard.append([
        InlineKeyboardButton("➕ Add alias", callback_data="add_alias"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])
    if send_new:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_templates(update.message, update.effective_user.id, send_new=True)


async def show_templates(msg_or_query, telegram_id: int, send_new: bool = False):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        txt = "❌ No active repo."
        if send_new:
            await msg_or_query.reply_text(txt, parse_mode="HTML")
        else:
            await msg_or_query.edit_message_text(txt, parse_mode="HTML")
        return
    templates = get_templates(telegram_id, session["github_username"], session["active_repo"])
    if not templates:
        text = (
            f"📝 <b>No commit templates yet</b>\n"
            f"Repo: <code>{h(session['active_repo'])}</code>\n\n"
            f"Example: <code>feat: {{description}}</code>"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("➕ Add template", callback_data="add_template"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ]])
        if send_new:
            await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=keyboard)
        return
    text = f"📝 <b>Commit Templates — {h(session['active_repo'].split('/')[-1])}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []
    for i, tmpl in enumerate(templates):
        text += f"{i+1}. <code>{h(tmpl['template'])}</code>\n"
        keyboard.append([
            InlineKeyboardButton(f"✅ Use: {tmpl['template'][:20]}", callback_data=f"use_template_{tmpl['id']}"),
            InlineKeyboardButton("🗑️", callback_data=f"remove_template_{tmpl['id']}"),
        ])
    keyboard.append([
        InlineKeyboardButton("➕ Add template", callback_data="add_template"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])
    if send_new:
        await msg_or_query.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await msg_or_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
