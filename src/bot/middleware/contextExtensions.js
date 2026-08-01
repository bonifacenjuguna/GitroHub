'use strict';

/**
 * Adds ctx.editOrReply(text, extra) — edits the triggering message in place
 * when the update came from a callback_query (button tap), or sends a fresh
 * message when it came from a command/text message. This is what powers
 * the "edit in place for navigation" pattern used across every menu.
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
    await next();
  };
}

module.exports = contextExtensions;
