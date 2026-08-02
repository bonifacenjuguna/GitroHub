'use strict';

require('dotenv').config();

/**
 * Every variable the bot cannot safely run without.
 * If any of these are missing, the process exits immediately with a
 * specific, actionable error instead of failing weirdly later at runtime.
 */
const REQUIRED_VARS = [
  'BOT_TOKEN',
  'BOT_USERNAME',
  'BOT_OWNER_ID',
  'DOMAIN',
  'WEBHOOK_SECRET',
  'GITHUB_OAUTH_CLIENT_ID',
  'GITHUB_OAUTH_CLIENT_SECRET',
  'ENCRYPTION_MASTER_KEY',
  'DATABASE_URL',
  'REDIS_URL',
];

function validateEnv() {
  const missing = REQUIRED_VARS.filter((key) => !process.env[key] || process.env[key].trim() === '');

  if (missing.length > 0) {
    // eslint-disable-next-line no-console
    console.error('\n❌ GitroHub cannot start — missing required environment variables:\n');
    missing.forEach((key) => console.error(`   • ${key}`));
    console.error('\nCopy .env.example to .env and fill these in, then restart.\n');
    process.exit(1);
  }

  if (!/^\d+$/.test(process.env.BOT_OWNER_ID)) {
    console.error('\n❌ BOT_OWNER_ID must be a numeric Telegram user ID.\n');
    process.exit(1);
  }

  if (process.env.ENCRYPTION_MASTER_KEY.length < 32) {
    console.error('\n❌ ENCRYPTION_MASTER_KEY must be at least 32 characters (use a 32-byte hex string).\n');
    process.exit(1);
  }

  if (!/^https?:\/\//.test(process.env.DOMAIN)) {
    console.error(
      `\n❌ DOMAIN must include the protocol (https://), e.g. "https://your-app.up.railway.app".\n` +
      `   Current value: "${process.env.DOMAIN}"\n\n` +
      `   This isn't just about GitHub OAuth — Telegram itself requires webhook URLs\n` +
      `   to be https://. Without the protocol here, the bot would start but NEVER\n` +
      `   receive any Telegram messages at all (the exact "active but silent" state).\n` +
      `   Refusing to start is the safer failure here.\n\n` +
      `   Fix: set DOMAIN to "https://${process.env.DOMAIN.replace(/\/$/, '')}" in Railway's Variables tab.\n`
    );
    process.exit(1);
  }
}

validateEnv();

module.exports = {
  BOT_TOKEN: process.env.BOT_TOKEN,
  BOT_USERNAME: process.env.BOT_USERNAME,
  BOT_OWNER_ID: Number(process.env.BOT_OWNER_ID),
  BOT_OWNER_USERNAME: process.env.BOT_OWNER_USERNAME || null,
  BOT_OWNER_NAME: process.env.BOT_OWNER_NAME || null,

  DOMAIN: process.env.DOMAIN.replace(/\/$/, ''),
  PORT: Number(process.env.PORT) || 3000,
  WEBHOOK_SECRET: process.env.WEBHOOK_SECRET,

  GITHUB_OAUTH_CLIENT_ID: process.env.GITHUB_OAUTH_CLIENT_ID,
  GITHUB_OAUTH_CLIENT_SECRET: process.env.GITHUB_OAUTH_CLIENT_SECRET,

  ENCRYPTION_MASTER_KEY: process.env.ENCRYPTION_MASTER_KEY,

  DATABASE_URL: process.env.DATABASE_URL,
  REDIS_URL: process.env.REDIS_URL,

  NODE_ENV: process.env.NODE_ENV || 'production',
  LOG_LEVEL: process.env.LOG_LEVEL || 'info',
  IS_PROD: (process.env.NODE_ENV || 'production') === 'production',
};
