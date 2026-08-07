-- GitroHub database schema
-- Run automatically on boot by src/db/migrate.js (safe to re-run, uses IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS users (
  telegram_id         BIGINT PRIMARY KEY,
  github_username     TEXT,
  github_token_enc    TEXT,          -- AES-256-GCM encrypted access token
  github_scope        TEXT,
  connected_at        TIMESTAMPTZ,
  disconnected_at     TIMESTAMPTZ,

  -- Notification preferences (per design: Settings -> Notifications submenu)
  notif_github_activity BOOLEAN NOT NULL DEFAULT TRUE,
  notif_system_alerts   BOOLEAN NOT NULL DEFAULT TRUE,
  notif_long_ops        BOOLEAN NOT NULL DEFAULT TRUE,
  notif_token_health     BOOLEAN NOT NULL DEFAULT TRUE,

  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS activity_log (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  icon          TEXT NOT NULL,        -- e.g. '⬆️', '➕', '⚠️'
  summary       TEXT NOT NULL,        -- e.g. "Uploaded 4 files → weather-app"
  detail        TEXT,                 -- optional expanded detail / error stack
  is_error      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activity_log_telegram_id_created
  ON activity_log (telegram_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_log_errors
  ON activity_log (telegram_id, is_error, created_at DESC);

-- Tracks one-off maintenance migrations (e.g. clearing corrupted encrypted
-- data) so they only ever run a single time, no matter how many times the
-- app restarts.
CREATE TABLE IF NOT EXISTS schema_migrations (
  id           TEXT PRIMARY KEY,
  applied_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
