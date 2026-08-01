'use strict';

const { InlineKeyboard } = require('grammy');
const repos = require('../../github/repos');
const { logAction } = require('../../db/postgres/activityLog');
const { renderRepoDetail } = require('./repoDetail');
const { renderRepoList } = require('./repositories');

function registerRepoDelete(bot) {
  bot.callbackQuery(/^repo:(.+):delete:confirm$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const kb = new InlineKeyboard()
      .text('✅ Yes, Delete', `repo:${encodeURIComponent(fullName)}:delete:execute`)
      .text('❌ Cancel', `repo:open:${encodeURIComponent(fullName)}`);
    await ctx.editOrReply(
      `⚠️ Delete ${fullName}?\n\nThis will permanently delete the repository, including all commits, branches, issues, and pull requests.\n\nThis cannot be undone.`,
      { reply_markup: kb }
    );
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):delete:execute$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    try {
      await repos.deleteRepo(ctx.from.id, owner, repoName);
      await logAction(ctx.from.id, 'delete_repo', fullName);
      const kb = new InlineKeyboard().text('⬅️ Back to Repositories', 'menu:repos');
      await ctx.editOrReply(`🗑️ ${fullName} has been deleted.`, { reply_markup: kb });
      await ctx.answerCallbackQuery('Deleted');
    } catch (err) {
      await ctx.answerCallbackQuery('Delete failed — see message', { show_alert: true });
      await renderRepoDetail(ctx, fullName);
    }
  });
}

module.exports = { registerRepoDelete };
