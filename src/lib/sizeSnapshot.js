const { pool } = require('../db/postgres');

/** Returns the previous snapshot's total bytes and when it was taken, or
 * null if this is the first time Stats has ever computed a total. */
async function getPrevious(telegramId) {
  const { rows } = await pool.query(
    'SELECT total_bytes, snapshotted_at FROM size_snapshots WHERE telegram_id = $1',
    [telegramId]
  );
  return rows[0] || null;
}

/** Overwrites the stored snapshot with the current total. Only one row per
 * user is ever kept — this isn't a history, just "what was it last time
 * Stats was viewed", enough to show a single trend delta. */
async function save(telegramId, totalBytes) {
  await pool.query(
    `INSERT INTO size_snapshots (telegram_id, total_bytes, snapshotted_at)
     VALUES ($1, $2, now())
     ON CONFLICT (telegram_id) DO UPDATE SET total_bytes = $2, snapshotted_at = now()`,
    [telegramId, totalBytes]
  );
}

module.exports = { getPrevious, save };
