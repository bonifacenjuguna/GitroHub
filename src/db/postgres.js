const { Pool } = require('pg');
const config = require('../config');

const pool = new Pool({
  connectionString: config.DATABASE_URL,
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

module.exports = { pool, ping };
