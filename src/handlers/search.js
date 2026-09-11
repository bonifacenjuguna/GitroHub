const Fuse = require('fuse.js');
const github = require('../lib/github');
const repoCache = require('../lib/repoCache');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const activity = require('../lib/activity');
const { Markup } = require('telegraf');
const style = require('../keyboards/buttonStyle');
const ephemeral = require('../lib/ephemeral');

const GITHUB_URL_RE = /^(?:https?:\/\/)?(?:www\.)?github\.com\/([a-zA-Z0-9-]+)\/([a-zA-Z0-9._-]+?)(?:\.git)?\/?$/;

// Advanced search qualifiers — GitHub-style `key:value` tokens that combine
// with whatever free text is left over. Reuses lib/filterClauses.js (the
// same engine behind Bulk Actions' filter builder and Smart Folders) so
// "private repos matching auth" and "a Smart Folder for private repos"
// agree on exactly what "private" means.
const QUALIFIER_RE = /\b(is|lang|language|tag|stars):(\S+)/gi;

/** Splits a raw query into filterClauses-shaped clauses plus whatever free
 * text remains for fuzzy matching. Unrecognized qualifier values are
 * dropped silently rather than erroring — worst case they just don't
 * narrow anything, same "fail open" philosophy as filterClauses itself. */
function parseAdvancedQuery(query, userTags) {
  const clauses = [];
  let freeText = query;
  let match;
  QUALIFIER_RE.lastIndex = 0;
  while ((match = QUALIFIER_RE.exec(query))) {
    const [full, rawKey, rawVal] = match;
    const key = rawKey.toLowerCase();
    const val = rawVal;

    if (key === 'is') {
      const v = val.toLowerCase();
      if (v === 'private' || v === 'public') clauses.push({ type: 'visibility', value: v });
      else if (v === 'fork') clauses.push({ type: 'fork', value: 'true' });
      else if (v === 'notfork') clauses.push({ type: 'fork', value: 'false' });
      else if (v === 'licensed') clauses.push({ type: 'haslicense', value: true });
      else if (v === 'unlicensed') clauses.push({ type: 'nolicense', value: true });
    } else if (key === 'lang' || key === 'language') {
      clauses.push({ type: 'language', value: val });
    } else if (key === 'tag') {
      const tag = userTags.find((t) => t.name.toLowerCase() === val.toLowerCase());
      if (tag) clauses.push({ type: 'tag', value: tag.id });
    } else if (key === 'stars') {
      const m = val.match(/^(>=|<=|>|<)?(\d+)$/);
      if (m) clauses.push({ type: 'stars', value: { op: m[1] || '=', num: Number(m[2]) } });
    }
    freeText = freeText.replace(full, ' ');
  }
  return { clauses, freeText: freeText.replace(/\s+/g, ' ').trim() };
}

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

/** 📁 My Repos search entry point — fuzzy-searches only your own repos.
 * Doesn't guess intent from a single shared box (see handlePublicRepoInput
 * for the other explicit entry point) — a GitHub link pasted here is
 * treated as a literal (probably not matching) search term, not auto-detected. */
async function handleMyReposSearchInput(ctx, query) {
  return handleRepoSearch(ctx, query);
}

/** 🌐 Public Repo entry point — expects a GitHub link, view/fork/download only. */
async function handlePublicRepoInput(ctx, input) {
  const parsed = parseGithubUrl(input);
  if (!parsed) {
    return ctx.reply(format.errorMessage(
      'Not a GitHub repo link',
      `"${input}" doesn\u2019t look like a github.com/owner/repo URL`,
      'Paste a full repo link, e.g. https://github.com/owner/repo, or ❌ Cancel.'
    ));
  }
  return handleExternalRepo(ctx, parsed.owner, parsed.repo);
}

