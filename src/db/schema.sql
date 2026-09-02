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

-- ── My Defaults, Storage & Access ───────────────────────────────

-- My Defaults, Storage & Data auto-cleanup, Access Log alerts
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_visibility TEXT NOT NULL DEFAULT 'private';
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_commit_message TEXT NOT NULL DEFAULT 'Update via GitroHub';
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_upload_path TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_sort TEXT NOT NULL DEFAULT 'updated';
ALTER TABLE users ADD COLUMN IF NOT EXISTS default_filter TEXT NOT NULL DEFAULT 'all';
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_suggest_defaults BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS activity_retention_days INT NOT NULL DEFAULT 90;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_cleanup_on_delete BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS alert_on_new_connection BOOLEAN NOT NULL DEFAULT TRUE;

-- Pinned repos, with a manual order for the reorder feature
CREATE TABLE IF NOT EXISTS pinned_repos (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  repo_name     TEXT NOT NULL,
  position      INT NOT NULL,
  pinned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (telegram_id, repo_name)
);
CREATE INDEX IF NOT EXISTS idx_pinned_repos_user ON pinned_repos (telegram_id, position);

-- Tags (user-defined labels) and their assignment to repos
CREATE TABLE IF NOT EXISTS tags (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  name          TEXT NOT NULL,
  emoji         TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (telegram_id, name)
);

