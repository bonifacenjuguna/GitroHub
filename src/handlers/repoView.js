const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');

async function showRepoView(ctx, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;

  let repo;
  try {
    const user = await github.getAuthenticatedUser(token);
    repo = await github.getRepo(token, user.login, repoName);
  } catch (err) {
    return ctx.reply(format.errorMessage(
      `Couldn\u2019t open "${repoName}"`,
      err.status === 404 ? 'repository not found or was renamed' : err.message,
      'Go back and refresh your repo list.'
    ));
  }

  const text =
    `📦 *${format.escapeMd(repo.name)}*\n` +
    `${format.visibilityLine(repo.private)} · ${format.languageLine(repo.language)} · ⭐ ${repo.stargazers_count}   🍴 ${repo.forks_count}   👁 ${repo.watchers_count}\n` +
    `Size: ${format.escapeMd(format.formatBytes(repo.size * 1024))}\n` +
    `Last updated: ${format.escapeMd(format.relativeTime(repo.updated_at))}\n` +
    `Created: ${format.escapeMd(format.relativeTime(repo.created_at))}`;

  ctx.session = ctx.session || {};
  ctx.session.currentRepo = repo.name;
  ctx.session.repoOwner = repo.owner.login;

  // Reply keyboard (BBTB) and inline keyboard can't share one message — send
  // the BBTB once via a tiny marker message, then the real content with only inline.
  await ctx.reply('📦 Repo View', bbtb.repoView);
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...inline.repoActions(repo.name) });
}

async function showRepoDetails(ctx, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const user = await github.getAuthenticatedUser(token);
  const repo = await github.getRepo(token, user.login, repoName);
  let fileCount = '—';
  try {
    const tree = await github.getTree(token, user.login, repoName);
    fileCount = tree.length;
  } catch (_) { /* best-effort, non-fatal */ }

  const text =
    `🔍 *${format.escapeMd(repo.name)} — Full Details*\n\n` +
    `📊 *Stats*\n` +
    `⭐ ${repo.stargazers_count} stars · 🍴 ${repo.forks_count} forks · 👁 ${repo.watchers_count} watchers\n` +
    `📂 ${fileCount} files · ${format.escapeMd(format.formatBytes(repo.size * 1024))} total\n\n` +
    `🌐 *Activity*\n` +
    `Created: ${format.escapeMd(format.relativeTime(repo.created_at))}\n` +
    `Last push: ${format.escapeMd(format.relativeTime(repo.pushed_at))}\n` +
    `Default branch: ${format.escapeMd(repo.default_branch)}\n\n` +
    `🔗 *Links*\n${format.escapeMd(repo.html_url)}`;

  await ctx.reply(text, { parse_mode: 'MarkdownV2' });
}

async function askDeleteRepo(ctx, repoName) {
  await ctx.reply(
    `⚠️ Delete "${format.escapeMd(repoName)}" permanently? \nThis cannot be undone\\.`,
    { parse_mode: 'MarkdownV2', ...inline.deleteRepoConfirm(repoName) }
  );
}

async function executeDeleteRepo(ctx, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;

  try {
    const user = await github.getAuthenticatedUser(token);
    await github.deleteRepo(token, user.login, repoName);
    await activity.log(ctx.from.id, '🗑', `Deleted repo → ${repoName}`);
    await ctx.reply(format.successMessage(`Deleted repository "${repoName}"`), bbtb.mainMenu);
  } catch (err) {
    await activity.log(ctx.from.id, '⚠️', `Delete repo failed → ${repoName}`, { detail: err.message, isError: true });
    await ctx.reply(format.errorMessage(
      `Couldn\u2019t delete "${repoName}"`,
      err.message,
      'Check your token permissions and try again.'
    ));
  }
}

async function askToggleVisibility(ctx, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const user = await github.getAuthenticatedUser(token);
  const repo = await github.getRepo(token, user.login, repoName);

  const text = repo.private
    ? `🔒 *${format.escapeMd(repoName)}* is currently Private\\.\n\nSwitching to Public will:\n• Make the code visible to anyone\n• Show it in your public GitHub profile`
    : `🌐 *${format.escapeMd(repoName)}* is currently Public\\.\n\nSwitching to Private will:\n• Hide it from search and public listings\n• Revoke access for anyone who isn\u2019t a collaborator`;

  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...inline.visibilityConfirm(repoName, repo.private) });
}

async function executeToggleVisibility(ctx, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;

  try {
    const user = await github.getAuthenticatedUser(token);
    const repo = await github.getRepo(token, user.login, repoName);
    const updated = await github.setVisibility(token, user.login, repoName, !repo.private);
    await activity.log(ctx.from.id, '🔒', `Visibility changed → ${repoName} (${repo.private ? 'Private→Public' : 'Public→Private'})`);
    await ctx.reply(format.successMessage(
      `Visibility updated: ${repoName} is now ${updated.private ? '🔒 Private' : '🌐 Public'}`
    ));
  } catch (err) {
    await activity.log(ctx.from.id, '⚠️', `Visibility change failed → ${repoName}`, { detail: err.message, isError: true });
    await ctx.reply(format.errorMessage(
      `Couldn\u2019t change visibility`,
      err.message.includes('403') ? 'your token may not have admin rights on this repo' : err.message,
      'Try reconnecting GitHub with full scope.'
    ));
  }
}

async function downloadRepo(ctx, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;

  await ctx.reply(`📦 Preparing zip of ${format.escapeMd(repoName)}\\.\\.\\.`, { parse_mode: 'MarkdownV2' });
  try {
    const user = await github.getAuthenticatedUser(token);
    const repo = await github.getRepo(token, user.login, repoName);
    const url = github.zipDownloadUrl(user.login, repoName, repo.default_branch);
    const res = await fetch(url);
    const buffer = Buffer.from(await res.arrayBuffer());

    if (buffer.length > 20 * 1024 * 1024) {
      return ctx.reply(format.errorMessage(
        'Download failed',
        `repo is ${format.formatBytes(buffer.length)} — exceeds Telegram's 20MB limit for bot-sent files`,
        `Here's a direct download link instead:\n${url}`
      ));
    }

    await ctx.replyWithDocument({ source: buffer, filename: `${repoName}.zip` });
    await activity.log(ctx.from.id, '⬇️', `Downloaded repo → ${repoName}`);
  } catch (err) {
    await activity.log(ctx.from.id, '⚠️', `Download failed → ${repoName}`, { detail: err.message, isError: true });
    await ctx.reply(format.errorMessage('Download failed', err.message, 'Try again.'));
  }
}

module.exports = {
  showRepoView,
  showRepoDetails,
  askDeleteRepo,
  executeDeleteRepo,
  askToggleVisibility,
  executeToggleVisibility,
  downloadRepo,
};
