'use strict';

const { query } = require('./pool');
const { encrypt, decrypt } = require('../../security/encryption');

/** Ensures a row exists for this Telegram user, updating identity fields on every call. */
async function upsertTelegramUser(ctxFrom) {
  const { id, username, first_name, last_name } = ctxFrom;
  const result = await query(
    `INSERT INTO users (telegram_user_id, telegram_username, telegram_first_name, telegram_last_name)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (telegram_user_id)
     DO UPDATE SET telegram_username = $2, telegram_first_name = $3, telegram_last_name = $4, updated_at = now()
     RETURNING *`,
    [id, username || null, first_name || null, last_name || null]
  );

  // Ensure preferences row exists too (default values apply via schema defaults)
  await query(
    `INSERT INTO user_preferences (telegram_user_id) VALUES ($1)
     ON CONFLICT (telegram_user_id) DO NOTHING`,
    [id]
  );

  return result.rows[0];
}

async function getUser(telegramUserId) {
  const result = await query('SELECT * FROM users WHERE telegram_user_id = $1', [telegramUserId]);
  return result.rows[0] || null;
}

async function isConnected(telegramUserId) {
  const user = await getUser(telegramUserId);
  return Boolean(user && user.encrypted_token);
}

/** Stores the GitHub OAuth token, encrypted at rest with AES-256-GCM. */
async function saveGithubConnection(telegramUserId, { githubUsername, githubUserId, accessToken, scopes }) {
  const encryptedToken = encrypt(accessToken);
  await query(
    `UPDATE users
     SET github_username = $2, github_user_id = $3, encrypted_token = $4,
         token_scopes = $5, connected_at = now(), updated_at = now()
     WHERE telegram_user_id = $1`,
    [telegramUserId, githubUsername, githubUserId, encryptedToken, scopes]
  );
}

/** Returns the decrypted GitHub token for making API calls. Throws if not connected. */
async function getDecryptedToken(telegramUserId) {
  const user = await getUser(telegramUserId);
  if (!user || !user.encrypted_token) {
    const err = new Error('GitHub account not connected');
    err.code = 'NOT_CONNECTED';
    throw err;
  }
  return decrypt(user.encrypted_token);
}

async function disconnectGithub(telegramUserId) {
  await query(
    `UPDATE users
     SET encrypted_token = NULL, token_scopes = NULL, connected_at = NULL, updated_at = now()
     WHERE telegram_user_id = $1`,
    [telegramUserId]
  );
}

async function setPin(telegramUserId, pinHash) {
  await query('UPDATE users SET pin_hash = $2, updated_at = now() WHERE telegram_user_id = $1', [
    telegramUserId,
    pinHash,
  ]);
}

async function clearPin(telegramUserId) {
  await setPin(telegramUserId, null);
}

module.exports = {
  upsertTelegramUser,
  getUser,
  isConnected,
  saveGithubConnection,
  getDecryptedToken,
  disconnectGithub,
  setPin,
  clearPin,
};
