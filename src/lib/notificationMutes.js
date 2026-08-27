const { pool } = require('../db/postgres');

async function isMuted(telegramId, repoName) {
  const { rows } = await pool.query(
    'SELECT 1 FROM notification_mutes WHERE telegram_id = $1 AND repo_name = $2',
    [telegramId, repoName]
  );
  return rows.length > 0;
}

async function mute(telegramId, repoName) {
  await pool.query(
    `INSERT INTO notification_mutes (telegram_id, repo_name, muted_at)
     VALUES ($1, $2, now()) ON CONFLICT (telegram_id, repo_name) DO NOTHING`,
    [telegramId, repoName]
  );
}

async function unmute(telegramId, repoName) {
  await pool.query('DELETE FROM notification_mutes WHERE telegram_id = $1 AND repo_name = $2', [telegramId, repoName]);
}

module.exports = { isMuted, mute, unmute };
