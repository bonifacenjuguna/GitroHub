'use strict';

const { InlineKeyboard } = require('grammy');
const issuesApi = require('../../github/issues');

function enc(s) { return encodeURIComponent(s); }

async function renderIssueList(ctx, fullName) {
  const [owner, repoName] = fullName.split('/');
  const issues = await issuesApi.listIssues(ctx.from.id, owner, repoName, 'open');
  let body = `🐛 Issues — ${fullName} (${issues.length} open)\n\n`;
  const kb = new InlineKeyboard();
  issues.slice(0, 8).forEach((issue, i) => {
    const labels = issue.labels.map((l) => l.name).join(', ');
    body += `#${issue.number} ${issue.title}\n    ${labels ? `🏷️ ${labels} · ` : ''}${issue.comments} comments\n\n`;
    kb.text(String(i + 1), `issue:${enc(fullName)}:${issue.number}`);
  });
  kb.row().text('➕ New Issue', `issue:${enc(fullName)}:create`).text('🎯 Milestones', `issue:${enc(fullName)}:milestones`).row();
  kb.text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);
  await ctx.editOrReply(body, { reply_markup: kb });
}

async function renderIssueDetail(ctx, fullName, number) {
  const [owner, repoName] = fullName.split('/');
  const issue = await issuesApi.getIssue(ctx.from.id, owner, repoName, number);
  let body = `#${issue.number} ${issue.title}\n`;
  if (issue.labels.length) body += `🏷️ ${issue.labels.map((l) => l.name).join(', ')}\n`;
  body += `👤 opened by ${issue.user.login}\n\n${issue.body ? issue.body.slice(0, 300) : ''}\n\n💬 ${issue.comments} comments`;

  const kb = new InlineKeyboard()
    .text('💬 Comment', `issue:${enc(fullName)}:${number}:comment`)
    .text('🎯 Milestone', `issue:${enc(fullName)}:${number}:milestone`).row()
    .text(issue.state === 'open' ? '✅ Close Issue' : '🔓 Reopen', `issue:${enc(fullName)}:${number}:toggle`).row()
    .text('⬅️ Back to Issues', `repo:${enc(fullName)}:issues`);
  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerIssues(bot) {
  bot.callbackQuery(/^repo:(.+):issues$/, async (ctx) => {
    await renderIssueList(ctx, decodeURIComponent(ctx.match[1]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^issue:(.+):(\d+)$/, async (ctx) => {
    await renderIssueDetail(ctx, decodeURIComponent(ctx.match[1]), Number(ctx.match[2]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^issue:(.+):create$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'create_issue_title', payload: { fullName } };
    await ctx.editOrReply('🐛 New Issue\n\nSend a title.', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^issue:(.+):(\d+):toggle$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const num = Number(ctx.match[2]);
    const issue = await issuesApi.getIssue(ctx.from.id, ...fullName.split('/'), num);
    if (issue.state === 'open') await issuesApi.closeIssue(ctx.from.id, ...fullName.split('/'), num);
    else await issuesApi.reopenIssue(ctx.from.id, ...fullName.split('/'), num);
    await ctx.answerCallbackQuery('Updated');
    await renderIssueDetail(ctx, fullName, num);
  });

  bot.callbackQuery(/^issue:(.+):(\d+):comment$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'issue_comment', payload: { fullName, number: Number(ctx.match[2]) } };
    await ctx.editOrReply('💬 Send your comment.', { reply_markup: new InlineKeyboard().text('❌ Cancel', 'flow:cancel') });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^issue:(.+):milestones$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const milestones = await issuesApi.listMilestones(ctx.from.id, ...fullName.split('/'));
    let body = `🎯 Milestones — ${fullName}\n\n`;
    milestones.forEach((m) => (body += `${m.title} — ${m.closed_issues}/${m.open_issues + m.closed_issues} closed\n`));
    await ctx.editOrReply(body || '🎯 No milestones yet.', { reply_markup: new InlineKeyboard().text('⬅️ Back to Issues', `repo:${enc(fullName)}:issues`) });
    await ctx.answerCallbackQuery();
  });
}

module.exports = { registerIssues, renderIssueList };
