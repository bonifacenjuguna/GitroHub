'use strict';

const { InlineKeyboard } = require('grammy');
const { getClient } = require('../../github/client');

function registerGists(bot) {
  bot.callbackQuery('menu:gists', async (ctx) => {
    const octokit = await getClient(ctx.from.id).catch(() => null);
    if (!octokit) {
      return ctx.editOrReply('📋 Connect GitHub first to use Gists.', { reply_markup: new InlineKeyboard().text('🔗 Connect', 'auth:connect').row().text('⬅️ Back', 'menu:main') });
    }
    const { data } = await octokit.rest.gists.listForUser({ username: (await octokit.rest.users.getAuthenticated()).data.login, per_page: 8 });
    let body = `📋 Your Gists (${data.length})\n\n`;
    const kb = new InlineKeyboard();
    data.forEach((g, i) => {
      const filename = Object.keys(g.files)[0];
      body += `${i + 1}. ${g.description || filename}\n`;
      kb.text(String(i + 1), `gist:${g.id}`).row();
    });
    kb.text('➕ New Gist', 'gist:create').row().text('⬅️ Back to Menu', 'menu:main');
    await ctx.editOrReply(body, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('gist:create', async (ctx) => {
    ctx.session.pendingAction = { type: 'create_gist_filename', payload: {} };
    await ctx.editOrReply('📋 New Gist\n\nSend a filename (e.g. snippet.js).', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^gist:([a-f0-9]+)$/, async (ctx) => {
    const octokit = await getClient(ctx.from.id);
    const { data } = await octokit.rest.gists.get({ gist_id: ctx.match[1] });
    const filename = Object.keys(data.files)[0];
    const content = data.files[filename].content.slice(0, 800);
    await ctx.editOrReply(`📋 ${filename}\n\n${content}\n\n🔗 ${data.html_url}`, { reply_markup: new InlineKeyboard().text('⬅️ Back', 'menu:gists') });
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerGists };
