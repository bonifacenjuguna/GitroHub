'use strict';

const { InlineKeyboard } = require('grammy');
const repos = require('../../github/repos');
const { getPinnedRepos, pinRepo, unpinRepo } = require('../../db/postgres/preferences');
const { formatError } = require('../../utils/errors');
const { relativeTime, formatBytes } = require('../../utils/format');

const STATUS_DOT = { public: '🟢', private: '🔵', archived: '⚫' };
const PAGE_SIZE = 5;

function repoStatusDot(repo) {
  if (repo.archived) return STATUS_DOT.archived;
  return repo.private ? STATUS_DOT.private : STATUS_DOT.public;
}

async function renderRepoList(ctx, { page = 1, sort = 'updated' } = {}) {
  try {
    const [allRepos, pinned] = await Promise.all([
      repos.listRepos(ctx.from.id, { page, perPage: PAGE_SIZE, sort }),
      getPinnedRepos(ctx.from.id),
    ]);

    ctx.session.listState = { sort, page };

    let body = `📦 Repositories\n\n`;
    if (allRepos.length === 0) {
      body += 'No repositories found on this page.';
    } else {
      for (const r of allRepos) {
        body += `${repoStatusDot(r)} ${r.full_name}${pinned.includes(r.full_name) ? ' 📌' : ''}\n`;
        body += `   ⭐ ${r.stargazers_count} · 🍴 ${r.forks_count} · updated ${relativeTime(r.updated_at)}\n\n`;
      }
    }
    body += `Page ${page} · Sort: ${sortLabel(sort)}`;

    const kb = new InlineKeyboard();
    allRepos.forEach((r, i) => kb.text(String(i + 1), `repo:open:${encodeURIComponent(r.full_name)}`));
    kb.row();
    kb.text('◀️', `repos:page:${Math.max(1, page - 1)}:${sort}`)
      .text(`Page ${page}`, 'noop')
      .text('▶️', `repos:page:${page + 1}:${sort}`).row();
    kb.text('↕️ Sort', 'repos:sort:menu').text('📌 Pins', 'repos:pins:menu').row();
    kb.text('➕ New', 'repo:create:start').text('📥 Import', 'repo:import:start').text('🔎 Search', 'search:repos:start').row();
    kb.text('⬅️ Back to Menu', 'menu:main');

    await ctx.editOrReply(body, { reply_markup: kb });
  } catch (err) {
    const formatted = formatError(err, { retryCallback: 'menu:repos', backCallback: 'menu:main' });
    const kb = new InlineKeyboard();
    formatted.buttons.forEach((row) => {
      kb.row();
      row.forEach((btn) => kb.text(btn.text, btn.data));
    });
    await ctx.editOrReply(formatted.text, { reply_markup: kb });
  }
}

function sortLabel(sort) {
  return { updated: 'Recently Updated', created: 'Recently Created', name_asc: 'Name (A–Z)', name_desc: 'Name (Z–A)' }[sort] || sort;
}

async function renderSortMenu(ctx) {
  const current = ctx.session.listState?.sort || 'updated';
  const options = [
    ['updated', 'Recently Updated'], ['created', 'Recently Created'],
    ['name_asc', 'Name (A–Z)'], ['name_desc', 'Name (Z–A)'],
  ];
  const kb = new InlineKeyboard();
  options.forEach(([value, label]) => {
    kb.text(`${current === value ? '✅ ' : ''}${label}`, `repos:sort:apply:${value}`).row();
  });
  kb.text('⬅️ Back to Repositories', 'menu:repos');
  await ctx.editOrReply(`↕️ Sort Repositories By\n\nCurrently: ${sortLabel(current)}`, { reply_markup: kb });
}

async function renderPinsMenu(ctx) {
  const pinned = await getPinnedRepos(ctx.from.id);
  const kb = new InlineKeyboard();
  pinned.forEach((name) => kb.text(`📌 ${name}`, 'noop').text('✖️ Unpin', `repos:unpin:${encodeURIComponent(name)}`).row());
  kb.text('➕ Pin a repo...', 'repos:pins:select').row();
  kb.text('⬅️ Back to Repositories', 'menu:repos');
  await ctx.editOrReply(`📌 Pinned Repositories (${pinned.length}/5)\n\nPinned repos always show at the top. Max 5 pins.`, { reply_markup: kb });
}

function registerRepositoriesMenu(bot) {
  bot.callbackQuery('menu:repos', async (ctx) => {
    await renderRepoList(ctx, { page: 1, sort: ctx.session.listState?.sort || 'updated' });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repos:page:(\d+):(.+)$/, async (ctx) => {
    const page = Number(ctx.match[1]);
    const sort = ctx.match[2];
    await renderRepoList(ctx, { page, sort });
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery('repos:sort:menu', async (ctx) => {
    await renderSortMenu(ctx);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repos:sort:apply:(.+)$/, async (ctx) => {
    await renderRepoList(ctx, { page: 1, sort: ctx.match[1] });
    await ctx.answerCallbackQuery('Sort applied');
  });

  bot.callbackQuery('repos:pins:menu', async (ctx) => {
    await renderPinsMenu(ctx);
    await ctx.answerCallbackQuery();
  });

  bot.callbackQuery(/^repos:unpin:(.+)$/, async (ctx) => {
    await unpinRepo(ctx.from.id, decodeURIComponent(ctx.match[1]));
    await renderPinsMenu(ctx);
    await ctx.answerCallbackQuery('Unpinned');
  });

  bot.callbackQuery('noop', async (ctx) => ctx.answerCallbackQuery());
}

module.exports = { registerRepositoriesMenu, renderRepoList, repoStatusDot };
