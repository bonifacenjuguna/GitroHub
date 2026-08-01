'use strict';

const { InlineKeyboard } = require('grammy');
const branchesApi = require('../../github/branches');
const reposApi = require('../../github/repos');
const { relativeTime } = require('../../utils/format');
const { formatError } = require('../../utils/errors');

function enc(s) { return encodeURIComponent(s); }

async function renderBranchList(ctx, fullName) {
  const [owner, repoName] = fullName.split('/');
  try {
    const [repo, branches] = await Promise.all([
      reposApi.getRepo(ctx.from.id, owner, repoName),
      branchesApi.listBranches(ctx.from.id, owner, repoName),
    ]);

    let body = `🌿 Branches — ${fullName} (${branches.length} total)\n\n`;
    const kb = new InlineKeyboard();
    branches.slice(0, 10).forEach((b, i) => {
      const isDefault = b.name === repo.default_branch;
      body += `${isDefault ? '●' : ' '} ${b.name}${isDefault ? ' (default)' : ''}${b.protected ? ' 🔒' : ''}\n`;
      kb.text(String(i + 1), `branch:${enc(fullName)}:${enc(b.name)}:detail`);
    });
    kb.row();
    kb.text('➕ New Branch', `branch:${enc(fullName)}:create`).text('🧹 Delete Merged', `branch:${enc(fullName)}:delete_merged:confirm`).row();
    kb.text('⬅️ Back to Repo', `repo:open:${enc(fullName)}`);

    await ctx.editOrReply(body, { reply_markup: kb });
  } catch (err) {
    const formatted = formatError(err, { retryCallback: `repo:${enc(fullName)}:branches`, backCallback: `repo:open:${enc(fullName)}` });
    const kb = new InlineKeyboard();
    formatted.buttons.forEach((row) => { kb.row(); row.forEach((b) => kb.text(b.text, b.data)); });
    await ctx.editOrReply(formatted.text, { reply_markup: kb });
  }
}

async function renderBranchDetail(ctx, fullName, branchName) {
  const [owner, repoName] = fullName.split('/');
  const repo = await reposApi.getRepo(ctx.from.id, owner, repoName);
  const branch = await branchesApi.getBranch(ctx.from.id, owner, repoName, branchName);
  let comparison = null;
  if (branchName !== repo.default_branch) {
    comparison = await branchesApi.compareBranches(ctx.from.id, owner, repoName, repo.default_branch, branchName).catch(() => null);
  }

  let body = `🌿 ${branchName}\n${fullName}\n\n`;
  if (comparison) {
    body += `${comparison.ahead_by} commits ahead, ${comparison.behind_by} behind ${repo.default_branch}\n`;
  }
  body += `🕐 Last commit: "${branch.commit.commit.message.split('\n')[0]}" · ${relativeTime(branch.commit.commit.author.date)}\n`;
  body += `👤 by ${branch.commit.commit.author.name}\n\n`;
  body += branch.protected ? 'Protected 🔒' : 'Not protected';

  const kb = new InlineKeyboard()
    .text('📝 View Commits', `repo:${enc(fullName)}:commits`).text('📁 Browse Files', `repo:${enc(fullName)}:files:`).row()
    .text('🔀 Create Pull Request', `pr:${enc(fullName)}:create:${enc(branchName)}`).row()
    .text('⇄ Compare', `branch:${enc(fullName)}:${enc(branchName)}:compare`).row();
  if (branchName !== repo.default_branch) {
    kb.text('🗑️ Delete Branch', `branch:${enc(fullName)}:${enc(branchName)}:delete:confirm`).row();
  }
  kb.text('⬅️ Back to Branches', `repo:${enc(fullName)}:branches`);

  await ctx.editOrReply(body, { reply_markup: kb });
}

function registerBranches(bot) {
  bot.callbackQuery(/^repo:(.+):branches$/, async (ctx) => {
    await renderBranchList(ctx, decodeURIComponent(ctx.match[1]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^branch:(.+):(.+):detail$/, async (ctx) => {
    await renderBranchDetail(ctx, decodeURIComponent(ctx.match[1]), decodeURIComponent(ctx.match[2]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^branch:(.+):create$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    ctx.session.pendingAction = { type: 'create_branch', payload: { fullName } };
    const kb = new InlineKeyboard().text('❌ Cancel', 'flow:cancel');
    await ctx.editOrReply(`➕ Create New Branch\n\nBranching from: ${ctx.session.activeBranch}\n\nSend the new branch name.`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^branch:(.+):(.+):delete:confirm$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const branchName = decodeURIComponent(ctx.match[2]);
    const [owner, repoName] = fullName.split('/');
    const repo = await reposApi.getRepo(ctx.from.id, owner, repoName);
    const comparison = await branchesApi.compareBranches(ctx.from.id, owner, repoName, repo.default_branch, branchName).catch(() => null);

    let warning = `⚠️ Delete ${branchName}?`;
    if (comparison && comparison.ahead_by > 0) {
      warning += `\n\nThis branch has ${comparison.ahead_by} commits not merged into ${repo.default_branch}. Deleting it will make those commits unreachable through this bot.`;
    }
    const kb = new InlineKeyboard()
      .text('✅ Delete Anyway', `branch:${enc(fullName)}:${enc(branchName)}:delete:execute`)
      .text('❌ Cancel', `branch:${enc(fullName)}:${enc(branchName)}:detail`);
    await ctx.editOrReply(warning, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^branch:(.+):(.+):delete:execute$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const branchName = decodeURIComponent(ctx.match[2]);
    const [owner, repoName] = fullName.split('/');
    await branchesApi.deleteBranch(ctx.from.id, owner, repoName, branchName);
    await ctx.answerCallbackQuery('Branch deleted');
    await renderBranchList(ctx, fullName);
  });

  bot.callbackQuery(/^branch:(.+):delete_merged:confirm$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const kb = new InlineKeyboard()
      .text('✅ Confirm', `branch:${enc(fullName)}:delete_merged:execute`)
      .text('❌ Cancel', `repo:${enc(fullName)}:branches`);
    await ctx.editOrReply(`🧹 Delete all branches already merged into the default branch?`, { reply_markup: kb });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^branch:(.+):delete_merged:execute$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    const repo = await reposApi.getRepo(ctx.from.id, owner, repoName);
    const deleted = await branchesApi.deleteMergedBranches(ctx.from.id, owner, repoName, repo.default_branch);
    await ctx.answerCallbackQuery(`Deleted ${deleted.length} branches`);
    await renderBranchList(ctx, fullName);
  });
}

module.exports = { registerBranches, renderBranchList, renderBranchDetail };
