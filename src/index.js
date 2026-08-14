const config = require('./config');
const { migrate } = require('./db/migrate');
const redisDb = require('./db/redis');
const pgDb = require('./db/postgres');
const createBot = require('./bot');
const createApp = require('./server/app');
const logger = require('./lib/logger');

let bot;
let httpServer;
let shuttingDown = false;

/**
 * Closes everything in order (bot polling/webhook, HTTP server, Redis,
 * Postgres) before the process exits. Used for real SIGTERM/SIGINT from
 * Railway, the voluntary memory-watchdog restart, and an uncaught
 * exception — every path ends here so connections close cleanly instead
 * of the process just disappearing mid-write.
 */
async function shutdown(reason) {
  if (shuttingDown) return;
  shuttingDown = true;
  logger.info(`Shutting down`, { reason });

  try {
    if (bot) bot.stop(reason);
  } catch (err) {
    logger.error('Error stopping bot', { message: err.message });
  }
  try {
    if (httpServer) await new Promise((resolve) => httpServer.close(resolve));
  } catch (err) {
    logger.error('Error closing HTTP server', { message: err.message });
  }
  try {
    await redisDb.close();
  } catch (err) {
    logger.error('Error closing Redis', { message: err.message });
  }
  try {
    await pgDb.close();
  } catch (err) {
    logger.error('Error closing Postgres pool', { message: err.message });
  }

  logger.info('Shutdown complete');
  process.exit(0);
}

/**
 * Checks RSS memory every 30s against a self-imposed ceiling comfortably
 * under Railway's hard container limit. If crossed, triggers the SAME
 * clean shutdown path above rather than waiting for the kernel to SIGKILL
 * the process.
 */
function startMemoryWatchdog() {
  setInterval(() => {
    const rssMB = Math.round(process.memoryUsage().rss / 1024 / 1024);
    if (rssMB >= config.MEMORY_WATCHDOG_MB) {
      logger.warn('Memory watchdog threshold crossed — restarting cleanly', { rssMB, ceilingMB: config.MEMORY_WATCHDOG_MB });
      shutdown('memory-watchdog');
    }
  }, config.MEMORY_WATCHDOG_CHECK_INTERVAL_MS).unref();
}

/**
 * Process-level safety net. An uncaught exception leaves Node in an
 * undefined state — best practice is to log it clearly and exit via the
 * same clean shutdown path, rather than either silently crashing (loses
 * the "why") or trying to keep running (risks corrupted state). Unhandled
 * promise rejections are logged but don't trigger a restart on their own —
 * most of these are already recoverable errors caught one level up (e.g.
 * bot.catch), and restarting on every one would be too trigger-happy for
 * what's usually a non-fatal issue.
 */
function installCrashHandlers() {
  process.on('uncaughtException', (err) => {
    logger.error('Uncaught exception — shutting down', { message: err.message, stack: err.stack });
    shutdown('uncaughtException');
  });
  process.on('unhandledRejection', (reason) => {
    logger.error('Unhandled promise rejection', { reason: reason && reason.message ? reason.message : String(reason) });
  });
}

async function main() {
  installCrashHandlers();

  logger.info('Running database migrations...');
  await migrate();

  logger.info('Connecting to Redis...');
  await redisDb.connect();

  logger.info('Starting Telegram bot...');
  bot = createBot();

  await bot.telegram.setMyCommands([
    { command: 'start', description: '🏠 Open main menu, or connect your GitHub account' },
    { command: 'settings', description: '⚙️ View settings and live system status' },
    { command: 'cancel', description: '❌ Cancel whatever you\'re doing and return to the menu' },
  ]);

  logger.info('Starting web server (OAuth callback + health check)...');
  const app = createApp(bot);

  const useWebhook = process.env.NODE_ENV === 'production';

  if (useWebhook) {
    const webhookPath = '/telegram-webhook';
    app.use(bot.webhookCallback(webhookPath, { secretToken: config.TELEGRAM_WEBHOOK_SECRET }));
    httpServer = app.listen(config.PORT, async () => {
      logger.info('Server listening', { port: config.PORT });
      await bot.telegram.setWebhook(`${config.BASE_URL}${webhookPath}`, { secret_token: config.TELEGRAM_WEBHOOK_SECRET });
      logger.info('Telegram webhook set', { url: `${config.BASE_URL}${webhookPath}` });
    });
  } else {
    httpServer = app.listen(config.PORT, () => {
      logger.info('Server listening (OAuth callback + health check)', { port: config.PORT });
    });
    await bot.launch();
    logger.info('Bot running in polling mode (development)');
  }

  startMemoryWatchdog();

  process.once('SIGINT', () => shutdown('SIGINT'));
  process.once('SIGTERM', () => shutdown('SIGTERM'));
}

main().catch((err) => {
  logger.error('Fatal startup error', { message: err.message, stack: err.stack });
  process.exit(1);
});
