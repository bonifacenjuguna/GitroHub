'use strict';

const { InlineKeyboard } = require('grammy');
const reposApi = require('../../github/repos');

function enc(s) { return encodeURIComponent(s); }

function registerRepoCreateImport(bot) {
  bot.callbackQuery('repo:create:start', async (ctx) => {
    ctx.session.pendingAction = { type: 'create_repo_name', payload: {} };
    await ctx.editOrReply('➕ Create New Repository\n\nSend a name for your new repo.', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('repo:import:start', async (ctx) => {
    ctx.session.pendingAction = { type: 'import_repo_url', payload: {} };
    await ctx.editOrReply('📥 Import a Repository\n\nSend the repo URL or owner/name (e.g. torvalds/linux)', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:create:visibility:(public|private):(.+)$/, async (ctx) => {
    const isPrivate = ctx.match[1] === 'private';
    const name = decodeURIComponent(ctx.match[2]);
    const repo = await reposApi.createRepo(ctx.from.id, {
      name, isPrivate, autoInit: true, gitignoreTemplate: 'Node', licenseTemplate: 'mit',
    });
    await ctx.answerCallbackQuery('Created!');
    const kb = new InlineKeyboard()
      .text('📁 Upload Files Now', `upload:set_repo:${enc(repo.full_name)}:${enc(repo.default_branch)}`)
      .text('📦 Go to Repo', `repo:open:${enc(repo.full_name)}`).row()
      .text('🏠 Main Menu', 'menu:main');
    await ctx.editOrReply(`✅ ${repo.full_name} created!`, { reply_markup: kb });
  });

  bot.callbackQuery(/^repo:import:fork:(.+)$/, async (ctx) => {
    const [owner, repoName] = decodeURIComponent(ctx.match[1]).split('/');
    const forked = await reposApi.forkRepo(ctx.from.id, owner, repoName);
    await ctx.answerCallbackQuery('Forked!');
    const kb = new InlineKeyboard().text('📦 Go to Repo', `repo:open:${enc(forked.full_name)}`).text('🏠 Main Menu', 'menu:main');
    await ctx.editOrReply(`✅ Forked! Now under your account as ${forked.full_name}.`, { reply_markup: kb });
  });
}

module.exports = { registerRepoCreateImport };
