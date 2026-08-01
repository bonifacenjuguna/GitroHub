'use strict';

const { InlineKeyboard, InputFile } = require('grammy');
const actionsApi = require('../../github/actions');
const { relativeTime } = require('../../utils/format');

function enc(s) { return encodeURIComponent(s); }
const STATUS_ICON = { success: '✅', failure: '❌', in_progress: '🟡', queued: '🟡', cancelled: '⚪' };

async function renderRunList(ctx, fullName) {
  const [owner, repoName] = fullName.split('/');
  const runs = await actionsApi.listWorkflowRuns(ctx.from.id, owner, repoName);
  let body = `⚙️ Actions — ${fullName}\n\nRecent workflow runs:\n\n`;
  const kb = new InlineKeyboard();
  runs.slice(0, 6).forEach((run, i) => {
    const icon = STATUS_ICON[run.conclusion] || STATUS_ICON[run.status] || '⚪';
    body += `${icon} ${run.name}   ${run.head_branch} · ${relativeTime(run.created_at)}\n`;
    kb.text(String(i + 1), `run:${enc(fullName)}:${run.id}`);
  });
  kb.row().text('▶️ Trigger Workflow', `run:${enc(fullName)}:trigger`).row();
  kb.text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);
  await ctx.editOrReply(body, { reply_markup: kb });
}

async function renderRunDetail(ctx, fullName, runId) {
  const [owner, repoName] = fullName.split('/');
  const run = await actionsApi.getRun(ctx.from.id, owner, repoName, runId);
  const icon = STATUS_ICON[run.conclusion] || STATUS_ICON[run.status] || '⚪';
  let body = `${icon} ${run.name}\n${run.head_branch} · commit ${run.head_sha.slice(0, 7)}\n\n🕐 Started ${relativeTime(run.created_at)}`;

  const kb = new InlineKeyboard()
    .text('📄 View Logs', `run:${enc(fullName)}:${runId}:logs`)
    .text('📦 Artifacts', `run:${enc(fullName)}:${runId}:artifacts`).row()
    .text('🔁 Re-run', `run:${enc(fullName)}:${runId}:rerun`)
    .text('🛑 Cancel', `run:${enc(fullName)}:${runId}:cancel`).row()
    .text('⬅️ Back to Actions', `repo:${enc(fullName)}:actions`);
  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerActions(bot) {
  bot.callbackQuery(/^repo:(.+):actions$/, async (ctx) => {
    await renderRunList(ctx, decodeURIComponent(ctx.match[1]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^run:(.+):(\d+)$/, async (ctx) => {
    await renderRunDetail(ctx, decodeURIComponent(ctx.match[1]), ctx.match[2]);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^run:(.+):(\d+):rerun$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    await actionsApi.rerunRun(ctx.from.id, ...fullName.split('/'), ctx.match[2]);
    await ctx.answerCallbackQuery('Re-run triggered');
    await renderRunDetail(ctx, fullName, ctx.match[2]);
  });

  bot.callbackQuery(/^run:(.+):(\d+):cancel$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    await actionsApi.cancelRun(ctx.from.id, ...fullName.split('/'), ctx.match[2]);
    await ctx.answerCallbackQuery('Cancelled');
    await renderRunDetail(ctx, fullName, ctx.match[2]);
  });

  bot.callbackQuery(/^run:(.+):(\d+):artifacts$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const artifacts = await actionsApi.listArtifacts(ctx.from.id, ...fullName.split('/'), ctx.match[2]);
    const kb = new InlineKeyboard();
    artifacts.forEach((a) => kb.text(`⬇️ ${a.name}`, `artifact:${enc(fullName)}:${a.id}:${a.name}`).row());
    kb.text('⬅️ Back to Run', `run:${enc(fullName)}:${ctx.match[2]}`);
    await ctx.editOrReply(`📦 Artifacts`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^artifact:(.+):(\d+):(.+)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    await ctx.answerCallbackQuery('Downloading...');
    const buffer = await actionsApi.downloadArtifact(ctx.from.id, ...fullName.split('/'), ctx.match[2]);
    await ctx.replyWithDocument(new InputFile(buffer, `${ctx.match[3]}.zip`));
  });

  bot.callbackQuery(/^run:(.+):trigger$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const workflows = await actionsApi.listWorkflows(ctx.from.id, ...fullName.split('/'));
    const kb = new InlineKeyboard();
    workflows.forEach((w) => kb.text(w.name, `run:${enc(fullName)}:trigger:${w.id}`).row());
    kb.text('⬅️ Cancel', `repo:${enc(fullName)}:actions`);
    await ctx.editOrReply('▶️ Select a workflow to trigger:', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^run:(.+):trigger:(\d+)$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    await actionsApi.triggerWorkflow(ctx.from.id, ...fullName.split('/'), ctx.match[2], ctx.session.activeBranch);
    await ctx.answerCallbackQuery('Workflow triggered!');
    await renderRunList(ctx, fullName);
  });
}

module.exports = { registerActions, renderRunList };
