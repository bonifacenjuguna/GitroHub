const { pool } = require('../db/postgres');

/**
 * 🗑️ Trash — see db/schema.sql's trashed_repos table for the storage
 * approach (the zip snapshot lives as a Telegram document in the person's
 * own chat; this table just tracks its file_id plus enough metadata to
 * restore or display it).
 */
async function add(telegramId, { originalName, description, visibility, backupFileId, retentionDays }) {
  const { rows } = await pool.query(
    `INSERT INTO trashed_repos (telegram_id, original_name, description, visibility, backup_file_id, expires_at)
     VALUES ($1, $2, $3, $4, $5, now() + ($6 || ' days')::interval)
     RETURNING *`,
    [telegramId, originalName, description || null, visibility, backupFileId, retentionDays]
  );
  return rows[0];
}

/** Everything still recoverable — not yet restored, not yet expired. */
async function list(telegramId) {
  const { rows } = await pool.query(
    `SELECT * FROM trashed_repos
     WHERE telegram_id = $1 AND restored_at IS NULL AND expires_at > now()
     ORDER BY deleted_at DESC`,
    [telegramId]
  );
  return rows;
}

async function get(telegramId, id) {
  const { rows } = await pool.query(
    `SELECT * FROM trashed_repos WHERE telegram_id = $1 AND id = $2`,
    [telegramId, id]
  );
  return rows[0] || null;
}

async function markRestored(telegramId, id) {
  await pool.query(
    `UPDATE trashed_repos SET restored_at = now() WHERE telegram_id = $1 AND id = $2`,
    [telegramId, id]
  );
}

/** Edits a trash entry's own record before it's restored — used by
 * "✏️ Edit & Restore" so the collision check and eventual GitHub creation
 * both see the updated values (see handlers/trash.js's requestRestore,
 * which re-fetches the entry fresh every time). */
const EDITABLE_FIELDS = { originalName: 'original_name', description: 'description', visibility: 'visibility' };
async function update(telegramId, id, field, value) {
  const col = EDITABLE_FIELDS[field];
  if (!col) throw new Error(`Unknown trashed_repos field: ${field}`);
  await pool.query(
    `UPDATE trashed_repos SET ${col} = $1 WHERE telegram_id = $2 AND id = $3 AND restored_at IS NULL`,
    [value, telegramId, id]
  );
}

/** Permanently removes a trash entry — "🗑️ Delete Forever", for when
 * someone wants it gone right now instead of waiting for expiry. The
 * backup document itself isn't (and can't be) deleted from the person's
 * own Telegram chat history from here — this just removes the bot's
 * record of it, matching what expiry already does under the hood. */
async function remove(telegramId, id) {
  const { rowCount } = await pool.query(
    `DELETE FROM trashed_repos WHERE telegram_id = $1 AND id = $2 AND restored_at IS NULL`,
    [telegramId, id]
  );
  return rowCount > 0;
}

/** Called daily by the automation scheduler — expired rows just get
 * dropped from the table. There's no separate cleanup needed on the
 * Telegram side; an unreferenced file_id simply stops being useful once
 * nothing in the bot points at it anymore. */
async function pruneExpired() {
  const { rowCount } = await pool.query(
    `DELETE FROM trashed_repos WHERE expires_at <= now() AND restored_at IS NULL`
  );
  return rowCount;
}

module.exports = { add, list, get, markRestored, update, remove, pruneExpired };
