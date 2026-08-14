const { Pool } = require('pg');
const config = require('../config');

// Default pool size is up to 10 idle connections — far more than a
// single-owner bot ever needs, and each idle connection holds its own
// buffers in memory. Capped low to keep the baseline footprint small on
// Railway's 512MB free-tier limit.
const pool = new Pool({
  connectionString: config.DATABASE_URL,
  max: config.PG_POOL_MAX,
  idleTimeoutMillis: 30000,
  ssl: config.DATABASE_URL.includes('railway') || process.env.NODE_ENV === 'production'
    ? { rejectUnauthorized: false }
    : false,
});

pool.on('error', (err) => {
  console.error('⚠️ Unexpected Postgres pool error:', err.message);
});

/**
 * Ping the database and return round-trip latency in ms.
 * Used by Settings screen to show live DB health.
 */
async function ping() {
  const start = Date.now();
  try {
    await pool.query('SELECT 1');
    return { ok: true, ms: Date.now() - start };
  } catch (err) {
    return { ok: false, ms: null, error: err.message };
  }
}

/** Closes all pool connections cleanly — used on graceful shutdown (SIGTERM). */
async function close() {
  await pool.end();
}

module.exports = { pool, ping, close };
