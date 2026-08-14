require('dotenv').config();
const crypto = require('crypto');

function required(name) {
  const val = process.env[name];
  if (!val) {
    console.error(`❌ Missing required environment variable: ${name}`);
    console.error('   Check your .env file against .env.example');
    process.exit(1);
  }
  return val;
}

module.exports = {
  BOT_TOKEN: required('BOT_TOKEN'),
  OWNER_ID: Number(required('OWNER_ID')),

  GITHUB_CLIENT_ID: required('GITHUB_CLIENT_ID'),
  GITHUB_CLIENT_SECRET: required('GITHUB_CLIENT_SECRET'),

  BASE_URL: required('BASE_URL').replace(/\/$/, ''),
  PORT: Number(process.env.PORT || 3000),

  SESSION_JWT_SECRET: required('SESSION_JWT_SECRET'),
  TOKEN_ENCRYPTION_KEY: required('TOKEN_ENCRYPTION_KEY'),

  DATABASE_URL: required('DATABASE_URL'),
  REDIS_URL: required('REDIS_URL'),

  BOT_VERSION: process.env.BOT_VERSION || '0.7.2',

  // Hard limits (from design spec)
  MAX_ZIP_SIZE_BYTES: 1 * 1024 * 1024, // 1MB
  MAX_ZIP_UNCOMPRESSED_BYTES: 15 * 1024 * 1024, // 15MB decompressed — zip bomb guard
  MAX_SINGLE_FILE_BYTES: 5 * 1024 * 1024, // 5MB — single-file uploads (not zips) were previously uncapped
  MAX_TELEGRAM_FILE_SIZE_BYTES: 20 * 1024 * 1024, // 20MB (bot send limit)
  REPOS_PER_PAGE: 5,
  FILES_PER_PAGE: 8,
  ACTIVITY_PER_PAGE: 6,
  WIZARD_SESSION_TTL_SECONDS: 30 * 60, // 30 min, per our "stale session" rule

  // Memory management — tuned for Railway's 512MB free-tier ceiling.
  // See README "Memory & stability" section for the full explanation.
  PG_POOL_MAX: Number(process.env.PG_POOL_MAX || 3),
  MEMORY_WATCHDOG_MB: Number(process.env.MEMORY_WATCHDOG_MB || 400),
  MEMORY_WATCHDOG_CHECK_INTERVAL_MS: 30 * 1000,

  // Verifies incoming webhook requests actually came from Telegram. Falls
  // back to a value derived from SESSION_JWT_SECRET if not explicitly set,
  // so the bot still works without extra setup — but a dedicated secret
  // (openssl rand -hex 24) is strongly recommended for a public URL.
  TELEGRAM_WEBHOOK_SECRET: process.env.TELEGRAM_WEBHOOK_SECRET ||
    crypto.createHash('sha256').update(process.env.SESSION_JWT_SECRET || 'fallback').digest('hex').slice(0, 32),
};
