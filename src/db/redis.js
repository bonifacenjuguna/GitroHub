const { createClient } = require('redis');
const config = require('../config');
const logger = require('../lib/logger');

const client = createClient({ url: config.REDIS_URL });

client.on('error', (err) => {
  logger.error('Redis client error', { message: err.message });
});
client.on('reconnecting', () => {
  logger.warn('Redis reconnecting...');
});
client.on('ready', () => {
  logger.info('Redis connection ready');
});

let connected = false;
async function connect() {
  if (!connected) {
    await client.connect();
    connected = true;
    logger.info('Redis connected');
  }
}

/**
 * Ping Redis and return round-trip latency in ms.
 * Used by Settings screen to show live DB health.
 */
async function ping() {
  const start = Date.now();
  try {
    await client.ping();
    return { ok: true, ms: Date.now() - start };
  } catch (err) {
    return { ok: false, ms: null, error: err.message };
  }
}

/** Closes the Redis connection cleanly — used on graceful shutdown (SIGTERM). */
async function close() {
  if (connected) {
    await client.quit();
    connected = false;
  }
}

module.exports = { client, connect, ping, close };
