require('dotenv').config();

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

  BOT_VERSION: process.env.BOT_VERSION || '0.1.1',

  // Hard limits (from design spec)
  MAX_ZIP_SIZE_BYTES: 1 * 1024 * 1024, // 1MB
  MAX_TELEGRAM_FILE_SIZE_BYTES: 20 * 1024 * 1024, // 20MB (bot send limit)
  REPOS_PER_PAGE: 5,
  FILES_PER_PAGE: 8,
  ACTIVITY_PER_PAGE: 6,
  WIZARD_SESSION_TTL_SECONDS: 30 * 60, // 30 min, per our "stale session" rule
};
