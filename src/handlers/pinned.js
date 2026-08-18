const { Markup } = require('telegraf');
const github = require('../lib/github');
const repoCache = require('../lib/repoCache');
const pins = require('../lib/pins');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const bbtb = require('../keyboards/bbtb');
const myRepos = require('./myRepos');
const tags = require('../lib/tags');

async function showPinned(ctx) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const telegramId = ctx.from.id;
  const pinList = await pins.list(telegramId);

  if (pinList.length === 0) {
    await ctx.reply('⭐ Pinned', bbtb.pinned);
    await ctx.reply(
      '📌 Pinned Repos\n\nYou haven\u2019t pinned any repos yet.\nOpen any repo and tap 📌 Pin below to add it here.'
    );
    return;
  }

  const allRepos = await repoCache.getRepos(ctx.from.id, token);
  const repoByName = new Map(allRepos.map((r) => [r.name, r]));
  const tagMap = await tags.tagsForRepos(telegramId, pinList.map((p) => p.repo_name));

  const rows = [];
  const lines = [];

  for (let i = 0; i < pinList.length; i++) {
    const repo = repoByName.get(pinList[i].repo_name);
    if (!repo) continue; // repo may have been deleted/renamed since pinning

    const line = await myRepos.renderRepoLine(telegramId, token, repo, {
      pinned: true,
      repoTags: tagMap[repo.name] || [],
    });
    lines.push(line);

    const arrowRow = [];
    if (i > 0) arrowRow.push(Markup.button.callback('⬆️', `pin:up:${repo.name}`));
    if (i < pinList.length - 1) arrowRow.push(Markup.button.callback('⬇️', `pin:down:${repo.name}`));
    arrowRow.push(Markup.button.callback(`Open ${repo.name}`, `repo:${repo.name}`));
    rows.push(arrowRow);
  }

  const text = `${format.escapeMd(format.sectionHeader('PINNED', lines.length))}\n\n` + lines.join('\n──────────────────\n');

  await ctx.reply('⭐ Pinned', bbtb.pinned);
  await ctx.reply(text, { parse_mode: 'MarkdownV2', ...Markup.inlineKeyboard(rows) });
}

async function movePin(ctx, repoName, direction) {
  await pins.move(ctx.from.id, repoName, direction === 'up' ? -1 : 1);
  return showPinned(ctx);
}

module.exports = { showPinned, movePin };
