'use strict';

const fs = require('fs');
const path = require('path');
const { pool } = require('./pool');
const logger = require('../../utils/logger');

async function migrate() {
  const schemaPath = path.join(__dirname, 'schema.sql');
  const sql = fs.readFileSync(schemaPath, 'utf8');

  logger.info('Running Postgres migration...');
  await pool.query(sql);
  logger.info('✅ Migration complete — all tables ensured.');
  await pool.end();
  process.exit(0);
}

migrate().catch((err) => {
  logger.error({ err }, '❌ Migration failed');
  process.exit(1);
});
