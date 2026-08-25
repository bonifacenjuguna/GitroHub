const { pool } = require('../db/postgres');

async function getLastPath(telegramId, repoName) {
  const { rows } = await pool.query(
    'SELECT last_path FROM repo_path_memory WHERE telegram_id = $1 AND repo_name = $2',
    [telegramId, repoName]
  );
  return rows[0] ? rows[0].last_path : null;
}

async function setLastPath(telegramId, repoName, path) {
  await pool.query(
    `INSERT INTO repo_path_memory (telegram_id, repo_name, last_path, updated_at)
     VALUES ($1, $2, $3, now())
     ON CONFLICT (telegram_id, repo_name) DO UPDATE SET last_path = $3, updated_at = now()`,
    [telegramId, repoName, path]
  );
}

async function removeForRepo(telegramId, repoName) {
  await pool.query('DELETE FROM repo_path_memory WHERE telegram_id = $1 AND repo_name = $2', [telegramId, repoName]);
}

/**
 * Root fix for "Rename Repo doesn't migrate path memory" — same gap as
 * pins/tags (see lib/pins.js renameRepo). If the new name already has
 * its own remembered path (the practically-impossible case of the new
 * name having been used before), keep that one and drop the old row
 * rather than erroring.
 */
async function renameRepo(telegramId, oldName, newName) {
  try {
    await pool.query(
      'UPDATE repo_path_memory SET repo_name = $1 WHERE telegram_id = $2 AND repo_name = $3',
      [newName, telegramId, oldName]
    );
  } catch (err) {
    if (err.code === '23505') {
      await pool.query('DELETE FROM repo_path_memory WHERE telegram_id = $1 AND repo_name = $2', [telegramId, oldName]);
    } else {
      throw err;
    }
  }
}

module.exports = { getLastPath, setLastPath, removeForRepo, renameRepo };
