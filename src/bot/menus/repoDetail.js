'use strict';

const { InlineKeyboard } = require('grammy');
const repos = require('../../github/repos');
const { listPulls } = require('../../github/pullRequests');
const { listIssues } = require('../../github/issues');
const { listCommits } = require('../../github/commits');
const { getPinnedRepos } = require('../../db/postgres/preferences');
const { formatBytes, relativeTime, languageBar } = require('../../utils/format');
const { formatError } = require('../../utils/errors');

async function renderRepoDetail(ctx, fullName) {
  try {
    const [owner, repoName] = fullName.split('/');
    ctx.session.activeRepoId = fullName;

    const [repo, languages, isStarred, pinned] = await Promise.all([
      repos.getRepo(ctx.from.id, owner, repoName),
      repos.getLanguages(ctx.from.id, owner, repoName),
      repos.isStarred(ctx.from.id, owner, repoName),
      getPinnedRepos(ctx.from.id),
    ]);
    ctx.session.activeBranch = repo.default_branch;

    const [prs, issues, commits] = await Promise.all([
      listPulls(ctx.from.id, owner, repoName, 'open').catch(() => []),
      listIssues(ctx.from.id, owner, repoName, 'open').catch(() => []),
      listCommits(ctx.from.id, owner, repoName, repo.default_branch, 1, 1).catch(() => []),
    ]);

    const totalBytes = Object.values(languages).reduce((a, b) => a + b, 0) || 1;
    const langLines = Object.entries(languages)
      .slice(0, 3)
      .map(([lang, bytes]) => {
        const pct = Math.round((bytes / totalBytes) * 100);
        return `${lang} ${pct}% ${languageBar(pct)}`;
      })
      .join('\n');

    const isPinned = pinned.includes(fullName);
    const lastCommit = commits[0];

    let body = `${repo.private ? '🔵' : '🟢'} ${repo.full_name}${isPinned ? ' 📌' : ''}\n`;
    body += `${repo.private ? 'Private' : 'Public'} · Default branch: ${repo.default_branch}\n\n`;
    if (repo.description) body += `📝 ${repo.description}\n\n`;
    if (langLines) body += `${langLines}\n\n`;
    body += `📦 ${formatBytes(repo.size * 1024)}   ⭐ ${repo.stargazers_count}   🍴 ${repo.forks_count}   👁️ ${repo.subscribers_count}\n`;
    body += `🔀 ${prs.length} open PRs   🐛 ${issues.length} open issues\n`;
    if (lastCommit) {
      body += `🕐 Last commit: "${lastCommit.commit.message.split('\n')[0]}" · ${relativeTime(lastCommit.commit.author.date)}\n`;
    }
    body += `🌐 ${repo.html_url}`;

    const kb = new InlineKeyboard()
      .text('🌿 Branches', `repo:${enc(fullName)}:branches`).text('📝 Commits', `repo:${enc(fullName)}:commits`).row()
      .text('🔀 Pull Requests', `repo:${enc(fullName)}:prs`).text('🐛 Issues', `repo:${enc(fullName)}:issues`).row()
      .text('🚀 Releases', `repo:${enc(fullName)}:releases`).text('⚙️ Actions', `repo:${enc(fullName)}:actions`).row()
      .text('📁 Browse Files', `repo:${enc(fullName)}:files:`).text('🔎 Search Code', `repo:${enc(fullName)}:search`).row()
      .text('📊 Insights', `repo:${enc(fullName)}:insights`).text('🔑 Secrets', `repo:${enc(fullName)}:secrets`).row()
      .text('👥 Collaborators', `repo:${enc(fullName)}:collabs`).text('🔔 Notifications', `repo:${enc(fullName)}:notifs`).row()
      .text(isStarred ? '⭐ Unstar' : '⭐ Star', `repo:${enc(fullName)}:star:toggle`)
      .text('👁️ Watch', `repo:${enc(fullName)}:watch:toggle`).row()
      .text('🍴 Fork', `repo:${enc(fullName)}:fork`).text('📥 Download ZIP', `repo:${enc(fullName)}:download`).row()
      .text(isPinned ? '📌 Unpin' : '📌 Pin', `repo:${enc(fullName)}:pin:toggle`)
      .text('✏️ Edit Details', `repo:${enc(fullName)}:edit`).row()
      .text('🗑️ Delete Repo', `repo:${enc(fullName)}:delete:confirm`).row()
      .text('⬅️ Back to Repositories', 'menu:repos');

    await ctx.editOrReply(body, { reply_markup: kb, disable_web_page_preview: true });
  } catch (err) {
    const formatted = formatError(err, { retryCallback: `repo:open:${enc(fullName)}`, backCallback: 'menu:repos', notFoundLabel: 'This repository' });
    const kb = new InlineKeyboard();
    formatted.buttons.forEach((row) => { kb.row(); row.forEach((b) => kb.text(b.text, b.data)); });
    await ctx.editOrReply(formatted.text, { reply_markup: kb });
  }
}

function enc(fullName) {
  return encodeURIComponent(fullName);
}

function registerRepoDetail(bot) {
  bot.callbackQuery(/^repo:open:(.+)$/, async (ctx) => {
    await renderRepoDetail(ctx, decodeURIComponent(ctx.match[1]));
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repo:(.+):star:toggle$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    const currentlyStarred = await repos.isStarred(ctx.from.id, owner, repoName);
    await repos.toggleStar(ctx.from.id, owner, repoName, !currentlyStarred);
    await renderRepoDetail(ctx, fullName);
    await ctx.answerCallbackQuery(currentlyStarred ? 'Unstarred' : 'Starred!');
  });

  bot.callbackQuery(/^repo:(.+):watch:toggle$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    await repos.toggleWatch(ctx.from.id, owner, repoName, true);
    await renderRepoDetail(ctx, fullName);
    await ctx.answerCallbackQuery('Watching');
  });

  bot.callbackQuery(/^repo:(.+):fork$/, async (ctx) => {
    const fullName = decodeURIComponent(ctx.match[1]);
    const [owner, repoName] = fullName.split('/');
    const forked = await repos.forkRepo(ctx.from.id, owner, repoName);
    await ctx.answerCallbackQuery('Forked!');
    await renderRepoDetail(ctx, forked.full_name);
  });

  bot.callbackQuery(/^repo:(.+):pin:toggle$/, async (ctx) => {
    const { pinRepo, unpinRepo, getPinnedRepos: getPins } = require('../../db/postgres/preferences');
    const fullName = decodeURIComponent(ctx.match[1]);
    const pinned = await getPins(ctx.from.id);
    if (pinned.includes(fullName)) {
      await unpinRepo(ctx.from.id, fullName);
      await ctx.answerCallbackQuery('Unpinned');
    } else {
      try {
        await pinRepo(ctx.from.id, fullName);
        await ctx.answerCallbackQuery('Pinned!');
      } catch (err) {
        await ctx.answerCallbackQuery(err.message, { show_alert: true });
        return;
      }
    }
    await renderRepoDetail(ctx, fullName);
  });
}

module.exports = { registerRepoDetail, renderRepoDetail };
