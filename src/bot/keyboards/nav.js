'use strict';

const { InlineKeyboard } = require('grammy');

/**
 * Every screen builder in this bot should end with one of these, per the
 * navigation standard: Back to immediate parent + Main Menu on any screen
 * beyond the top level; just "Back to Menu" on top-level screens.
 */
function withBack(keyboard, backLabel, backCallback) {
  return keyboard.row().text(`⬅️ ${backLabel}`, backCallback);
}

function withBackAndHome(keyboard, backLabel, backCallback) {
  return keyboard.row().text(`⬅️ ${backLabel}`, backCallback).text('🏠 Main Menu', 'menu:main');
}

function cancelOnly(keyboard = new InlineKeyboard()) {
  return keyboard.row().text('❌ Cancel', 'flow:cancel');
}

function confirmCancel(confirmLabel, confirmCallback, cancelCallback = 'flow:cancel') {
  return new InlineKeyboard().text(`✅ ${confirmLabel}`, confirmCallback).text('❌ Cancel', cancelCallback);
}

module.exports = { withBack, withBackAndHome, cancelOnly, confirmCancel, InlineKeyboard };
