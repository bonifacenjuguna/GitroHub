'use strict';

const { InlineKeyboard } = require('grammy');
const reposApi = require('../../github/repos');
const branchesApi = require('../../github/branches');
const { renderRepoDetail } = require('./repoDetail');

function enc(s) { return encodeURIComponent(s); }

async function renderEditMenu(ctx, fullName) {
  const kb = new InlineKeyboard()
    .text('📝 Description', `repo:${enc(fullName)}:edit:description`).row()
    .text('🏷️ Topics/Tags', `repo:${enc(fullName)}:edit:topics`).row()
    .text('🌿 Default Branch', `repo:${enc(fullName)}:edit:branch`).row()
    .text('🔒 Visibility', `repo:${enc(fullName)}:edit:visibility`).row()
    .text('✏️ Rename Repo', `repo:${enc(fullName)}:edit:rename`).row()
    .text('🌐 Homepage URL', `repo:${enc(fullName)}:edit:homepage`).row()
    .text('📦 Archive Repo', `repo:${enc(fullName)}:edit:archive:confirm`).row()
    .text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);
  await ctx.editOrReply(`✏️ Edit ${fullName}\n\nWhat would you like to change?`, { reply_markup: kb });
}

function registerRepoEdit(bot) {
  bot.callbackQuery(/^repo:(.+):edit$/, async (ctx) => {
    await renderEditMenu(ctx, decodeURIComponent(ctx.match[1]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:description$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'edit_description', payload: { fullName } };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply('📝 Edit Description\n\nSend a new description.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:topics$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'edit_topics', payload: { fullName } };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply('🏷️ Edit Topics\n\nSend new topics as a comma-separated list.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:rename$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'rename_repo', payload: { fullName } };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply(`✏️ Rename Repository\n\nCurrent: ${fullName}\n\n⚠️ Existing clones/CI configs pointing to the old URL may break.\n\nSend the new name.`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:homepage$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'homepage_url', payload: { fullName } };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply('🌐 Homepage URL\n\nSend a URL.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:branch$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    const [repo, branches] = await Promise.all([
      reposApi.getRepo(ctx.from.id, owner, repoName),
      branchesApi.listBranches(ctx.from.id, owner, repoName),
    ]);
    const kb = new InlineKeyboard();
    branches.forEach((b) => kb.text(`${b.name === repo.default_branch ? '● ' : ''}${b.name}`, `repo:${enc(fullName)}:edit:branch:set:${enc(b.name)}`).row());
    kb.text('⬅️ Cancel', `repo:${enc(fullName)}:edit`);
    await ctx.editOrReply(`🌿 Default Branch\n\nCurrent: ${repo.default_branch}\n\nSelect a new default branch:`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:branch:set:(.+)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const branch = decodeURIComponent(ctx.match[2]);
    const [owner, repoName] = fullName.split('/');
    await branchesApi.setDefaultBranch(ctx.from.id, owner, repoName, branch);
    await ctx.answerCallbackQuery(`Default branch set to ${branch}`);
    await renderRepoDetail(ctx, fullName);
  });

  bot.callbackQuery(/^repo:(.+):edit:visibility$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    const repo = await reposApi.getRepo(ctx.from.id, owner, repoName);
    const kb = new InlineKeyboard()
      .text(repo.private ? '🌐 Make Public' : '🔒 Make Private', `repo:${enc(fullName)}:edit:visibility:confirm:${!repo.private}`)
      .text('❌ Cancel', `repo:${enc(fullName)}:edit`);
    await ctx.editOrReply(`🔒 Repository Visibility\n\nCurrently: ${repo.private ? 'Private' : 'Public'}\n\nChanging this affects who can see your code.`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:visibility:confirm:(true|false)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const makePrivate = ctx.match[2] === 'true';
    const kb = new InlineKeyboard()
      .text('✅ Confirm', `repo:${enc(fullName)}:edit:visibility:execute:${makePrivate}`)
      .text('❌ Cancel', `repo:${enc(fullName)}:edit`);
    await ctx.editOrReply(`⚠️ Confirm: Make ${fullName} ${makePrivate ? 'private' : 'public'}?`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:visibility:execute:(true|false)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const makePrivate = ctx.match[2] === 'true';
    const [owner, repoName] = fullName.split('/');
    await reposApi.updateRepo(ctx.from.id, owner, repoName, { private: makePrivate });
    const { logAction } = require('../../db/postgres/activityLog');
    await logAction(ctx.from.id, 'change_visibility', fullName, { private: makePrivate });
    await ctx.answerCallbackQuery('Visibility updated');
    await renderRepoDetail(ctx, fullName);
  });

  bot.callbackQuery(/^repo:(.+):edit:archive:confirm$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const kb = new InlineKeyboard().text('✅ Archive', `repo:${enc(fullName)}:edit:archive:execute`).text('❌ Cancel', `repo:${enc(fullName)}:edit`);
    await ctx.editOrReply(`📦 Archive ${fullName}?\n\nArchived repos become read-only. You can unarchive anytime. This does NOT delete anything.`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):edit:archive:execute$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    await reposApi.updateRepo(ctx.from.id, owner, repoName, { archived: true });
    await ctx.answerCallbackQuery('Archived');
    await renderRepoDetail(ctx, fullName);
  });
}

module.exports = { registerRepoEdit };
