-- ============================================================
-- GitroHub — PostgreSQL Schema
-- Single-owner bot, but modeled with telegram_user_id everywhere
-- so nothing breaks if you ever loosen the owner-only restriction.
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
  telegram_user_id     BIGINT PRIMARY KEY,
  telegram_username    TEXT,
  telegram_first_name  TEXT,
  telegram_last_name   TEXT,
  github_username      TEXT,
  github_user_id       BIGINT,
  encrypted_token       TEXT,            -- AES-256-GCM encrypted OAuth token
  token_scopes          TEXT,
  pin_hash               TEXT,            -- bcrypt-style hash, null = PIN lock disabled
  connected_at           TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS oauth_states (
  state          TEXT PRIMARY KEY,
  telegram_user_id BIGINT NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at      TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pinned_repos (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  repo_full_name    TEXT NOT NULL,
  pinned_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(telegram_user_id, repo_full_name)
);

CREATE TABLE IF NOT EXISTS user_preferences (
  telegram_user_id     BIGINT PRIMARY KEY REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  list_view_style        TEXT NOT NULL DEFAULT 'cards',       -- cards | compact
  diff_style              TEXT NOT NULL DEFAULT 'unified',     -- unified | split
  emoji_density            TEXT NOT NULL DEFAULT 'full',        -- full | minimal | off
  date_format               TEXT NOT NULL DEFAULT 'relative',    -- relative | absolute
  default_repo_visibility   TEXT NOT NULL DEFAULT 'private',
  default_readme            BOOLEAN NOT NULL DEFAULT true,
  default_gitignore_template TEXT NOT NULL DEFAULT 'Node',
  default_license           TEXT NOT NULL DEFAULT 'MIT',
  upload_target_mode        TEXT NOT NULL DEFAULT 'ask',         -- ask | fixed_branch | fixed_repo
  commit_message_mode       TEXT NOT NULL DEFAULT 'ask',         -- ask | auto
  notifications_enabled     BOOLEAN NOT NULL DEFAULT true,
  quiet_hours_start          SMALLINT,
  quiet_hours_end            SMALLINT,
  quiet_hours_mute_critical  BOOLEAN NOT NULL DEFAULT false,
  language                   TEXT NOT NULL DEFAULT 'en',
  timezone                   TEXT NOT NULL DEFAULT 'UTC',
  developer_mode             BOOLEAN NOT NULL DEFAULT false,
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repo_notification_settings (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  repo_full_name    TEXT NOT NULL,
  on_push            BOOLEAN NOT NULL DEFAULT true,
  on_pr               BOOLEAN NOT NULL DEFAULT true,
  on_issue            BOOLEAN NOT NULL DEFAULT false,
  on_action_failure   BOOLEAN NOT NULL DEFAULT true,
  on_release          BOOLEAN NOT NULL DEFAULT false,
  webhook_id          BIGINT,
  UNIQUE(telegram_user_id, repo_full_name)
);

CREATE TABLE IF NOT EXISTS custom_shortcuts (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  command             TEXT NOT NULL,
  action_type          TEXT NOT NULL,     -- upload_to_repo | open_repo | show_prs
  target_repo           TEXT,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(telegram_user_id, command)
);

CREATE TABLE IF NOT EXISTS activity_log (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  action_type         TEXT NOT NULL,      -- delete_repo | change_visibility | merge_pr | push | disconnect | ...
  repo_full_name      TEXT,
  details               JSONB,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_log_user_time ON activity_log (telegram_user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS scheduled_tasks (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  task_type           TEXT NOT NULL,      -- repo_summary | delete_merged_branches | trigger_workflow | pull_notify | auto_commit | auto_readme
  cron_expression      TEXT NOT NULL,
  config                 JSONB NOT NULL DEFAULT '{}'::jsonb,
  enabled                 BOOLEAN NOT NULL DEFAULT true,
  last_run_at             TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trigger_rules (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  repo_full_name      TEXT,
  trigger_event         TEXT NOT NULL,     -- push | pr_opened | issue_opened | action_failed | label_added | release_published
  trigger_condition      JSONB NOT NULL DEFAULT '{}'::jsonb,
  action_type             TEXT NOT NULL,     -- notify | add_label | auto_assign | auto_comment | trigger_workflow | auto_rerun
  action_config             JSONB NOT NULL DEFAULT '{}'::jsonb,
  enabled                    BOOLEAN NOT NULL DEFAULT true,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS automerge_rules (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  repo_full_name      TEXT NOT NULL,
  target_branch         TEXT NOT NULL DEFAULT 'main',
  require_checks          BOOLEAN NOT NULL DEFAULT true,
  require_no_conflicts     BOOLEAN NOT NULL DEFAULT true,
  require_approval          BOOLEAN NOT NULL DEFAULT false,
  merge_method               TEXT NOT NULL DEFAULT 'squash',
  enabled                     BOOLEAN NOT NULL DEFAULT true,
  UNIQUE(telegram_user_id, repo_full_name)
);

CREATE TABLE IF NOT EXISTS backups (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  storage_path        TEXT NOT NULL,
  repo_count            INT NOT NULL,
  size_bytes             BIGINT NOT NULL,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS repo_templates (
  id                SERIAL PRIMARY KEY,
  telegram_user_id  BIGINT NOT NULL REFERENCES users(telegram_user_id) ON DELETE CASCADE,
  name                 TEXT NOT NULL,
  source_repo_full_name TEXT NOT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions_backup (
  -- Redis is the source of truth for live sessions; this table exists only
  -- as an optional durability fallback for long-running pendingAction state
  -- if you ever want session data to survive a full Redis flush.
  telegram_user_id  BIGINT PRIMARY KEY,
  session_json        JSONB NOT NULL,
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
