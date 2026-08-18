const requireConnected = require('../lib/requireConnected');
const repoCache = require('../lib/repoCache');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');

/**
 * 📊 Stats screen — aggregate view across every repo. Deliberately built
 * entirely from the repo-list payload (repoCache.getRepos), which already
 * carries language, star, and timestamp fields per repo. No per-repo
 * language-breakdown or tree calls here — doing that for every repo on
 * every Stats view would be an N+1 call explosion for anyone with more
 * than a handful of repos, for very little extra insight.
 */
async function showStats(ctx) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const repos = await repoCache.getRepos(ctx.from.id, token);

  if (repos.length === 0) {
    await ctx.reply('📊 Stats', bbtb.myRepos);
    await ctx.reply('📊 *Stats*\n\nYou don\u2019t have any repos yet.', { parse_mode: 'MarkdownV2' });
    return;
  }

  const publicCount = repos.filter((r) => !r.private).length;
  const privateCount = repos.length - publicCount;
  const totalStars = repos.reduce((sum, r) => sum + (r.stargazers_count || 0), 0);

  const langCounts = {};
  for (const r of repos) {
    const lang = r.language || 'None';
    langCounts[lang] = (langCounts[lang] || 0) + 1;
  }
  const topLanguageEntry = Object.entries(langCounts).sort((a, b) => b[1] - a[1])[0];
  const topLanguage = topLanguageEntry ? `${topLanguageEntry[0]} (${topLanguageEntry[1]} repos)` : 'None';

  const mostActive = [...repos].sort((a, b) => new Date(b.pushed_at) - new Date(a.pushed_at))[0];
  const oldest = [...repos].sort((a, b) => new Date(a.created_at) - new Date(b.created_at))[0];

  const text =
    `${format.escapeMd(format.sectionHeader('YOUR STATS', repos.length, 'repos'))}\n\n` +
    `▸ 🌐 Public: ${publicCount}  ·  🔒 Private: ${privateCount}\n` +
    `▸ ⭐ Total stars: ${totalStars}\n` +
    `▸ 💻 Top language: ${format.escapeMd(topLanguage)}\n` +
    `▸ 🔥 Most active: ${format.escapeMd(mostActive.name)} \\(${format.escapeMd(format.relativeTime(mostActive.pushed_at))}\\)\n` +
    `▸ 🕰 Oldest repo: ${format.escapeMd(oldest.name)} \\(${format.escapeMd(format.relativeTime(oldest.created_at))}\\)`;

  await ctx.reply('📊 Stats', bbtb.myRepos);
  await ctx.reply(text, { parse_mode: 'MarkdownV2' });
}

module.exports = { showStats };
