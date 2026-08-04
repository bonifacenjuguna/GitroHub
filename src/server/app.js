const express = require('express');
const fs = require('fs');
const path = require('path');
const config = require('../config');
const oauth = require('../lib/oauth');
const github = require('../lib/github');
const users = require('../lib/users');
const activity = require('../lib/activity');

const PAGE_TEMPLATE = fs.readFileSync(path.join(__dirname, '..', '..', 'public', 'callback.html'), 'utf8');

const SUCCESS_STEPS = [
  'Verifying request',
  'Exchanging authorization code',
  'Encrypting access token',
  'Saving to secure storage',
  'Linking Telegram session',
];

function renderPage(data) {
  const inject = `<script>window.__GITROHUB__ = ${JSON.stringify(data)};</script>`;
  return PAGE_TEMPLATE.replace('</head>', `${inject}</head>`);
}

function createApp(bot) {
  const app = express();
  app.use('/logo.png', express.static(path.join(__dirname, '..', '..', 'public', 'logo.png')));

  app.get('/', (req, res) => {
    res.send('GitroHub is running. This endpoint has nothing to show you directly — open the bot on Telegram.');
  });

  app.get('/callback', async (req, res) => {
    const { code, state, error: oauthError } = req.query;
    const botDeepLink = 'https://t.me/GitroHubBot';

    // GitHub itself reported denial/cancellation
    if (oauthError) {
      return res.send(renderPage({
        status: 'error',
        steps: ['Verifying request'],
        failStepIndex: 0,
        error: 'Authorization cancelled: you didn\u2019t approve access on GitHub, or closed the page before finishing.',
        botDeepLink,
      }));
    }

    let telegramId;
    try {
      telegramId = oauth.verifyState(state);
    } catch (err) {
      return res.send(renderPage({
        status: 'error',
        steps: ['Verifying request'],
        failStepIndex: 0,
        error: 'The authorization link was invalid or expired. This can happen if you waited too long or reused an old link.',
        botDeepLink,
      }));
    }

    try {
      const tokenData = await oauth.exchangeCodeForToken(code);
      const ghUser = await github.getAuthenticatedUser(tokenData.access_token);

      await users.saveConnection(telegramId, {
        accessToken: tokenData.access_token,
        scope: tokenData.scope,
        githubUsername: ghUser.login,
      });

      await activity.log(telegramId, '🔗', `Connected GitHub account (@${ghUser.login})`, {});

      // Proactively push the confirmation into the chat (per design: bot pushes
      // this automatically, no need for the user to tap anything back in Telegram)
      const { successMessage, escapeMd } = require('../lib/format');
      const bbtb = require('../keyboards/bbtb');
      await bot.telegram.sendMessage(
        telegramId,
        `✅ *GitHub Connected*\nLinked as: ${escapeMd(ghUser.login)}\nScope: repo \\(full control of repos\\)`,
        { parse_mode: 'MarkdownV2', reply_markup: bbtb.mainMenu.reply_markup }
      );

      return res.send(renderPage({
        status: 'success',
        steps: SUCCESS_STEPS,
        username: ghUser.login,
        botDeepLink,
      }));
    } catch (err) {
      console.error('OAuth callback error:', err.message);
      await activity.log(telegramId, '⚠️', 'GitHub connection failed', { detail: err.message, isError: true }).catch(() => {});

      return res.send(renderPage({
        status: 'error',
        steps: SUCCESS_STEPS.slice(0, 2),
        failStepIndex: 1,
        error: `Couldn\u2019t complete the token exchange with GitHub: ${err.message}. This is usually temporary.`,
        botDeepLink,
      }));
    }
  });

  return app;
}

module.exports = createApp;
