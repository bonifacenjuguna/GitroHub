const { pool } = require('../db/postgres');

/**
 * 📤 Scheduled Uploads — commits/uploads a file to an EXISTING repo at a
 * future time, as opposed to 🆕 Scheduled Repos (which creates a new one).
 * The file itself is held as a Telegram file_id and re-downloaded at
 * execution time — same proven approach as 🗑️ Trash's backup snapshots,
 * not a new assumption about Telegram's file storage being introduced
 * here.
 */
async function create(telegramId, { repoName, targetPath, commitMessage, fileId, fileName, isArchive, archiveAction, scheduledFor }) {
  const { rows } = await pool.query(
    `INSERT INTO scheduled_uploads (telegram_id, repo_name, target_path, commit_message, file_id, file_name, is_archive, archive_action, scheduled_for)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) RETURNING *`,
    [telegramId, repoName, targetPath || null, commitMessage || null, fileId, fileName, !!isArchive, archiveAction || null, scheduledFor]
  );
  return rows[0];
}

async function listPending(telegramId) {
  const { rows } = await pool.query(
    `SELECT * FROM scheduled_uploads WHERE telegram_id = $1 AND status = 'pending' ORDER BY scheduled_for ASC`,
    [telegramId]
  );
  return rows;
}

async function get(telegramId, id) {
  const { rows } = await pool.query(
    `SELECT * FROM scheduled_uploads WHERE telegram_id = $1 AND id = $2`,
    [telegramId, id]
  );
  return rows[0] || null;
}

async function cancel(telegramId, id) {
  await pool.query(
    `UPDATE scheduled_uploads SET status = 'cancelled' WHERE telegram_id = $1 AND id = $2 AND status = 'pending'`,
    [telegramId, id]
  );
}

/** Edits one field of a still-pending scheduled upload — the "✏️ Edit"
 * flow in handlers/scheduledUploads.js. Whitelisted column map (not raw
 * string interpolation of the field name), same reasoning as
 * scheduledRepos.js's own updateField. */
const EDITABLE_FIELDS = {
  targetPath: 'target_path', commitMessage: 'commit_message', scheduledFor: 'scheduled_for',
};
async function updateField(telegramId, id, field, value) {
  const col = EDITABLE_FIELDS[field];
  if (!col) throw new Error(`Unknown scheduled_uploads field: ${field}`);
  await pool.query(
    `UPDATE scheduled_uploads SET ${col} = $1 WHERE telegram_id = $2 AND id = $3 AND status = 'pending'`,
    [value, telegramId, id]
  );
}

/** Everything due right now, across every user — polled every minute by
 * index.js, same cadence as Scheduled Repos for the same reason (a
 * schedule implies real timing precision). */
async function getDue() {
  const { rows } = await pool.query(`SELECT * FROM scheduled_uploads WHERE status = 'pending' AND scheduled_for <= now()`);
  return rows;
}

async function markCompleted(id) {
  await pool.query(`UPDATE scheduled_uploads SET status = 'completed' WHERE id = $1`, [id]);
}

async function markFailed(id, errorMessage) {
  await pool.query(`UPDATE scheduled_uploads SET status = 'failed', error_message = $2 WHERE id = $1`, [id, errorMessage]);
}

module.exports = { create, listPending, get, cancel, updateField, getDue, markCompleted, markFailed };
