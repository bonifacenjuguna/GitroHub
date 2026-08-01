'use strict';

const { query } = require('./pool');
const logger = require('../../utils/logger');

/**
 * Records a security/audit-relevant action. Called for destructive or
 * sensitive actions: delete, visibility change, merge, disconnect,
 * permission changes, force-push, PIN changes, etc.
 */
async function logAction(telegramUserId, actionType, repoFullName = null, details = {}) {
  try {
    await query(
      `INSERT INTO activity_log (telegram_user_id, action_type, repo_full_name, details)
       VALUES ($1, $2, $3, $4)`,
      [telegramUserId, actionType, repoFullName, JSON.stringify(details)]
    );
  } catch (err) {
    // Logging must never crash the primary action it's describing.
    logger.error({ err, actionType }, 'Failed to write activity log entry');
  }
}

async function getRecentActivity(telegramUserId, { limit = 5, offset = 0, actionType = null } = {}) {
  const params = [telegramUserId, limit, offset];
  let filter = '';
  if (actionType) {
    filter = 'AND action_type = $4';
    params.push(actionType);
  }
  const result = await query(
    `SELECT * FROM activity_log
     WHERE telegram_user_id = $1 ${filter}
     ORDER BY created_at DESC
     LIMIT $2 OFFSET $3`,
    params
  );
  return result.rows;
}

module.exports = { logAction, getRecentActivity };
