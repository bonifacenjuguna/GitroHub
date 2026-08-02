'use strict';

const logger = require('../../utils/logger');

/**
 * Adds ctx.editOrReply(text, extra) — edits the triggering message in place
 * when the update came from a callback_query (button tap), or sends a fresh
 * message when it came from a command/text message. This is what powers
 * the "edit in place for navigation" pattern used across every menu.
 *
 * Also wraps ctx.answerCallbackQuery so an expired/stale callback query
 * (Telegram gives these roughly 30-60 seconds to live — tapping an old
 * button after leaving the chat open triggers this) can never crash the
 * whole bot process. Every menu file calls ctx.answerCallbackQuery()
 * directly and expects it to just work; patching it once here means every
 * call site is protected without having to find and edit each one
 * individually, and any new menu code written later is automatically safe
 * too.
 */
function contextExtensions() {
  return async (ctx, next) => {
    ctx.editOrReply = async (text, extra = {}) => {
      if (ctx.callbackQuery) {
        try {
          return await ctx.editMessageText(text, extra);
        } catch (err) {
          // e.g. "message not modified" or message too old to edit — fall back to a fresh send
          return ctx.reply(text, extra);
        }
      }
      return ctx.reply(text, extra);
    };

    if (ctx.callbackQuery) {
      const originalAnswerCallbackQuery = ctx.answerCallbackQuery.bind(ctx);
      ctx.answerCallbackQuery = (...args) =>
        originalAnswerCallbackQuery(...args).catch((err) => {
          // Expired/invalid query IDs are expected, routine Telegram behavior,
          // not a real error worth surfacing above debug level.
          logger.debug({ err: err.description || err.message }, 'answerCallbackQuery failed (likely expired) — ignored safely');
        });
    }

    await next();
  };
}

module.exports = contextExtensions;
