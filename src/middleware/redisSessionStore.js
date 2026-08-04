const { client } = require('../db/redis');
const config = require('../config');

/**
 * Telegraf-compatible session store backed by Redis.
 * Used with telegraf's session() middleware so Scenes/Wizard state
 * (Create Repo, Upload, Rename, Edit File flows) survives a Railway
 * restart/redeploy instead of silently losing the user's progress.
 */
const redisStore = {
  async get(key) {
    const raw = await client.get(`tg-session:${key}`);
    return raw ? JSON.parse(raw) : undefined;
  },
  async set(key, value) {
    await client.set(`tg-session:${key}`, JSON.stringify(value), {
      EX: config.WIZARD_SESSION_TTL_SECONDS,
    });
  },
  async delete(key) {
    await client.del(`tg-session:${key}`);
  },
};

module.exports = redisStore;
