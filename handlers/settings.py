import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import (
    get_active_session, get_settings, update_settings,
    get_saved_paths, add_saved_path, remove_saved_path,
    get_aliases, add_alias, remove_alias,
    get_templates, add_template, remove_template,
    get_state, set_state, clear_state
)
from handlers.core import escape_md

logger = logging.getLogger(__name__)


# ── Settings ──────────────────────────────────────────────────────────────────

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    await show_settings(update.message, telegram_id)


async def show_settings(message, telegram_id: int, edit: bool = False):
    settings = get_settings(telegram_id)

    text = (
        f"⚙️ *GitroHub — Settings*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎨 Theme:       {settings.get('theme', 'dark').title()}\n"
        f"🕐 Time:        {settings.get('time_format', '24hr')}\n"
        f"📅 Date:        {settings.get('date_format', 'DD/MM/YYYY')}\n"
        f"🌐 Timezone:    {settings.get('timezone', 'UTC')}\n"
        f"🌍 Language:    English\n"
    )

    keyboard = [
        [
            InlineKeyboardButton("🎨 Theme", callback_data="settings_theme"),
            InlineKeyboardButton("🕐 Time Format", callback_data="settings_time"),
        ],
        [
            InlineKeyboardButton("📅 Date Format", callback_data="settings_date"),
            InlineKeyboardButton("🌐 Timezone", callback_data="settings_timezone"),
        ],
        [
            InlineKeyboardButton("💬 Private Message", callback_data="privatemsg_menu"),
            InlineKeyboardButton("↩️ Reset All", callback_data="settings_reset"),
        ],
        [InlineKeyboardButton("🏠 Home", callback_data="home")]
    ]

    if edit and hasattr(message, 'edit_text'):
        await message.edit_text(text, parse_mode="MarkdownV2",
                                reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await message.reply_text(text, parse_mode="MarkdownV2",
                                 reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_privatemsg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    settings = get_settings(telegram_id)
    custom = settings.get("private_message") or "\\(default message\\)"
    owner = settings.get("private_message_owner") or "not set"
    link = settings.get("private_message_link") or "not set"

    keyboard = [
        [
            InlineKeyboardButton("📝 Edit full message",
                callback_data="pm_edit_full"),
            InlineKeyboardButton("👁 Preview", callback_data="pm_preview"),
        ],
        [
            InlineKeyboardButton("👤 Change owner username",
                callback_data="pm_edit_owner"),
            InlineKeyboardButton("🔗 Set/remove link",
                callback_data="pm_edit_link"),
        ],
        [
            InlineKeyboardButton("↩️ Reset to default",
                callback_data="pm_reset"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]
    ]

    await update.message.reply_text(
        f"💬 *Private Message Settings*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Owner username: `{escape_md(owner)}`\n"
        f"Link: `{escape_md(link)}`\n\n"
        f"*Available variables:*\n"
        f"`{{owner}}` `{{botname}}` `{{date}}` `{{link}}`",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Saved Paths ───────────────────────────────────────────────────────────────

async def cmd_savedpaths(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    paths = get_saved_paths(
        telegram_id,
        session["github_username"],
        session["active_repo"]
    )

    if not paths:
        await update.message.reply_text(
            f"⭐ *No saved paths yet*\n"
            f"Repo: `{escape_md(session['active_repo'])}`\n\n"
            f"Use /browse to navigate and tap ⭐ to save paths\\.",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📂 Browse", callback_data="browse"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
        return

    text = (
        f"⭐ *Saved Paths — {escape_md(session['active_repo'].split('/')[-1])}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    keyboard = []
    for i, path in enumerate(paths):
        text += f"{i+1}\\. `{escape_md(path)}`\n"
        keyboard.append([
            InlineKeyboardButton(f"⬆️ Upload to {path.split('/')[-1]}",
                callback_data=f"upload_saved_{path}"),
            InlineKeyboardButton("🗑️ Remove",
                callback_data=f"remove_saved_{path}"),
        ])

    keyboard.append([
        InlineKeyboardButton("➕ Add path", callback_data="add_saved_path"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])

    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Aliases ───────────────────────────────────────────────────────────────────

async def cmd_aliases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    aliases = get_aliases(telegram_id)

    if not aliases:
        await update.message.reply_text(
            "⌨️ *No aliases set*\n\n"
            "Create shortcuts for long commands\\.\n"
            "Example: `/up` → `/upload src/app\\.py`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Add alias", callback_data="add_alias"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
        return

    text = "⌨️ *Your Aliases*\n━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    keyboard = []

    for row in aliases:
        text += f"`{escape_md(row['alias'])}` → `{escape_md(row['command'])}`\n"
        keyboard.append([
            InlineKeyboardButton(f"🗑️ Remove {row['alias']}",
                callback_data=f"remove_alias_{row['alias']}"),
        ])

    keyboard.append([
        InlineKeyboardButton("➕ Add alias", callback_data="add_alias"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])

    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Templates ─────────────────────────────────────────────────────────────────

async def cmd_templates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    templates = get_templates(
        telegram_id,
        session["github_username"],
        session["active_repo"]
    )

    if not templates:
        await update.message.reply_text(
            f"📝 *No commit templates yet*\n"
            f"Repo: `{escape_md(session['active_repo'])}`\n\n"
            f"Templates help you write consistent commit messages\\.\n"
            f"Example: `feat: {{description}}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Add template",
                    callback_data="add_template"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
        return

    text = (
        f"📝 *Commit Templates — {escape_md(session['active_repo'].split('/')[-1])}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    keyboard = []
    for i, tmpl in enumerate(templates):
        text += f"{i+1}\\. `{escape_md(tmpl['template'])}`\n"
        keyboard.append([
            InlineKeyboardButton(f"✅ Use: {tmpl['template'][:20]}",
                callback_data=f"use_template_{tmpl['id']}"),
            InlineKeyboardButton("🗑️",
                callback_data=f"remove_template_{tmpl['id']}"),
        ])

    keyboard.append([
        InlineKeyboardButton("➕ Add template", callback_data="add_template"),
        InlineKeyboardButton("🏠 Home", callback_data="home"),
    ])

    await update.message.reply_text(
        text, parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
