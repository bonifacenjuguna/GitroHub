/**
 * Bot API 9.4 (Feb 2026) added a `style` field to both InlineKeyboardButton
 * and KeyboardButton — three preset colors: 'danger' (red), 'success'
 * (green), 'primary' (blue). Telegram just reads whatever JSON is sent, so
 * these helpers attach `style` directly onto the button object Telegraf's
 * own Markup.button.* produces, regardless of whether the installed
 * Telegraf version's own TypeScript types have caught up to this Bot API
 * version yet — sidesteps that uncertainty entirely rather than depending
 * on it.
 *
 * Locked color mapping (v0.8.5):
 *   RED    — every Cancel button, and the "Yes" side of destructive
 *            confirms (Delete Repo, Delete File, Disconnect, Storage Clear)
 *   GREEN  — the "Confirm/Yes" side of SAFE actions (Rename, License,
 *            Create Repo, Upload/Commit, Done Selecting)
 *   BLUE   — everything else (navigation, Filter/Sort, picks, pagination)
 */
const { Markup } = require('telegraf');

const RED = 'danger';
const GREEN = 'success';
const BLUE = 'primary';

/** Inline callback button with a color style applied. */
function callback(text, data, style = BLUE) {
  return { ...Markup.button.callback(text, data), style };
}

/** BBTB (reply keyboard) text button with a color style applied. */
function text(label, style = BLUE) {
  return { ...Markup.button.text(label), style };
}

module.exports = { RED, GREEN, BLUE, callback, text };
