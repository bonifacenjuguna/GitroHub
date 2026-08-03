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

  // Safety net: log any unhandled promise rejection instead of letting Node
  // kill the entire process over it. This is what actually crashed the bot
  // in production — a stale/expired Telegram callback query rejected a
  // promise that nothing was awaiting, and Node's default behavior for an
  // unhandled rejection is to terminate the process. The specific case
  // that caused this (ctx.answerCallbackQuery on expired queries) is now
  // fixed at the source in contextExtensions.js, but this handler stays as
  // a second layer so no single unforeseen rejection anywhere else in the
  // codebase can ever take the whole bot down the same way again.
  process.on('unhandledRejection', (reason) => {
    const summary = reason instanceof Error
      ? { message: reason.message, name: reason.name, description: reason.description }
      : { value: String(reason) };
    logger.error({ err: summary }, '⚠️ Unhandled promise rejection — logged and ignored, process kept alive');
  });

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

    // Register the primary user-facing commands with Telegram so they
    // appear in the "/" autocomplete menu. This is a deliberate reversal
    // of the original design (v1.0.0 intentionally left ALL commands
    // hidden from BotFather) — see CHANGELOG.md for why. Diagnostic/dev
    // commands (/ping, /health, /whoami, /version, /uptime, /logs) stay
    // unregistered on purpose: they still work when typed, they just don't
    // clutter the autocomplete list for a bot only you use.
    await bot.api.setMyCommands([
      { command: 'start', description: 'Open the main menu' },
      { command: 'menu', description: 'Jump to the main menu' },
      { command: 'repo', description: 'Open a repo — /repo owner/name' },
      { command: 'upload', description: 'Upload a file or ZIP project' },
      { command: 'security', description: 'Account & Security' },
      { command: 'settings', description: 'Bot settings' },
      { command: 'status', description: 'Quick account & repo summary' },
      { command: 'help', description: 'Help & documentation' },
      { command: 'cancel', description: 'Cancel the current action' },
    ]).catch((err) => logger.warn({ err }, 'Failed to register bot commands with Telegram'));

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
