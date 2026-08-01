'use strict';

const { InlineKeyboard } = require('grammy');
const { getRateLimitSnapshot } = require('../../db/redis/cache');

function registerDevTools(bot) {
  bot.callbackQuery('menu:devtools', async (ctx) => {
    const kb = new InlineKeyboard()
      .text('🔌 API Explorer', 'devtools:api').row()
      .text('📊 Rate-Limit Monitor', 'devtools:ratelimit').row()
      .text('⬅️ Back to Menu', 'menu:main');
    await ctx.editOrReply('🛠️ Developer Tools\n\nFor power users and debugging.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('devtools:api', async (ctx) => {
    ctx.session.pendingAction = { type: 'api_explorer', payload: {} };
    await ctx.editOrReply('🔌 API Explorer\n\nSend a GitHub API endpoint to call directly (GET only).\n\ne.g. /repos/you/gitrohub-bot/commits', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('devtools:ratelimit', async (ctx) => {
    const snapshot = await getRateLimitSnapshot(ctx.from.id);
    const body = snapshot
      ? `📊 Rate-Limit Monitor\n\nRemaining: ${snapshot.remaining} / ${snapshot.limit}\nResets: ${new Date(snapshot.resetsAt).toLocaleTimeString()}`
      : '📊 No recent API calls recorded yet.';
    await ctx.editOrReply(body, { reply_markup: new InlineKeyboard().text('⬅️ Back', 'menu:devtools') });
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerDevTools };
