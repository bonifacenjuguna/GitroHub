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
  const app = createServer(bot);

  // Start listening FIRST, before touching the Telegram API. Railway's
  // healthcheck hits /health as soon as the process is up — if we block
  // on bot.init() (a network call to Telegram) before binding the port,
  // a slow or briefly-unreachable Telegram API can cause Railway to see
  // the deploy as unhealthy and send SIGTERM before we ever get a chance
  // to respond. Binding the port first guarantees /health answers
  // immediately regardless of Telegram's reachability.
  const server = app.listen(env.PORT, () => {
    logger.info(`🌐 Web server listening on port ${env.PORT}`);
  });

  // --- Graceful shutdown (registered early so a slow init below can still shut down cleanly) ---
  const shutdown = async (signal) => {
    logger.info(`Received ${signal}, shutting down gracefully...`);
    server.close();
    await pool.end();
    redis.disconnect();
    process.exit(0);
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));

  try {
    await bot.init(); // fetches bot info (username, id) from Telegram

    const webhookUrl = `${env.DOMAIN}/telegram/webhook`;
    await bot.api.setWebhook(webhookUrl, { secret_token: env.WEBHOOK_SECRET });
    logger.info(`✅ Telegram webhook set: ${webhookUrl}`);

    // Self-check: confirm Telegram actually accepted the webhook URL we
    // think we set. If DOMAIN doesn't match Railway's real public URL,
    // this will show the mismatch clearly in logs instead of the bot
    // just silently never receiving updates.
    const info = await bot.api.getWebhookInfo();
    if (info.url !== webhookUrl) {
      logger.warn(
        { expected: webhookUrl, actual: info.url },
        '⚠️ Webhook URL mismatch — DOMAIN env var likely does not match your real public URL'
      );
    }
    if (info.last_error_message) {
      logger.warn({ lastError: info.last_error_message }, '⚠️ Telegram reported a previous webhook delivery error');
    }

    startScheduler(bot);
    logger.info(`✅ GitroHub is live as @${bot.botInfo.username}, owner-only mode (BOT_OWNER_ID=${env.BOT_OWNER_ID})`);
  } catch (err) {
    // Do NOT exit here — the web server (and /health) stays up so Railway
    // doesn't kill the whole deploy. But this is loud and specific about
    // what failed, since "active but not responding" with no error is the
    // worst failure mode to debug.
    logger.error({ err }, '❌ Telegram bot failed to initialize — web server is still running, but the bot will NOT respond until this is fixed and the service is redeployed.');
  }
}

main().catch((err) => {
  logger.error({ err }, '❌ Fatal error during startup');
  process.exit(1);
});
