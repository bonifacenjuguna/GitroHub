'use strict';

const { Octokit } = require('octokit');
const { getDecryptedToken } = require('../db/postgres/users');
const { setRateLimitSnapshot } = require('../db/redis/cache');
const logger = require('../utils/logger');

/**
 * Builds an authenticated Octokit instance for the given Telegram user,
 * and wires a response hook that captures GitHub's rate-limit headers
 * on every call, storing them in Redis for fast display elsewhere
 * (Settings, /status, /health) without needing a dedicated API call.
 */
async function getClient(telegramUserId) {
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

  return octokit;
}

module.exports = { getClient };