CREATE TABLE IF NOT EXISTS repo_tags (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  repo_name     TEXT NOT NULL,
  tag_id        BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  UNIQUE (telegram_id, repo_name, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_repo_tags_lookup ON repo_tags (telegram_id, repo_name);

-- Per-repo "last upload path used" memory, feeds Upload Here's smart default
CREATE TABLE IF NOT EXISTS repo_path_memory (
  telegram_id   BIGINT NOT NULL,
  repo_name     TEXT NOT NULL,
  last_path     TEXT NOT NULL DEFAULT '',
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (telegram_id, repo_name)
);

-- Security-focused connection history, separate from the general Activity Log
CREATE TABLE IF NOT EXISTS access_log (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  event         TEXT NOT NULL, -- 'connected' | 'reconnected' | 'disconnected'
  detail        TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_access_log_user ON access_log (telegram_id, created_at DESC);

-- ── Search History & Size Snapshots ─────────────────────────────

-- Search history — last few searches per user, shown as quick-tap suggestions
CREATE TABLE IF NOT EXISTS search_history (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  query         TEXT NOT NULL,
  searched_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_search_history_user ON search_history (telegram_id, searched_at DESC);

-- One row per (user, total-account size) snapshot — feeds the Stats screen's
-- size trend ("grew by X this week"). Only ever keeps the single most recent
-- prior snapshot; overwritten each time Stats actually shows a trend line.
CREATE TABLE IF NOT EXISTS size_snapshots (
  telegram_id     BIGINT PRIMARY KEY,
  total_bytes     BIGINT NOT NULL,
  snapshotted_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Recently Viewed ──────────────────────────────────────────────

-- Recently viewed repos — quick-tap shortcuts back to whatever you actually
-- opened recently, same shape as search_history.
CREATE TABLE IF NOT EXISTS recently_viewed (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  repo_name     TEXT NOT NULL,
  viewed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recently_viewed_user ON recently_viewed (telegram_id, viewed_at DESC);

-- Per-repo notification mute — keeps GitHub Activity notifications on
-- globally (Settings) while silencing one specific noisy repo.
CREATE TABLE IF NOT EXISTS notification_mutes (
  telegram_id   BIGINT NOT NULL,
  repo_name     TEXT NOT NULL,
  muted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (telegram_id, repo_name)
);

-- Tracks which repos have a live GitHub webhook pointed at this bot, plus
-- the id GitHub assigned it (needed to delete it again on disconnect/mute)
-- and the per-webhook secret used to verify incoming payloads.
CREATE TABLE IF NOT EXISTS repo_webhooks (
  telegram_id   BIGINT NOT NULL,
  repo_name     TEXT NOT NULL,
  webhook_id    BIGINT NOT NULL,
  secret        TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (telegram_id, repo_name)
);

-- ── Nested Tags & Auto-Rules ─────────────────────────────────────

-- Nested tags (self-reference; NULL parent = top-level) + color class for
-- chip rendering. Existing rows get parent_id=NULL, color_class='default'.
ALTER TABLE tags ADD COLUMN IF NOT EXISTS parent_id BIGINT REFERENCES tags(id) ON DELETE CASCADE;
ALTER TABLE tags ADD COLUMN IF NOT EXISTS color_class TEXT NOT NULL DEFAULT 'default';
ALTER TABLE tags ADD COLUMN IF NOT EXISTS auto_rule_json TEXT; -- {"field":"language","op":"eq","value":"Python"} — NULL = manual tag

-- Per-tag default overrides (visibility, upload_path, commit_message).
-- Resolution order: repo's tag override -> global user default.
CREATE TABLE IF NOT EXISTS tag_defaults (
  tag_id        BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
  key           TEXT NOT NULL, -- 'default_visibility' | 'default_upload_path' | 'default_commit_message'
  value         TEXT NOT NULL,
  PRIMARY KEY (tag_id, key)
);

-- Pin sections — optional named grouping, NULL = ungrouped ("Pinned").
ALTER TABLE pinned_repos ADD COLUMN IF NOT EXISTS pin_section TEXT;

-- Saved views ("smart folders") — reuses the same filter-clause JSON shape
-- as Bulk Actions' composable filter builder (see lib/filterClauses.js).
CREATE TABLE IF NOT EXISTS saved_views (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  name          TEXT NOT NULL,
  filter_json   TEXT NOT NULL,
  position      INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (telegram_id, name)
);

-- Every settings/defaults change, old -> new, for the defaults audit trail.
CREATE TABLE IF NOT EXISTS defaults_changelog (
  id            BIGSERIAL PRIMARY KEY,
  telegram_id   BIGINT NOT NULL,
  field         TEXT NOT NULL,
  old_value     TEXT,
  new_value     TEXT,
  source        TEXT NOT NULL DEFAULT 'manual', -- 'manual' | 'learned-suggestion'
  changed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_defaults_changelog_user ON defaults_changelog (telegram_id, changed_at DESC);

-- Reversible bulk-action undo ledger. Scoped to actions that are safely
-- reversible (visibility, tag assign, archive, pin) — never delete/rename.
CREATE TABLE IF NOT EXISTS bulk_action_log (
  id                BIGSERIAL PRIMARY KEY,
  telegram_id       BIGINT NOT NULL,
  action_type       TEXT NOT NULL,
  repo_names        TEXT NOT NULL, -- JSON array
  previous_state    TEXT NOT NULL, -- JSON, shape depends on action_type
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at        TIMESTAMPTZ NOT NULL,
  undone_at         TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_bulk_action_log_user ON bulk_action_log (telegram_id, created_at DESC);

-- Upload path frequency, feeds "learned defaults" suggestions.
CREATE TABLE IF NOT EXISTS upload_path_frequency (
  telegram_id   BIGINT NOT NULL,
  path          TEXT NOT NULL,
  count         INT NOT NULL DEFAULT 1,
  last_used_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (telegram_id, path)
);

-- Rolling size history (size_snapshots stays as the fast "latest" lookup).
CREATE TABLE IF NOT EXISTS size_snapshot_history (
  id                BIGSERIAL PRIMARY KEY,
  telegram_id       BIGINT NOT NULL,
  total_bytes       BIGINT NOT NULL,
  snapshotted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_size_snapshot_history_user ON size_snapshot_history (telegram_id, snapshotted_at DESC);

-- Access Log anomaly flags.
ALTER TABLE access_log ADD COLUMN IF NOT EXISTS is_anomalous BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE access_log ADD COLUMN IF NOT EXISTS anomaly_reason TEXT;

-- New notification prefs: daily/weekly rollup opt-in + quiet hours window.
ALTER TABLE users ADD COLUMN IF NOT EXISTS notif_rollup TEXT NOT NULL DEFAULT 'off'; -- 'off' | 'daily' | 'weekly'
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiet_hours_start INT; -- 0-23, NULL = disabled
ALTER TABLE users ADD COLUMN IF NOT EXISTS quiet_hours_end INT;  -- 0-23

-- Commit message template placeholders live on the existing
-- default_commit_message column itself (e.g. "Update {filename} — {date}"),
-- expanded at commit time — no schema change needed for that piece.

-- ── Automation ───────────────────────────────────────────────────

-- Marks an activity_log row as something GitroHub did on its own (auto-tag
-- rules, applied suggestions) rather than something the person tapped
-- directly — feeds the Automation Log's separate, filtered view.
ALTER TABLE activity_log ADD COLUMN IF NOT EXISTS is_automated BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS idx_activity_log_automated ON activity_log (telegram_id, is_automated, created_at DESC);
