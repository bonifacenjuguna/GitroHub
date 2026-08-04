const github = require('../lib/github');
const requireConnected = require('../lib/requireConnected');
const format = require('../lib/format');
const inline = require('../keyboards/inline');
const bbtb = require('../keyboards/bbtb');
const config = require('../config');

// Simple in-memory view-state per user (filter/sort/page) — not sensitive,
// fine to keep in process memory; resets on restart which is harmless here.
const viewState = new Map();

function getState(telegramId) {
  if (!viewState.has(telegramId)) {
    viewState.set(telegramId, { filter: 'all', sort: 'updated', page: 1 });
  }
  return viewState.get(telegramId);
}

function applyFilterSort(repos, state) {
  let filtered = repos;
  if (state.filter === 'public') filtered = repos.filter((r) => !r.private);
  if (state.filter === 'private') filtered = repos.filter((r) => r.private);
  if (state.filter === 'forks') filtered = repos.filter((r) => r.fork);

  const sorted = [...filtered];
  if (state.sort === 'updated') sorted.sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
  if (state.sort === 'name') sorted.sort((a, b) => a.name.localeCompare(b.name));
  if (state.sort === 'stars') sorted.sort((a, b) => b.stargazers_count - a.stargazers_count);
  if (state.sort === 'created') sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  return sorted;
}

const FILTER_LABELS = { all: 'All', public: '🌐 Public', private: '🔒 Private', forks: '🍴 Forks' };
const SORT_LABELS = { updated: 'Recently Updated', name: 'Name (A-Z)', stars: 'Most Stars', created: 'Recently Created' };

function renderRepoLine(r) {
  return `📦 *${format.escapeMd(r.name)}*\n   ${format.visibilityLine(r.private)} · ${format.languageLine(r.language)} · ⭐ ${r.stargazers_count}`;
}

async function showMyRepos(ctx, { edit = false } = {}) {
  const token = await requireConnected(ctx);
  if (!token) return;

  const telegramId = ctx.from.id;
  const state = getState(telegramId);

  const allRepos = await github.listRepos(token);
  const filtered = applyFilterSort(allRepos, state);

  const perPage = config.REPOS_PER_PAGE;
  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  state.page = Math.min(state.page, totalPages);
  const pageRepos = filtered.slice((state.page - 1) * perPage, state.page * perPage);

  let text = `📁 *Your Repositories* \\(${allRepos.length} total\\)\n`;
  text += `Filter: ${format.escapeMd(FILTER_LABELS[state.filter])}   Sort: ${format.escapeMd(SORT_LABELS[state.sort])}\n\n`;

  if (pageRepos.length === 0) {
    text += format.escapeMd(`No repos match filter "${FILTER_LABELS[state.filter]}".`);
  } else {
    text += pageRepos.map(renderRepoLine).join('\n\n');
    text += `\n\nPage ${state.page} of ${totalPages}`;
  }

  const keyboard = inline.repoList(pageRepos, state.page, totalPages);

  if (edit) {
    await ctx.editMessageText(text, { parse_mode: 'MarkdownV2', ...keyboard });
  } else {
    await ctx.reply(text, { parse_mode: 'MarkdownV2', ...keyboard, ...bbtb.myRepos });
  }
}

async function showFilterMenu(ctx) {
  await ctx.editMessageText('🔎 *Filter repositories by:*', {
    parse_mode: 'MarkdownV2',
    ...inline.filterMenu,
  });
}

async function showSortMenu(ctx) {
  await ctx.editMessageText('↕️ *Sort repositories by:*', {
    parse_mode: 'MarkdownV2',
    ...inline.sortMenu,
  });
}

function setFilter(telegramId, filter) {
  const state = getState(telegramId);
  state.filter = filter;
  state.page = 1;
}

function setSort(telegramId, sort) {
  const state = getState(telegramId);
  state.sort = sort;
  state.page = 1;
}

function setPage(telegramId, page) {
  getState(telegramId).page = page;
}

module.exports = { showMyRepos, showFilterMenu, showSortMenu, setFilter, setSort, setPage, getState };
