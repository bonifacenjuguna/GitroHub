'use strict';

const { session } = require('grammy');
const redisSessionStorage = require('../../db/redis/sessionStorage');

/**
 * Default shape for a fresh session. Kept intentionally small/flat —
 * only ephemeral navigation and in-progress-flow state lives here.
 * Anything durable (preferences, pins, shortcuts) lives in Postgres.
 */
function initialSession() {
  return {
    activeRepoId: null,       // "owner/name" of the repo currently being browsed
    activeBranch: null,
    activePath: '',           // current folder path when browsing files
    activePR: null,
    pendingAction: null,      // { type, payload } — set when bot is waiting for a text reply
    uploadState: null,        // { targetRepo, targetBranch, targetPath, mode: 'file'|'zip' }
    listState: { sort: 'updated', filter: {}, page: 1 },
  };
}

function sessionMiddleware() {
  return session({
    initial: initialSession,
    storage: redisSessionStorage,
    getSessionKey: (ctx) => (ctx.from ? String(ctx.from.id) : undefined),
  });
}

module.exports = { sessionMiddleware, initialSession };
