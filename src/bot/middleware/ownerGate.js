'use strict';

const env = require('../../config/env');
const logger = require('../../utils/logger');

/**
 * Global gate — must be the FIRST middleware registered on the bot.
 * Any update from a Telegram user ID other than BOT_OWNER_ID is dropped
 * immediately: no reply, no typing indicator, no logged "rejected"
 * interaction beyond a minimal debug-level trace. This runs before
 * session middleware, before any DB/Redis touch, before any GitHub call —
 * strangers cost the bot nothing beyond the webhook receipt itself.
 */
function ownerGate() {
  return async (ctx, next) => {
    const userId = ctx.from?.id;

    if (userId === undefined) {
      return; // no identifiable user (e.g. channel post) — drop silently
    }

    if (userId !== env.BOT_OWNER_ID) {
      // Deliberately minimal — never log this at info/warn level in production,
      // never call ctx.reply(). A responsive bot confirms it's alive; we don't want that.
      logger.debug({ userId }, 'Dropped update from non-owner user');
      return;
    }

    await next();
  };
}

module.exports = ownerGate;
