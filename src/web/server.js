'use strict';

const express = require('express');
const path = require('path');
const { webhookCallback } = require('grammy');
const env = require('../config/env');
const logger = require('../utils/logger');
const { consumeOAuthState, exchangeCodeForToken, fetchGithubIdentity } = require('../security/oauth');
const { saveGithubConnection } = require('../db/postgres/users');
const { logAction } = require('../db/postgres/activityLog');
const { ping: pgPing } = require('../db/postgres/pool');
const { ping: redisPing } = require('../db/redis/client');

function createServer(bot) {
  const app = express();
  app.use(express.json());

  // --- Telegram webhook ---
  app.post(
    '/telegram/webhook',
    webhookCallback(bot, 'express', { secretToken: env.WEBHOOK_SECRET })
  );

  // --- GitHub OAuth callback (the animated page) ---
  app.get('/oauth/github/callback', async (req, res) => {
    const { code, state, error } = req.query;

    if (error) {
      return res.status(400).sendFile(path.join(__dirname, 'public', 'callback-error.html'));
    }

    try {
      const telegramUserId = await consumeOAuthState(state);
      const { accessToken, scopes } = await exchangeCodeForToken(code);
      const identity = await fetchGithubIdentity(accessToken);

      await saveGithubConnection(telegramUserId, {
        githubUsername: identity.login,
        githubUserId: identity.id,
        accessToken,
        scopes,
      });
      await logAction(telegramUserId, 'connect_github');

      // Notify the user proactively in their chat, since the callback happens
      // in a browser tab, not inside the Telegram conversation itself.
      await bot.api.sendMessage(
        telegramUserId,
        `✅ GitHub Connected\n\nWelcome, @${identity.login}! You're all set.`
      ).catch((err) => logger.warn({ err }, 'Failed to send post-OAuth confirmation message'));

      res.send(renderCallbackHtml({ status: 'success', username: identity.login, botUsername: env.BOT_USERNAME }));
    } catch (err) {
      logger.error({ err }, 'OAuth callback failed');
      res.status(400).send(renderCallbackHtml({ status: 'error', message: err.message, botUsername: env.BOT_USERNAME }));
    }
  });

  // --- Health check (for Railway + external monitors) ---
  app.get('/health', async (req, res) => {
    const [pgMs, redisMs] = await Promise.all([
      pgPing().catch(() => null),
      redisPing().catch(() => null),
    ]);
    const healthy = pgMs !== null && redisMs !== null;
    res.status(healthy ? 200 : 503).json({
      status: healthy ? 'ok' : 'degraded',
      postgres: pgMs !== null ? `${pgMs}ms` : 'unreachable',
      redis: redisMs !== null ? `${redisMs}ms` : 'unreachable',
    });
  });

  // --- Legal pages (Terms, Privacy, Acceptable Use — served from /docs) ---
  app.get('/legal/:doc', (req, res) => {
    const allowed = ['terms', 'privacy', 'acceptable-use'];
    if (!allowed.includes(req.params.doc)) return res.status(404).send('Not found');
    res.sendFile(path.join(__dirname, '..', '..', 'docs', 'legal', `${req.params.doc}.html`), (err) => {
      if (err) res.status(404).send('Document not yet generated — see /docs in the project source.');
    });
  });

  app.get('/', (req, res) => {
    res.send('GitroHub is running. This is a private bot instance.');
  });

  return app;
}

/** Renders the animated OAuth callback page inline (kept in this file so it has access to dynamic state). */
function renderCallbackHtml({ status, username, message, botUsername }) {
  const fs = require('fs');
  const template = fs.readFileSync(path.join(__dirname, 'public', 'callback.html'), 'utf8');
  return template
    .replace('__STATUS__', status)
    .replace('__USERNAME__', username || '')
    .replace('__MESSAGE__', message || '')
    .replace('__BOT_USERNAME__', botUsername);
}

module.exports = { createServer };
