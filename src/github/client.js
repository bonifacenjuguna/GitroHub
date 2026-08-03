'use strict';

const { Octokit } = require('octokit');
const { getDecryptedToken } = require('../db/postgres/users');
const { setRateLimitSnapshot } = require('../db/redis/cache');
const logger = require('../utils/logger');

/**
 * Short-lived in-memory client cache, keyed by telegramUserId.
 *
 * Without this, every single GitHub API call anywhere in the bot — even
 * ones fired concurrently via Promise.all on a single screen — was doing
 * its own fresh Postgres query PLUS its own fresh scrypt-based AES-256-GCM
 * decryption before it could even reach GitHub. scrypt is deliberately
 * CPU-expensive by design (that's what makes it secure against brute
 * force), so redoing it 6+ times concurrently for a single screen like
 * Repo Detail was real, compounding overhead — the actual cause of
 * responses feeling slow and arriving "all at once" after a delay.
 *
 * The cache holds the constructed Octokit instance (which itself holds
 * the already-decrypted token in memory) for a short TTL, so a burst of
 * calls for the same user within that window reuses one decrypt + one DB
 * read instead of paying that cost per call. Invalidated eagerly on
 * disconnect/reconnect so a revoked token can never be used past its
 * validity window.
 */
const CLIENT_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const clientCache = new Map(); // telegramUserId -> { octokit, expiresAt }

async function getClient(telegramUserId) {
  const cached = clientCache.get(telegramUserId);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.octokit;
  }

  const token = await getDecryptedToken(telegramUserId);

  const octokit = new Octokit({
    auth: token,
    userAgent: 'GitroHub/1.0.0',
    request: { timeout: 10000 },
  });

  octokit.hook.after('request', async (response) => {
    const remaining = response.headers['x-ratelimit-remaining'];
    const limit = response.headers['x-ratelimit-limit'];
    const reset = response.headers['x-ratelimit-reset'];
    if (remaining !== undefined) {
      await setRateLimitSnapshot(telegramUserId, {
        remaining: Number(remaining),
        limit: Number(limit),
        resetsAt: Number(reset) * 1000,
      }).catch((err) => logger.warn({ err }, 'Failed to cache rate limit snapshot'));
    }
  });

  clientCache.set(telegramUserId, { octokit, expiresAt: Date.now() + CLIENT_CACHE_TTL_MS });
  return octokit;
}

/** Call this on disconnect/reconnect so a stale client can never outlive its token's validity. */
function invalidateClientCache(telegramUserId) {
  clientCache.delete(telegramUserId);
}

module.exports = { getClient, invalidateClientCache };
