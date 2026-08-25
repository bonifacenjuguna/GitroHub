const { client } = require('../db/redis');
const config = require('../config');

/**
 * Telegraf-compatible session store backed by Redis.
 * Used with telegraf's session() middleware so Scenes/Wizard state
 * (Create Repo, Upload, Rename, Edit File flows) survives a Railway
 * restart/redeploy instead of silently losing the user's progress.
 *
 * This runs on literally every single interaction (every tap, every
 * message), so it's the one piece of I/O that — if it ever stalled
 * without a timeout — could freeze the whole bot. Postgres and every
 * GitHub call already got hard timeouts; this was the missing piece.
 * Fails fast and loud (throws, doesn't silently swallow) so a stall here
 * surfaces as a clear error via bot.catch() instead of infinite silence.
 */
const SESSION_IO_TIMEOUT_MS = 5000;

/** Races `promise` against a hard timeout, and — unlike the version this
 * replaced — actually clears the timer once either side settles. The old
 * version left every timeout's setTimeout running for its full duration
 * regardless of whether the real operation finished first, on literally
 * every single Telegram update (see the docstring above: this runs on
 * every tap). That's a timer leak on the hottest path in the whole bot. */
function withTimeout(promise, label) {
  let timer;
  const timeoutPromise = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(`${label} timed out after ${SESSION_IO_TIMEOUT_MS}ms`)), SESSION_IO_TIMEOUT_MS);
  });
  return Promise.race([promise, timeoutPromise]).finally(() => clearTimeout(timer));
}

const redisStore = {
  async get(key) {
    const raw = await withTimeout(client.get(`tg-session:${key}`), 'Session read');
    if (!raw) return undefined;
    try {
      return JSON.parse(raw);
    } catch (err) {
      // A single malformed value here previously threw on every future
      // read for this chat too — session middleware runs on every
      // interaction, so one bad write effectively bricked the bot for
      // that user until someone manually cleared Redis. Treat it as "no
      // session" instead: the person loses whatever wizard state they
      // were mid-flow on, which is recoverable (they just restart that
      // flow), instead of every subsequent tap failing forever.
      return undefined;
    }
  },
  async set(key, value) {
    await withTimeout(
      client.set(`tg-session:${key}`, JSON.stringify(value), { EX: config.SESSION_TTL_SECONDS }),
      'Session write'
    );
  },
  async delete(key) {
    await withTimeout(client.del(`tg-session:${key}`), 'Session delete');
  },
};

module.exports = redisStore;
