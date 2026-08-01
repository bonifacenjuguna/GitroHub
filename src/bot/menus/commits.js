'use strict';

const { InlineKeyboard } = require('grammy');
const commitsApi = require('../../github/commits');
const { relativeTime } = require('../../utils/format');

function enc(s) { return encodeURIComponent(s); }

async function renderCommitList(ctx, fullName, page = 1) {
  const [owner, repoName] = fullName.split('/');
  const branch = ctx.session.activeBranch || 'main';
  const commits = await commitsApi.listCommits(ctx.from.id, owner, repoName, branch, page, 5);

  let body = `📝 Commits — ${fullName}\nBranch: ${branch}\n\n`;
  const kb = new InlineKeyboard();
  commits.forEach((c, i) => {
    body += `${c.sha.slice(0, 7)}  ${c.commit.message.split('\n')[0]}\n         👤 ${c.commit.author.name} · 🕐 ${relativeTime(c.commit.author.date)}\n\n`;
    kb.text(String(i + 1), `commit:${enc(fullName)}:${c.sha}`);
  });
  kb.row().text('◀️', `repo:${enc(fullName)}:commits:page:${Math.max(1, page - 1)}`).text(`Page ${page}`, 'noop').text('▶️', `repo:${enc(fullName)}:commits:page:${page + 1}`).row();
  kb.text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);

  await ctx.editOrReply(body, { reply_markup: kb });
}

async function renderCommitDetail(ctx, fullName, sha) {
  const [owner, repoName] = fullName.split('/');
  const commit = await commitsApi.getCommit(ctx.from.id, owner, repoName, sha);

  let body = `📝 ${commit.commit.message.split('\n')[0]}\n\n${commit.sha}\n👤 ${commit.commit.author.name}  🕐 ${relativeTime(commit.commit.author.date)}\n\n`;
  body += `Changed ${commit.files.length} files: +${commit.stats.additions} −${commit.stats.deletions}\n\n`;
  commit.files.slice(0, 5).forEach((f) => (body += `📄 ${f.filename}        +${f.additions} −${f.deletions}\n`));

  const kb = new InlineKeyboard()
    .text('📄 View Diff', `commit:${enc(fullName)}:${sha}:diff`).row()
    .text('🔀 Revert Commit', `commit:${enc(fullName)}:${sha}:revert:confirm`)
    .text('🍒 Cherry-pick', `commit:${enc(fullName)}:${sha}:cherrypick`).row()
    .text('⬅️ Back to Commits', `repo:${enc(fullName)}:commits`);

  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerCommits(bot) {
  bot.callbackQuery(/^repo:(.+):commits$/, async (ctx) => {
    await renderCommitList(ctx, decodeURIComponent(ctx.match[1]), 1);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):commits:page:(\d+)$/, async (ctx) => {
    await renderCommitList(ctx, decodeURIComponent(ctx.match[1]), Number(ctx.match[2]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^commit:(.+):([a-f0-9]+)$/, async (ctx) => {
    await renderCommitDetail(ctx, decodeURIComponent(ctx.match[1]), ctx.match[2]);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^commit:(.+):([a-f0-9]+):diff$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    const octokit = await require('../../github/client').getClient(ctx.from.id);
    const { data } = await octokit.rest.repos.getCommit({ owner, repo: repoName, ref: ctx.match[2], mediaType: { format: 'diff' } });
    const truncated = String(data).slice(0, 3500);
    await ctx.reply('```diff\n' + truncated + '\n```', { parse_mode: 'MarkdownV2' }).catch(() => ctx.reply(truncated));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^commit:(.+):([a-f0-9]+):revert:confirm$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const kb = new InlineKeyboard().text('✅ Confirm Revert', `commit:${enc(fullName)}:${ctx.match[2]}:revert:execute`).text('❌ Cancel', `commit:${enc(fullName)}:${ctx.match[2]}`);
    await ctx.editOrReply('🔀 Revert this commit? A new commit will be created that reverses these changes.', { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^commit:(.+):([a-f0-9]+):revert:execute$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const result = await commitsApi.revertCommit(ctx.from.id, ...fullName.split('/'), ctx.match[2], ctx.session.activeBranch);
    await ctx.answerCallbackQuery('Reverted');
    await ctx.editOrReply(`✅ Revert committed: ${result.sha.slice(0, 7)}`, { reply_markup: new InlineKeyboard().text('⬅️ Back to Commits', `repo:${enc(fullName)}:commits`) });
  });
}

module.exports = { registerCommits, renderCommitList };
