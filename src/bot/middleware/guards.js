'use strict';

const { guardInFlight } = require('../../db/redis/cache');
const { upsertTelegramUser } = require('../../db/postgres/users');

/** Prevents double-processing when a button is tapped twice rapidly before the first edit lands. */
function inFlightGuard() {
  return async (ctx, next) => {
    if (ctx.callbackQuery?.data) {
      const ok = await guardInFlight(ctx.from.id, ctx.callbackQuery.data);
      if (!ok) {
        await ctx.answerCallbackQuery().catch(() => {});
        return;
      }
    }
    await next();
  };
}

/** Keeps the users table's Telegram identity fields fresh on every interaction (name/username changes). */
function identitySync() {
  return async (ctx, next) => {
    if (ctx.from) {
      await upsertTelegramUser(ctx.from).catch(() => {}); // never block the request on a sync failure
    }
    await next();
  };
}

module.exports = { inFlightGuard, identitySync };
