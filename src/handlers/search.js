const Fuse = require('fuse.js');
const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');
const { Markup } = require('telegraf');

const GITHUB_URL_RE = /^(?:https?:\/\/)?(?:www\.)?github\.com\/([a-zA-Z0-9-]+)\/([a-zA-Z0-9._-]+?)(?:\.git)?\/?$/;

function parseGithubUrl(input) {
  const match = input.trim().match(GITHUB_URL_RE);
  if (!match) return null;
  return { owner: match[1], repo: match[2] };
}

async function handleSearchInput(ctx, query) {
  const parsed = parseGithubUrl(query);
  if (parsed) return handleExternalRepo(ctx, parsed.owner, parsed.repo);
  return handleRepoSearch(ctx, query);
}

async function handleRepoSearch(ctx, query) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const repos = await github.listRepos(token);
  const fuse = new Fuse(repos, { keys: ['name'], threshold: 0.4, includeScore: true });
  const results = fuse.search(query);

  if (results.length === 0) {
    return ctx.reply(
      format.errorMessage(
        `No repos matched "${query}"`,
        `you have ${repos.length} repos total — check spelling, or browse the full list instead`,
      ),
      bbtb.searchAgain
    );
  }

  const close = results.filter((r) => r.score <= 0.15).map((r) => r.item);
  const similar = results.filter((r) => r.score > 0.15).map((r) => r.item);

  let text = `🔍 *Results for "${format.escapeMd(query)}"*\n\n`;
  const rows = [];
  let counter = 1;

  if (close.length) {
    text += '🎯 *Close Matches*\n';
    for (const r of close) {
      text += `${counter}\\. 📦 ${format.escapeMd(r.name)}\n   ${format.visibilityLine(r.private)} · ${format.languageLine(r.language)} · ⭐ ${r.stargazers_count}\n`;
      rows.push([Markup.button.callback(`${counter}. ${r.name}`, `repo:${r.name}`)]);
      counter++;
    }
  }
  if (similar.length) {
    text += '\n🔁 *Similar Spelling*\n';
    for (const r of similar) {
      text += `${counter}\\. 📦 ${format.escapeMd(r.name)}\n   ${format.visibilityLine(r.private)} · ${format.languageLine(r.language)} · ⭐ ${r.stargazers_count}\n`;
      rows.push([Markup.button.callback(`${counter}. ${r.name}`, `repo:${r.name}`)]);
      counter++;
    }
  }

  await ctx.reply('🔍 Search Results', bbtb.searchAgain);
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...Markup.inlineKeyboard(rows) });
}

async function handleExternalRepo(ctx, owner, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;

  try {
    const repo = await github.getRepo(token, owner, repoName);
    if (repo.private) {
      return ctx.reply(format.errorMessage(
        `Couldn\u2019t find "${owner}/${repoName}"`,
        'it\u2019s private and you don\u2019t have access (only public repos can be downloaded/forked this way)',
      ));
    }

    ctx.session = ctx.session || {};
    ctx.session.externalRepo = { owner, repo: repoName };

    const text =
      `🔗 *External Repo Detected*\n\n` +
      `📦 ${format.escapeMd(repo.name)}\n` +
      `👤 by ${format.escapeMd(owner)}\n` +
      `${format.visibilityLine(repo.private)} · ${format.languageLine(repo.language)} · ⭐ ${repo.stargazers_count} · 🍴 ${repo.forks_count}`;

    const keyboard = Markup.inlineKeyboard([
      [Markup.button.callback('⬇️ Download as ZIP', 'external:download')],
      [Markup.button.callback('🍴 Fork to My Account', 'external:fork')],
      [Markup.button.url('🔗 View on GitHub', repo.html_url)],
      [Markup.button.callback('⬅️ Cancel', 'external:cancel')],
    ]);

    await ctx.reply(text, { parse_mode: 'MarkdownV2', ...keyboard });
  } catch (err) {
    if (err.status === 404) {
      return ctx.reply(format.errorMessage(
        `Couldn\u2019t find "${owner}/${repoName}"`,
        'it doesn\u2019t exist, was renamed, or is private',
      ));
    }
    await ctx.reply(format.errorMessage('Lookup failed', err.message, 'Try again.'));
  }
}

async function downloadExternalZip(ctx) {
  const { owner, repo } = ctx.session.externalRepo;
  const token = await requireConnected(ctx);
  if (!token) return;

  await ctx.reply(`📦 Preparing zip of ${format.escapeMd(owner)}/${format.escapeMd(repo)}\\.\\.\\.`, { parse_mode: 'MarkdownV2' });
  try {
    const repoData = await github.getRepo(token, owner, repo);
    const url = github.zipDownloadUrl(owner, repo, repoData.default_branch);
    const res = await fetch(url);
    const buf = Buffer.from(await res.arrayBuffer());

    if (buf.length > 20 * 1024 * 1024) {
      return ctx.reply(format.errorMessage(
        'Download failed',
        `repo is ${format.formatBytes(buf.length)} — exceeds Telegram's 20MB limit for bot-sent files`,
        `Here's a direct download link instead:\n${url}`
      ));
    }

    await ctx.replyWithDocument({ source: buf, filename: `${repo}.zip` });
    await activity.log(ctx.from.id, '⬇️', `Downloaded external repo → ${owner}/${repo}`);
  } catch (err) {
    await ctx.reply(format.errorMessage('Download failed', err.message, 'Try again later.'));
  }
}

async function forkExternal(ctx) {
  const { owner, repo } = ctx.session.externalRepo;
  await ctx.reply(
    `🍴 Fork "${format.escapeMd(repo)}" to your GitHub account\\?\n\nThis creates a copy under your account that you can edit, upload to, and manage like any other repo\\.`,
    { parse_mode: 'MarkdownV2', ...inline.forkConfirm() }
  );
}

async function executeForkExternal(ctx) {
  const { owner, repo } = ctx.session.externalRepo;
  const token = await requireConnected(ctx);
  if (!token) return;

  try {
    const forked = await github.forkRepo(token, owner, repo);
    await activity.log(ctx.from.id, '🍴', `Forked → ${owner}/${repo}`);
    await ctx.reply(
      `✅ Forked\\! ${format.escapeMd(repo)} is now in your account\\.`,
      { parse_mode: 'MarkdownV2', ...inline.createRepoSuccess(forked.name) }
    );
  } catch (err) {
    const reason = err.message.includes('name already exists')
      ? `you already have a repo named "${repo}" — GitHub forks must keep the original name`
      : err.message;
    await activity.log(ctx.from.id, '⚠️', `Fork failed → ${owner}/${repo}`, { detail: err.message, isError: true });
    await ctx.reply(format.errorMessage('Fork failed', reason, 'Rename or delete your existing repo, then retry.'));
  }
}

module.exports = {
  handleSearchInput,
  handleRepoSearch,
  handleExternalRepo,
  downloadExternalZip,
  forkExternal,
  executeForkExternal,
  parseGithubUrl,
};
