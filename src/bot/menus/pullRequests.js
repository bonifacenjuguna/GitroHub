'use strict';

const { InlineKeyboard } = require('grammy');
const prApi = require('../../github/pullRequests');

function enc(s) { return encodeURIComponent(s); }

async function renderPrList(ctx, fullName) {
  const [owner, repoName] = fullName.split('/');
  const prs = await prApi.listPulls(ctx.from.id, owner, repoName, 'open');
  let body = `🔀 Pull Requests — ${fullName} (${prs.length} open)\n\n`;
  const kb = new InlineKeyboard();
  prs.slice(0, 8).forEach((pr, i) => {
    body += `#${pr.number} ${pr.title}\n    ${pr.head.ref} → ${pr.base.ref}\n\n`;
    kb.text(String(i + 1), `pr:${enc(fullName)}:${pr.number}`);
  });
  kb.row().text('➕ New PR', `pr:${enc(fullName)}:create:${enc(ctx.session.activeBranch)}`).row();
  kb.text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);
  await ctx.editOrReply(body, { reply_markup: kb });
}

async function renderPrDetail(ctx, fullName, number) {
  const [owner, repoName] = fullName.split('/');
  const pr = await prApi.getPull(ctx.from.id, owner, repoName, number);
  let body = `#${pr.number} ${pr.title}\n${pr.head.ref} → ${pr.base.ref}\n👤 ${pr.user.login}\n`;
  body += pr.mergeable === false ? '❌ Has conflicts' : '✅ No conflicts';
  if (pr.body) body += `\n\n📝 ${pr.body.slice(0, 300)}`;

  const kb = new InlineKeyboard()
    .text('📄 View Diff', `pr:${enc(fullName)}:${number}:diff`).text('👥 Request Reviewers', `pr:${enc(fullName)}:${number}:reviewers`).row()
    .text('✅ Merge', `pr:${enc(fullName)}:${number}:merge:menu`).text('❌ Close', `pr:${enc(fullName)}:${number}:close`).row()
    .text('⬅️ Back to PRs', `repo:${enc(fullName)}:prs`);
  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerPullRequests(bot) {
  bot.callbackQuery(/^repo:(.+):prs$/, async (ctx) => {
    await renderPrList(ctx, decodeURIComponent(ctx.match[1]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^pr:(.+):(\d+)$/, async (ctx) => {
    await renderPrDetail(ctx, decodeURIComponent(ctx.match[1]), Number(ctx.match[2]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^pr:(.+):create:(.+)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const head = decodeURIComponent(ctx.match[2]);
    ctx.session.pendingAction = { type: 'create_pr_title', payload: { fullName, head } };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply(`🔀 Create Pull Request\n\n${head} → default branch\n\nSend a title for this PR.`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^pr:(.+):(\d+):diff$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const diff = await prApi.getDiff(ctx.from.id, ...fullName.split('/'), Number(ctx.match[2]));
    await ctx.reply(String(diff).slice(0, 3500));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^pr:(.+):(\d+):merge:menu$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const num = ctx.match[2];
    const kb = new InlineKeyboard()
      .text('🔀 Merge Commit', `pr:${enc(fullName)}:${num}:merge:merge`)
      .text('📎 Squash', `pr:${enc(fullName)}:${num}:merge:squash`)
      .text('🌿 Rebase', `pr:${enc(fullName)}:${num}:merge:rebase`).row()
      .text('❌ Cancel', `pr:${enc(fullName)}:${num}`);
    await ctx.editOrReply('Merge method:', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^pr:(.+):(\d+):merge:(merge|squash|rebase)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const num = Number(ctx.match[2]);
    const result = await prApi.mergePull(ctx.from.id, ...fullName.split('/'), num, ctx.match[3]);
    await ctx.answerCallbackQuery('Merged!');
    await ctx.editOrReply(`✅ PR #${num} merged.\nCommit: ${result.sha.slice(0, 7)}`, { reply_markup: new InlineKeyboard().text('⬅️ Back to PRs', `repo:${enc(fullName)}:prs`) });
  });

  bot.callbackQuery(/^pr:(.+):(\d+):close$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    await prApi.closePull(ctx.from.id, ...fullName.split('/'), Number(ctx.match[2]));
    await ctx.answerCallbackQuery('Closed');
    await renderPrList(ctx, fullName);
  });

  bot.callbackQuery(/^pr:(.+):(\d+):reviewers$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const reposApi = require('../../github/repos');
    const collabs = await reposApi.listCollaborators(ctx.from.id, ...fullName.split('/'));
    const kb = new InlineKeyboard();
    collabs.forEach((c) => kb.text(c.login, `pr:${enc(fullName)}:${ctx.match[2]}:reviewers:add:${c.login}`).row());
    kb.text('⬅️ Back to PR', `pr:${enc(fullName)}:${ctx.match[2]}`);
    await ctx.editOrReply('👥 Select a reviewer to request:', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^pr:(.+):(\d+):reviewers:add:(.+)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    await prApi.requestReviewers(ctx.from.id, ...fullName.split('/'), Number(ctx.match[2]), [ctx.match[3]]);
    await ctx.answerCallbackQuery(`Requested @${ctx.match[3]}`);
    await renderPrDetail(ctx, fullName, Number(ctx.match[2]));
  });
}

module.exports = { registerPullRequests, renderPrList };
