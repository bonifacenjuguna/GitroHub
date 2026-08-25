const { pool } = require('../db/postgres');
const logger = require('./logger');

/**
 * Records one line into the Activity Log (Settings -> 📜 Activity).
 * icon    e.g. '⬆️', '➕', '🗑', '⚠️', '🔒', '🍴'
 * summary e.g. "Uploaded 4 files → weather-app"
 * detail  optional longer text (full error message, stack, etc.)
 * isError marks it so it also shows under "⚠️ Errors Only" filter
 *
 * Deliberately never throws. This is called from inside nearly every
 * handler's `catch` block, to log the very failure that's already being
 * handled — a transient Postgres blip AT THAT MOMENT previously escaped
 * the surrounding catch entirely (since nothing there was awaiting-and-
 * catching this call), becoming an unhandled rejection instead of the
 * person just seeing the error message the code was already about to
 * send them. Logging a problem should never itself be able to crash the
 * response to it.
 */
async function log(telegramId, icon, summary, { detail = null, isError = false } = {}) {
  try {
    await pool.query(
      `INSERT INTO activity_log (telegram_id, icon, summary, detail, is_error)
       VALUES ($1, $2, $3, $4, $5)`,
      [telegramId, icon, summary, detail, isError]
    );
  } catch (err) {
    logger.error('Failed to write activity log entry (non-fatal)', { telegramId, summary, message: err.message });
  }
}

async function recent(telegramId, { limit = 6, offset = 0, errorsOnly = false } = {}) {
  const where = errorsOnly ? 'AND is_error = TRUE' : '';
  const { rows } = await pool.query(
    `SELECT * FROM activity_log
     WHERE telegram_id = $1 ${where}
     ORDER BY created_at DESC
     LIMIT $2 OFFSET $3`,
    [telegramId, limit, offset]
  );
  const { rows: countRows } = await pool.query(
    `SELECT COUNT(*)::int AS total FROM activity_log WHERE telegram_id = $1 ${where}`,
    [telegramId]
  );
  return { rows, total: countRows[0].total };
}

module.exports = { log, recent };
