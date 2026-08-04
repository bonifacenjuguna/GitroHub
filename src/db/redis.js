const { createClient } = require('redis');
const config = require('../config');

const client = createClient({ url: config.REDIS_URL });

client.on('error', (err) => {
  console.error('⚠️ Redis client error:', err.message);
});

let connected = false;
async function connect() {
  if (!connected) {
    await client.connect();
    connected = true;
    console.log('✅ Redis connected');
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

module.exports = { client, connect, ping };