async function handleRepoSearch(ctx, query) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const searchHistory = require('../lib/searchHistory');
  await searchHistory.record(ctx.from.id, query); // #12 — best-effort, non-blocking to the actual search

  const repos = await repoCache.getRepos(ctx.from.id, token);

  // Advanced qualifiers (is:private, lang:JavaScript, tag:work, stars:>50,
  // etc.) narrow the pool first; whatever free text is left, if any, then
  // goes through the usual fuzzy pass on top of that narrowed set.
  const filterClauses = require('../lib/filterClauses');
  const tags = require('../lib/tags');
  const userTags = await tags.listTags(ctx.from.id).catch(() => []);
  const { clauses, freeText } = parseAdvancedQuery(query, userTags);
  const qualifierCtx = await filterClauses.buildTagContext(ctx.from.id, clauses);
  const pool = filterClauses.applyClauses(repos, clauses, qualifierCtx);

  let results;
  if (freeText) {
    // Multi-field: name is still weighted highest (see searchRanking),
    // but description also participates in the fuzzy pass, so "the repo
    // about parsing CSVs" can surface even with a totally different name.
    const fuse = new Fuse(pool, { keys: [{ name: 'name', weight: 0.8 }, { name: 'description', weight: 0.2 }], threshold: 0.4, includeScore: true });
    const searchRanking = require('../lib/searchRanking');
    results = searchRanking.rank(fuse.search(freeText), freeText);
  } else if (clauses.length > 0) {
    // Qualifiers only, no free text left — just show the filtered set,
    // most-starred first, with no fuzzy score to speak of.
    results = pool
      .slice()
      .sort((a, b) => (b.stargazers_count || 0) - (a.stargazers_count || 0))
      .map((item) => ({ item, score: 0 }));
  } else {
    results = [];
  }

  if (results.length === 0) {
    const hint = clauses.length
      ? `no repos matched those filters`
      : `you have ${repos.length} repos total — check spelling, or try filters like is:private, lang:JavaScript, tag:work, stars:>50`;
    return ctx.reply(
      format.errorMessage(`No repos matched "${query}"`, hint),
      bbtb.searchAgain
    );
  }

  const close = results.filter((r) => r.score <= 0.15).map((r) => r.item);
  const similar = results.filter((r) => r.score > 0.15).map((r) => r.item);

  const sections = [];
  const rows = [];
  let counter = 1;

  if (close.length) {
    const cards = close.map((r) => {
      // #4 — Copy Link alongside Open, informational not navigation, colorless
      rows.push([
        style.callback(`${counter}. ${r.name}`, `repo:${r.name}`, style.BLUE),
        style.callback('📋 Copy Link', `search:copylink:${r.name}`),
      ]);
      const card = `${counter}\\. ` + format.repoCard(r);
      counter++;
      return card;
    });
    sections.push(`🎯 *${freeText ? 'Close Matches' : 'Matches'}*\n\n${cards.join(`\n${format.CARD_DIVIDER}\n`)}`);
  }
  if (similar.length) {
    const cards = similar.map((r) => {
      rows.push([
        style.callback(`${counter}. ${r.name}`, `repo:${r.name}`, style.BLUE),
        style.callback('📋 Copy Link', `search:copylink:${r.name}`),
      ]);
      const card = `${counter}\\. ` + format.repoCard(r);
      counter++;
      return card;
    });
    sections.push(`🔁 *Similar Spelling*\n\n${cards.join(`\n${format.CARD_DIVIDER}\n`)}`);
  }

  const qualifierLabel = clauses.length ? ` · ${filterClauses.describeClauses(clauses)}` : '';
  const queryLabel = freeText ? `"${freeText}"${qualifierLabel}` : qualifierLabel.replace(/^ · /, '');
  const text = `${format.sectionHeader('Search Results', queryLabel)}\n\n${sections.join('\n\n')}\n\n_Type another query to keep searching — no need to tap Search again\\._`;

  await ephemeral.sendEphemeral(ctx, '🔍 Search Results', bbtb.searchAgain);
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

    const starred = await github.isStarred(token, owner, repoName).catch(() => false);

    const text =
      `🔗 *External Repo Detected*\n\n` +
      `📦 ${format.escapeMd(repo.name)}\n` +
      `👤 by ${format.escapeMd(owner)}\n` +
      `${format.visibilityLine(repo.private)} · ${format.languageLine(repo.language)} · ⭐ ${repo.stargazers_count} · 🍴 ${repo.forks_count}\n\n` +
      `📋 Clone:\n\`\`\`\ngit clone ${format.escapeCodeBlock(repo.clone_url)}\n\`\`\``;

    const keyboard = Markup.inlineKeyboard([
      [style.callback('⬇️ Download as ZIP', 'external:download', style.BLUE)],
      [style.callback('🍴 Fork to My Account', 'external:fork', style.BLUE)],
      // Star/Unstar (#6) — a toggle that redraws this same screen, not
      // navigation, so it stays colorless like every other toggle.
      [style.callback(starred ? '⭐ Unstar' : '⭐ Star', 'external:star')],
      [Markup.button.url('🔗 View on GitHub', repo.html_url)],
      [style.callback('⬅️ Cancel', 'external:cancel', style.BLUE)],
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

/** #6 — Star/Unstar toggle. Re-shows the same external-repo screen after,
 * matching how other in-place toggles (Pin, Notifications) behave. */
async function toggleStar(ctx) {
  const { owner, repo } = ctx.session.externalRepo;
  const token = await requireConnected(ctx);
  if (!token) return;

  try {
    const starred = await github.isStarred(token, owner, repo);
    if (starred) await github.unstarRepo(token, owner, repo);
    else await github.starRepo(token, owner, repo);
  } catch (err) {
    await ctx.reply(format.errorMessage('Couldn\u2019t update star', err.message, 'Try again.'));
  }
  return handleExternalRepo(ctx, owner, repo);
}

async function downloadExternalZip(ctx) {
  const { owner, repo } = ctx.session.externalRepo;
  const token = await requireConnected(ctx);
  if (!token) return;

  await ctx.reply(`📦 Preparing zip of ${format.escapeMd(owner)}/${format.escapeMd(repo)}\\.\\.\\.`, { parse_mode: 'MarkdownV2' });
  try {
    const repoData = await github.getRepo(token, owner, repo);
    const buffer = await github.downloadZip(token, owner, repo, repoData.default_branch);

    if (buffer.length > 20 * 1024 * 1024) {
      const fallbackUrl = github.zipDownloadUrl(owner, repo, repoData.default_branch);
      return ctx.reply(format.errorMessage(
        'Download failed',
        `repo is ${format.formatBytes(buffer.length)} — exceeds Telegram's 20MB limit for bot-sent files`,
        `Here's a direct download link instead:\n${fallbackUrl}`
      ));
    }

    await ctx.replyWithDocument({ source: buffer, filename: `${repo}.zip` });
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

/** actionLock-protected — Fork is a destructive action, so it's guarded
 * with double-tap protection like the rest of this file's destructive actions. */
async function executeForkExternal(ctx) {
  const { owner, repo } = ctx.session.externalRepo;
  const token = await requireConnected(ctx);
  if (!token) return;

  const actionLock = require('../lib/actionLock');
  const { skipped } = await actionLock.withLock(ctx.from.id, 'fork', async () => {
    try {
      const forked = await github.forkRepo(token, owner, repo);
      repoCache.invalidateRepos(ctx.from.id);
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
  });
  if (skipped) await ctx.reply('⏳ Already forking — please wait a moment.');
}

/** #4 — Copy Link, sent as its own message so the URL is easy to tap-copy. */
async function copyRepoLink(ctx, repoName) {
  const token = await requireConnected(ctx);
  if (!token) return;
  const user = await repoCache.getUser(ctx.from.id, token);
  const repo = await github.getRepo(token, user.login, repoName);
  await ctx.reply(`🔗 ${repo.html_url}`);
}

module.exports = {
  handleSearchInput,
  handleMyReposSearchInput,
  handlePublicRepoInput,
  handleRepoSearch,
  handleExternalRepo,
  downloadExternalZip,
  forkExternal,
  executeForkExternal,
  toggleStar,
  copyRepoLink,
  parseGithubUrl,
};
