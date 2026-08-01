'use strict';

const env = require('./config/env');
const logger = require('./utils/logger');
const { createBot } = require('./bot/bot');
const { createServer } = require('./web/server');
const { startScheduler } = require('./automation/scheduler');
const { pool } = require('./db/postgres/pool');
const { redis } = require('./db/redis/client');

async function main() {
  logger.info('🐙 Starting GitroHub...');

  // Fail fast if the database schema hasn't been migrated yet.
  try {
    await pool.query('SELECT 1 FROM users LIMIT 1');
  } catch (err) {
    logger.error(
      { err },
      '❌ Database not migrated. Run "npm run migrate" before starting the bot.'
    );
    process.exit(1);
  }

  const bot = createBot();
  await bot.init(); // fetches bot info (username, id) before setting the webhook

  const app = createServer(bot);
  const server = app.listen(env.PORT, () => {
    logger.info(`🌐 Web server listening on port ${env.PORT}`);
  });

  const webhookUrl = `${env.DOMAIN}/telegram/webhook`;
  await bot.api.setWebhook(webhookUrl, { secret_token: env.WEBHOOK_SECRET });
  logger.info(`✅ Telegram webhook set: ${webhookUrl}`);

  startScheduler(bot);

  logger.info(`✅ GitroHub is live as @${bot.botInfo.username}, owner-only mode (BOT_OWNER_ID=${env.BOT_OWNER_ID})`);

  // --- Graceful shutdown ---
  const shutdown = async (signal) => {
    logger.info(`Received ${signal}, shutting down gracefully...`);
    server.close();
    await pool.end();
    redis.disconnect();
    process.exit(0);
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((err) => {
  logger.error({ err }, '❌ Fatal error during startup');
  process.exit(1);
});
