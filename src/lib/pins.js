const { pool } = require('../db/postgres');

async function list(telegramId) {
  const { rows } = await pool.query(
    'SELECT repo_name, position FROM pinned_repos WHERE telegram_id = $1 ORDER BY position ASC',
    [telegramId]
  );
  return rows;
}

async function isPinned(telegramId, repoName) {
  const { rows } = await pool.query(
    'SELECT 1 FROM pinned_repos WHERE telegram_id = $1 AND repo_name = $2',
    [telegramId, repoName]
  );
  return rows.length > 0;
}

async function pin(telegramId, repoName) {
  const { rows } = await pool.query(
    'SELECT COALESCE(MAX(position), -1) + 1 AS next FROM pinned_repos WHERE telegram_id = $1',
    [telegramId]
  );
  await pool.query(
    `INSERT INTO pinned_repos (telegram_id, repo_name, position)
     VALUES ($1, $2, $3)
     ON CONFLICT (telegram_id, repo_name) DO NOTHING`,
    [telegramId, repoName, rows[0].next]
  );
}

async function unpin(telegramId, repoName) {
  await pool.query('DELETE FROM pinned_repos WHERE telegram_id = $1 AND repo_name = $2', [telegramId, repoName]);
}

/** Swaps the position of a pin with its immediate neighbor (up = -1, down = +1) */
async function move(telegramId, repoName, direction) {
  const pins = await list(telegramId);
  const idx = pins.findIndex((p) => p.repo_name === repoName);
  const swapIdx = idx + direction;
  if (idx === -1 || swapIdx < 0 || swapIdx >= pins.length) return; // no-op at either end

  const a = pins[idx];
  const b = pins[swapIdx];
  await pool.query('UPDATE pinned_repos SET position = $1 WHERE telegram_id = $2 AND repo_name = $3', [b.position, telegramId, a.repo_name]);
  await pool.query('UPDATE pinned_repos SET position = $1 WHERE telegram_id = $2 AND repo_name = $3', [a.position, telegramId, b.repo_name]);
}

async function clearAll(telegramId) {
  await pool.query('DELETE FROM pinned_repos WHERE telegram_id = $1', [telegramId]);
}

async function removeByRepoName(telegramId, repoName) {
  await unpin(telegramId, repoName);
}

/**
 * Root fix for "Rename Repo doesn't migrate pins" — Delete Repo already
 * had cleanupOrphanedData() for its equivalent problem; Rename had
 * nothing, so a pinned repo silently vanished from ⭐ Pinned the moment
 * it was renamed (its row was still keyed under the OLD repo_name text,
 * which no longer matches anything GitHub returns).
 *
 * UPDATE, not a plain INSERT/DELETE pair, so the pin's position is kept.
 * The (telegram_id, repo_name) unique constraint means this can only
 * conflict in the practically-impossible case where the NEW name was
 * somehow already separately pinned — in that case just drop the old row
 * and keep whichever pin already existed under the new name.
 */
async function renameRepo(telegramId, oldName, newName) {
  try {
    await pool.query(
      'UPDATE pinned_repos SET repo_name = $1 WHERE telegram_id = $2 AND repo_name = $3',
      [newName, telegramId, oldName]
    );
  } catch (err) {
    if (err.code === '23505') {
      await pool.query('DELETE FROM pinned_repos WHERE telegram_id = $1 AND repo_name = $2', [telegramId, oldName]);
    } else {
      throw err;
    }
  }
}

module.exports = { list, isPinned, pin, unpin, move, clearAll, removeByRepoName, renameRepo };
