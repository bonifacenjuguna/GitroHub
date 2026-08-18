const github = require('./github');

/**
 * Short-lived in-process caches, all per-Telegram-user. GitroHub re-fetches
 * the full repo list (and a separate language call per visible repo) on
 * nearly every screen — My Repos, Pinned, Bulk Select, Search all hit this
 * independently, often within seconds of each other for information that
 * hasn't changed. These caches cut that down without needing a "did
 * anything change" check — a 60s TTL is short enough that staleness is
 * never noticeable, and every write path explicitly invalidates anyway.
 */

const REPO_LIST_TTL_MS = 60 * 1000;
const LANGUAGE_TTL_MS = 60 * 1000;
const STATS_TTL_MS = 60 * 1000;
const USERNAME_TTL_MS = 10 * 60 * 1000; // username essentially never changes mid-session

const repoListCache = new Map(); // telegramId -> { repos, timestamp }
const languageCache = new Map(); // `${telegramId}:${repoName}` -> { languages, timestamp }
const statsCache = new Map(); // `${telegramId}:${repoName}` -> { stats, timestamp }
const usernameCache = new Map(); // telegramId -> { user, timestamp }

async function getRepos(telegramId, token) {
  const cached = repoListCache.get(telegramId);
  if (cached && Date.now() - cached.timestamp < REPO_LIST_TTL_MS) {
    return cached.repos;
  }
  const repos = await github.listRepos(token);
  repoListCache.set(telegramId, { repos, timestamp: Date.now() });
  return repos;
}

async function getLanguages(telegramId, owner, repoName, token) {
  const key = `${telegramId}:${repoName}`;
  const cached = languageCache.get(key);
  if (cached && Date.now() - cached.timestamp < LANGUAGE_TTL_MS) {
    return cached.languages;
  }
  const languages = await github.getLanguages(token, owner, repoName);
  languageCache.set(key, { languages, timestamp: Date.now() });
  return languages;
}

/** File count, folder count, and true total size — see github.getRepoStats. */
async function getRepoStats(telegramId, owner, repoName, token) {
  const key = `${telegramId}:${repoName}`;
  const cached = statsCache.get(key);
  if (cached && Date.now() - cached.timestamp < STATS_TTL_MS) {
    return cached.stats;
  }
  const stats = await github.getRepoStats(token, owner, repoName);
  statsCache.set(key, { stats, timestamp: Date.now() });
  return stats;
}

async function getUser(telegramId, token) {
  const cached = usernameCache.get(telegramId);
  if (cached && Date.now() - cached.timestamp < USERNAME_TTL_MS) {
    return cached.user;
  }
  const user = await github.getAuthenticatedUser(token);
  usernameCache.set(telegramId, { user, timestamp: Date.now() });
  return user;
}

/** Call after ANY write (create/delete/rename/upload/visibility/bulk actions)
 * so the next read reflects reality instead of serving stale cached data. */
function invalidateRepos(telegramId) {
  repoListCache.delete(telegramId);
}

/** Languages and file-tree stats change together (both derived from repo
 * content), so every call site that invalidates one invalidates both here —
 * no need to touch every caller separately. */
function invalidateLanguages(telegramId, repoName) {
  languageCache.delete(`${telegramId}:${repoName}`);
  statsCache.delete(`${telegramId}:${repoName}`);
}

/** Called on disconnect — the cached username would otherwise be wrong for whoever connects next. */
function invalidateUser(telegramId) {
  usernameCache.delete(telegramId);
  repoListCache.delete(telegramId);
  for (const key of languageCache.keys()) {
    if (key.startsWith(`${telegramId}:`)) languageCache.delete(key);
  }
  for (const key of statsCache.keys()) {
    if (key.startsWith(`${telegramId}:`)) statsCache.delete(key);
  }
}

module.exports = { getRepos, getLanguages, getRepoStats, getUser, invalidateRepos, invalidateLanguages, invalidateUser };
