'use strict';

const { query } = require('../db/postgres/pool');
const { generateStateToken } = require('./encryption');
const env = require('../config/env');
const logger = require('../utils/logger');

const OAUTH_SCOPES = ['repo', 'workflow', 'admin:org', 'user', 'delete_repo'];
const STATE_TTL_MINUTES = 5;

/** Creates a single-use, expiring state token bound to this Telegram user, for CSRF protection. */
async function createOAuthState(telegramUserId) {
  const state = generateStateToken();
  await query(
    `INSERT INTO oauth_states (state, telegram_user_id, expires_at)
     VALUES ($1, $2, now() + interval '${STATE_TTL_MINUTES} minutes')`,
    [state, telegramUserId]
  );
  return state;
}

function buildAuthorizationUrl(state) {
  const params = new URLSearchParams({
    client_id: env.GITHUB_OAUTH_CLIENT_ID,
    redirect_uri: `${env.DOMAIN}/oauth/github/callback`,
    scope: OAUTH_SCOPES.join(' '),
    state,
    allow_signup: 'false',
  });
  return `https://github.com/login/oauth/authorize?${params.toString()}`;
}

/** Validates a state token exists, is unexpired, and returns + deletes it (single-use). */
async function consumeOAuthState(state) {
  const result = await query(
    'DELETE FROM oauth_states WHERE state = $1 AND expires_at > now() RETURNING telegram_user_id',
    [state]
  );
  if (result.rows.length === 0) {
    const err = new Error('Invalid or expired OAuth state');
    err.code = 'INVALID_STATE';
    throw err;
  }
  return result.rows[0].telegram_user_id;
}

/** Exchanges an OAuth authorization code for an access token. */
async function exchangeCodeForToken(code) {
  const response = await fetch('https://github.com/login/oauth/access_token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({
      client_id: env.GITHUB_OAUTH_CLIENT_ID,
      client_secret: env.GITHUB_OAUTH_CLIENT_SECRET,
      code,
      redirect_uri: `${env.DOMAIN}/oauth/github/callback`,
    }),
  });

  const data = await response.json();
  if (data.error) {
    logger.error({ error: data.error, description: data.error_description }, 'GitHub OAuth token exchange failed');
    const err = new Error(data.error_description || data.error);
    err.code = 'OAUTH_EXCHANGE_FAILED';
    throw err;
  }
  return { accessToken: data.access_token, scopes: data.scope };
}

/** Fetches the GitHub identity of the token owner, to store username/id alongside the encrypted token. */
async function fetchGithubIdentity(accessToken) {
  const response = await fetch('https://api.github.com/user', {
    headers: { Authorization: `Bearer ${accessToken}`, 'User-Agent': 'GitroHub/1.0.0' },
  });
  return response.json();
}

/** Revokes the OAuth app's grant on GitHub's side — a true revocation, not just a local delete. */
async function revokeToken(accessToken) {
  const auth = Buffer.from(`${env.GITHUB_OAUTH_CLIENT_ID}:${env.GITHUB_OAUTH_CLIENT_SECRET}`).toString('base64');
  await fetch(`https://api.github.com/applications/${env.GITHUB_OAUTH_CLIENT_ID}/grant`, {
    method: 'DELETE',
    headers: {
      Authorization: `Basic ${auth}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ access_token: accessToken }),
  }).catch((err) => logger.warn({ err }, 'Failed to revoke token on GitHub side (local deletion still proceeds)'));
}

module.exports = {
  OAUTH_SCOPES, createOAuthState, buildAuthorizationUrl, consumeOAuthState,
  exchangeCodeForToken, fetchGithubIdentity, revokeToken,
};
