'use strict';

const { InlineKeyboard } = require('grammy');

function registerSearchMenu(bot) {
  bot.callbackQuery('menu:search', async (ctx) => {
    const kb = new InlineKeyboard()
      .text('📄 Code', 'search:code:start').text('📦 Repositories', 'search:repos:start').row()
      .text('👤 Users', 'search:users:start').text('🏢 Organizations', 'search:orgs:start').row()
      .text('⬅️ Back to Menu', 'menu:main');
    await ctx.editOrReply('🔍 Global Search\n\nSearch across all of your repositories.\n\nWhat are you searching for?', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('search:code:start', async (ctx) => {
    ctx.session.pendingAction = { type: 'search_code_global', payload: {} };
    await ctx.editOrReply('📄 Search Code (all repos)\n\nSend a search term.', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('search:repos:start', async (ctx) => {
    ctx.session.pendingAction = { type: 'search_repos', payload: {} };
    await ctx.editOrReply('📦 Search Repositories\n\nSend a name or keyword.', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('search:users:start', async (ctx) => {
    ctx.session.pendingAction = { type: 'search_users', payload: {} };
    await ctx.editOrReply('🔍 Search Users\n\nSend a GitHub username or name.', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('search:orgs:start', async (ctx) => {
    ctx.session.pendingAction = { type: 'search_orgs', payload: {} };
    await ctx.editOrReply('🔍 Search Organizations\n\nSend an org name.', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):search$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'search_code_repo', payload: { fullName } };
    await ctx.editOrReply(`🔎 Search Code — ${fullName}\n\nSend a search term.`, { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerSearchMenu };
