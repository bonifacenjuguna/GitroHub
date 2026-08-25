const { pool } = require('../db/postgres');
const { encrypt, decrypt } = require('./crypto');

async function getUser(telegramId) {
  const { rows } = await pool.query('SELECT * FROM users WHERE telegram_id = $1', [telegramId]);
  return rows[0] || null;
}

async function isConnected(telegramId) {
  const user = await getUser(telegramId);
  return !!(user && user.github_token_enc && !user.disconnected_at);
}

async function getDecryptedToken(telegramId) {
  const user = await getUser(telegramId);
  if (!user || !user.github_token_enc) return null;
  return decrypt(user.github_token_enc);
}

/** Called by the OAuth /callback route once the token exchange succeeds */
async function saveConnection(telegramId, { accessToken, scope, githubUsername }) {
  const encToken = encrypt(accessToken);
  await pool.query(
    `INSERT INTO users (telegram_id, github_username, github_token_enc, github_scope, connected_at, disconnected_at)
     VALUES ($1, $2, $3, $4, now(), NULL)
     ON CONFLICT (telegram_id) DO UPDATE
       SET github_username = $2,
           github_token_enc = $3,
           github_scope = $4,
           connected_at = now(),
           disconnected_at = NULL`,
    [telegramId, githubUsername, encToken, scope]
  );
}

async function disconnect(telegramId) {
  await pool.query(
    `UPDATE users SET github_token_enc = NULL, disconnected_at = now() WHERE telegram_id = $1`,
    [telegramId]
  );
}

async function getNotificationPrefs(telegramId) {
  const user = await getUser(telegramId);
  if (!user) return null;
  return {
    githubActivity: user.notif_github_activity,
    systemAlerts: user.notif_system_alerts,
    longOps: user.notif_long_ops,
    tokenHealth: user.notif_token_health,
  };
}

async function toggleNotification(telegramId, key) {
  const columnMap = {
    githubActivity: 'notif_github_activity',
    systemAlerts: 'notif_system_alerts',
    longOps: 'notif_long_ops',
    tokenHealth: 'notif_token_health',
  };
  const column = columnMap[key];
  if (!column) throw new Error(`Unknown notification key: ${key}`);
  await pool.query(
    `UPDATE users SET ${column} = NOT ${column} WHERE telegram_id = $1`,
    [telegramId]
  );
  const user = await getUser(telegramId);
  return user[column];
}

/**
 * These three were previously raw `require('../db/postgres')` + `pool.query`
 * calls made directly inside handlers/storageData.js and
 * handlers/accessLogScreen.js — a direct violation of the README's stated
 * architecture rule ("lib/ = data access, handlers/ = screen logic") that
 * every other handler in the codebase actually follows. Moved here so
 * handlers stay declarative and DB access stays in exactly one layer.
 */
async function setActivityRetentionDays(telegramId, days) {
  await pool.query('UPDATE users SET activity_retention_days = $1 WHERE telegram_id = $2', [Number(days), telegramId]);
}

async function toggleAutoCleanupOnDelete(telegramId) {
  const user = await getUser(telegramId);
  const next = !(user && user.auto_cleanup_on_delete);
  await pool.query('UPDATE users SET auto_cleanup_on_delete = $1 WHERE telegram_id = $2', [next, telegramId]);
  return next;
}

async function toggleAlertOnNewConnection(telegramId) {
  const user = await getUser(telegramId);
  const next = !(user && user.alert_on_new_connection);
  await pool.query('UPDATE users SET alert_on_new_connection = $1 WHERE telegram_id = $2', [next, telegramId]);
  return next;
}

module.exports = {
  getUser,
  isConnected,
  getDecryptedToken,
  saveConnection,
  disconnect,
  getNotificationPrefs,
  toggleNotification,
  setActivityRetentionDays,
  toggleAutoCleanupOnDelete,
  toggleAlertOnNewConnection,
};
