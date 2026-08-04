const config = require('./config');
const { migrate } = require('./db/migrate');
const redisDb = require('./db/redis');
const createBot = require('./bot');
const createApp = require('./server/app');

async function main() {
  console.log('🔧 Running database migrations...');
  await migrate();

  console.log('🔧 Connecting to Redis...');
  await redisDb.connect();

  console.log('🔧 Starting Telegram bot...');
  const bot = createBot();

  // Register command shortcuts (shown when typing "/" in Telegram) without
  // needing to register them manually in BotFather.
  await bot.telegram.setMyCommands([
    { command: 'start', description: '🏠 Open main menu, or connect your GitHub account' },
    { command: 'settings', description: '⚙️ View settings and live system status' },
    { command: 'cancel', description: '❌ Cancel whatever you\'re doing and return to the menu' },
  ]);

  console.log('🔧 Starting web server (OAuth callback)...');
  const app = createApp(bot);

  const useWebhook = process.env.NODE_ENV === 'production';

  if (useWebhook) {
    const webhookPath = '/telegram-webhook';
    app.use(bot.webhookCallback(webhookPath));
    app.listen(config.PORT, async () => {
      console.log(`✅ Server listening on port ${config.PORT}`);
      await bot.telegram.setWebhook(`${config.BASE_URL}${webhookPath}`);
      console.log(`✅ Telegram webhook set to ${config.BASE_URL}${webhookPath}`);
    });
  } else {
    app.listen(config.PORT, () => {
      console.log(`✅ Server listening on port ${config.PORT} (OAuth callback only)`);
    });
    await bot.launch();
    console.log('✅ Bot running in polling mode (development)');
  }

  process.once('SIGINT', () => bot.stop('SIGINT'));
  process.once('SIGTERM', () => bot.stop('SIGTERM'));
}

main().catch((err) => {
  console.error('❌ Fatal startup error:', err);
  process.exit(1);
});
