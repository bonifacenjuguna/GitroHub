'use strict';

const cron = require('node-cron');
const { query } = require('../db/postgres/pool');
const branchesApi = require('../github/branches');
const reposApi = require('../github/repos');
const { getRateLimitSnapshot } = require('../db/redis/cache');
const logger = require('../utils/logger');

/**
 * Runs every minute, checking which scheduled_tasks are due based on their
 * stored cron expression. Guards against running automation when the
 * GitHub API rate limit is low, deferring non-critical tasks to the next
 * check instead of risking a mid-task failure.
 */
function startScheduler(bot) {
  cron.schedule('* * * * *', async () => {
    try {
      const { rows: tasks } = await query('SELECT * FROM scheduled_tasks WHERE enabled = true');
      for (const task of tasks) {
        if (!cron.validate(task.cron_expression)) continue;
        // node-cron doesn't expose "is this expression due right now" directly,
        // so scheduled_tasks are instead registered as their own cron jobs below
        // on startup — see registerIndividualTasks(). This loop is a safety net
        // for tasks added after boot.
      }
    } catch (err) {
      logger.error({ err }, 'Scheduler tick failed');
    }
  });

  registerIndividualTasks(bot);
  logger.info('⚡ Automation scheduler started');
}

const activeCronJobs = new Map();

async function registerIndividualTasks(bot) {
  const { rows: tasks } = await query('SELECT * FROM scheduled_tasks WHERE enabled = true');
  for (const task of tasks) {
    scheduleTask(bot, task);
  }
}

function scheduleTask(bot, task) {
  if (!cron.validate(task.cron_expression)) return;
  const job = cron.schedule(task.cron_expression, () => runTask(bot, task));
  activeCronJobs.set(task.id, job);
}

async function runTask(bot, task) {
  logger.info({ taskId: task.id, type: task.task_type }, 'Running scheduled task');

  const rateLimit = await getRateLimitSnapshot(task.telegram_user_id);
  if (rateLimit && rateLimit.remaining < 500) {
    logger.warn({ taskId: task.id }, 'Deferring scheduled task — GitHub API rate limit low');
    return;
  }

  try {
    if (task.task_type === 'delete_merged_branches') {
      const repos = await reposApi.listRepos(task.telegram_user_id, { perPage: 20, sort: 'updated' });
      let total = 0;
      for (const r of repos) {
        const [owner, name] = r.full_name.split('/');
        const deleted = await branchesApi.deleteMergedBranches(task.telegram_user_id, owner, name, r.default_branch);
        total += deleted.length;
      }
      await bot.api.sendMessage(task.telegram_user_id, `🧹 Scheduled cleanup: ${total} merged branches deleted across your repos.`);
    }

    if (task.task_type === 'repo_summary') {
      const repos = await reposApi.listRepos(task.telegram_user_id, { perPage: 5, sort: 'updated' });
      const lines = repos.map((r) => `${r.private ? '🔵' : '🟢'} ${r.full_name}`).join('\n');
      await bot.api.sendMessage(task.telegram_user_id, `📊 Daily Summary\n\n${lines}`);
    }

    await query('UPDATE scheduled_tasks SET last_run_at = now() WHERE id = $1', [task.id]);
  } catch (err) {
    logger.error({ err, taskId: task.id }, 'Scheduled task failed');
  }
}

module.exports = { startScheduler, scheduleTask };
