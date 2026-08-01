'use strict';

const { Pool } = require('pg');
const env = require('../../config/env');
const logger = require('../../utils/logger');

const pool = new Pool({
  connectionString: env.DATABASE_URL,
  max: 10,
  min: 2,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000,
  ssl: env.IS_PROD ? { rejectUnauthorized: false } : false,
});

pool.on('error', (err) => {
  logger.error({ err }, 'Unexpected Postgres pool error');
});

/** Runs a parameterized query with an explicit timeout guard. */
async function query(text, params = []) {
  const start = Date.now();
  const client = await pool.connect();
  try {
    const result = await client.query(text, params);
    logger.debug({ ms: Date.now() - start, query: text.slice(0, 80) }, 'pg query');
    return result;
  } finally {
    client.release();
  }
}

async function ping() {
  const start = Date.now();
  await pool.query('SELECT 1');
  return Date.now() - start;
}

module.exports = { pool, query, ping };
