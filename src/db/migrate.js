const fs = require('fs');
const path = require('path');
const { pool } = require('./postgres');

// One-off maintenance migration IDs. Each is recorded in `schema_migrations`
// once applied, so it only ever runs a single time across restarts.
const MAINTENANCE_MIGRATIONS = [
  {
    id: '2024_clear_corrupted_github_tokens',
    description:
      'Clears github_token_enc values encrypted with an old TOKEN_ENCRYPTION_KEY ' +
      'that can no longer be decrypted, which was crashing the bot on startup.',
    run: async () => {
      await pool.query('UPDATE users SET github_token_enc = NULL;');
    },
  },
];

async function runMaintenanceMigrations() {
  for (const migration of MAINTENANCE_MIGRATIONS) {
    try {
      const { rows } = await pool.query(
        'SELECT 1 FROM schema_migrations WHERE id = $1',
        [migration.id]
      );
      if (rows.length > 0) {
        continue; // already applied
      }

      console.log(`🔧 Running one-off migration: ${migration.id}`);
      await migration.run();
      await pool.query(
        'INSERT INTO schema_migrations (id) VALUES ($1) ON CONFLICT (id) DO NOTHING',
        [migration.id]
      );
      console.log(`✅ Applied one-off migration: ${migration.id}`);
    } catch (err) {
      // Never crash the app because of a maintenance migration failure.
      console.error(`⚠️ One-off migration "${migration.id}" failed:`, err.message);
    }
  }
}

async function migrate() {
  const sql = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf8');
  await pool.query(sql);
  console.log('✅ Database schema is up to date');

  await runMaintenanceMigrations();
}

if (require.main === module) {
  migrate()
    .then(() => process.exit(0))
    .catch((err) => {
      console.error('❌ Migration failed:', err);
      process.exit(1);
    });
}

module.exports = { migrate };
