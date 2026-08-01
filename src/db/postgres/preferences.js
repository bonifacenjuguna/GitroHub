'use strict';

const { query } = require('./pool');

async function getPreferences(telegramUserId) {
  const result = await query('SELECT * FROM user_preferences WHERE telegram_user_id = $1', [telegramUserId]);
  return result.rows[0] || null;
}

async function updatePreference(telegramUserId, field, value) {
  const ALLOWED_FIELDS = [
    'list_view_style', 'diff_style', 'emoji_density', 'date_format',
    'default_repo_visibility', 'default_readme', 'default_gitignore_template', 'default_license',
    'upload_target_mode', 'commit_message_mode', 'notifications_enabled',
    'quiet_hours_start', 'quiet_hours_end', 'quiet_hours_mute_critical',
    'language', 'timezone', 'developer_mode',
  ];
  if (!ALLOWED_FIELDS.includes(field)) {
    throw new Error(`Attempted to update disallowed preference field: ${field}`);
  }
  await query(
    `UPDATE user_preferences SET ${field} = $2, updated_at = now() WHERE telegram_user_id = $1`,
    [telegramUserId, value]
  );
}

async function getPinnedRepos(telegramUserId) {
  const result = await query(
    'SELECT repo_full_name FROM pinned_repos WHERE telegram_user_id = $1 ORDER BY pinned_at DESC',
    [telegramUserId]
  );
  return result.rows.map((r) => r.repo_full_name);
}

async function pinRepo(telegramUserId, repoFullName) {
  const count = await query('SELECT COUNT(*) FROM pinned_repos WHERE telegram_user_id = $1', [telegramUserId]);
  if (Number(count.rows[0].count) >= 5) {
    const err = new Error('Maximum of 5 pinned repos reached');
    err.code = 'PIN_LIMIT';
    throw err;
  }
  await query(
    `INSERT INTO pinned_repos (telegram_user_id, repo_full_name) VALUES ($1, $2)
     ON CONFLICT DO NOTHING`,
    [telegramUserId, repoFullName]
  );
}

async function unpinRepo(telegramUserId, repoFullName) {
  await query('DELETE FROM pinned_repos WHERE telegram_user_id = $1 AND repo_full_name = $2', [
    telegramUserId,
    repoFullName,
  ]);
}

module.exports = { getPreferences, updatePreference, getPinnedRepos, pinRepo, unpinRepo };
