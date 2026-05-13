"""
Database — GitroHub v2.0
asyncpg connection pool + all queries.
Zero blocking operations.
"""
import asyncpg
import orjson
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)
_pool: Optional[asyncpg.Pool] = None


async def init_pool():
    global _pool
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=settings.db_min_connections,
        max_size=settings.db_max_connections,
        command_timeout=10,
        ssl="require" if settings.database_url.startswith("postgresql://") and "localhost" not in settings.database_url and "127.0.0.1" not in settings.database_url else None,
    )
    await _create_tables()
    logger.info("✅ Database pool initialized")


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool


# ── Schema ────────────────────────────────────────────────────────────────────

async def _create_tables():
    async with pool().acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id     BIGINT PRIMARY KEY,
            role            TEXT NOT NULL DEFAULT 'member',
            invited_by      BIGINT,
            invite_token    TEXT,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_active     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id                    SERIAL PRIMARY KEY,
            telegram_id           BIGINT NOT NULL,
            github_username       TEXT NOT NULL,
            github_email          TEXT,
            github_plan           TEXT,
            encrypted_token       TEXT NOT NULL,
            encrypted_refresh     TEXT,
            active_repo           TEXT,
            active_branch         TEXT DEFAULT 'main',
            recent_repos          TEXT[] DEFAULT '{}',
            pinned_repos          TEXT[] DEFAULT '{}',
            is_active             BOOLEAN NOT NULL DEFAULT FALSE,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(telegram_id, github_username)
        );

        CREATE TABLE IF NOT EXISTS settings (
            telegram_id         BIGINT PRIMARY KEY,
            theme               TEXT DEFAULT 'dark',
            time_format         TEXT DEFAULT '24hr',
            date_format         TEXT DEFAULT 'DD/MM/YYYY',
            timezone            TEXT DEFAULT 'UTC',
            language            TEXT DEFAULT 'en',
            private_message     TEXT,
            pm_owner            TEXT,
            pm_link             TEXT,
            notif_stars         BOOLEAN DEFAULT TRUE,
            notif_pulls         BOOLEAN DEFAULT TRUE,
            notif_issues        BOOLEAN DEFAULT TRUE,
            notif_workflow_fail BOOLEAN DEFAULT TRUE,
            notif_workflow_pass BOOLEAN DEFAULT FALSE,
            notif_releases      BOOLEAN DEFAULT TRUE,
            notif_forks         BOOLEAN DEFAULT FALSE,
            notif_followers     BOOLEAN DEFAULT TRUE,
            notif_security      BOOLEAN DEFAULT TRUE,
            notif_comments      BOOLEAN DEFAULT FALSE,
            quiet_hours_enabled BOOLEAN DEFAULT FALSE,
            quiet_from          TEXT DEFAULT '22:00',
            quiet_until         TEXT DEFAULT '08:00',
            muted_repos         TEXT[] DEFAULT '{}',
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS commit_messages (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            github_username TEXT NOT NULL,
            repo_name       TEXT NOT NULL,
            message         TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS commit_templates (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            github_username TEXT NOT NULL,
            repo_name       TEXT NOT NULL,
            template        TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS saved_paths (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            github_username TEXT NOT NULL,
            repo_name       TEXT NOT NULL,
            path            TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(telegram_id, github_username, repo_name, path)
        );

        CREATE TABLE IF NOT EXISTS aliases (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            alias           TEXT NOT NULL,
            command         TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(telegram_id, alias)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            event_type      TEXT NOT NULL,
            repo_name       TEXT,
            title           TEXT NOT NULL,
            body            TEXT,
            actor           TEXT,
            url             TEXT,
            is_read         BOOLEAN DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS invites (
            id              SERIAL PRIMARY KEY,
            token           TEXT NOT NULL UNIQUE,
            created_by      BIGINT NOT NULL,
            used_by         BIGINT,
            is_used         BOOLEAN DEFAULT FALSE,
            expires_at      TIMESTAMPTZ NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS projects (
            id              SERIAL PRIMARY KEY,
            telegram_id     BIGINT NOT NULL,
            name            TEXT NOT NULL,
            description     TEXT,
            files           JSONB DEFAULT '{}',
            target_repo     TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(telegram_id, name)
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_telegram
            ON sessions(telegram_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_active
            ON sessions(telegram_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_notifications_telegram
            ON notifications(telegram_id, is_read, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_commit_messages_lookup
            ON commit_messages(telegram_id, github_username, repo_name);
        """)
        logger.info("✅ Database schema created/verified")


# ── User queries ──────────────────────────────────────────────────────────────

async def get_user(telegram_id: int) -> Optional[dict]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
        return dict(row) if row else None


async def create_user(telegram_id: int, role: str = "member",
                      invited_by: int = None, invite_token: str = None):
    async with pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, role, invited_by, invite_token)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (telegram_id) DO UPDATE
            SET last_active = NOW(), is_active = TRUE
        """, telegram_id, role, invited_by, invite_token)


async def update_user_activity(telegram_id: int):
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE users SET last_active = NOW() WHERE telegram_id = $1",
            telegram_id
        )


async def is_authorized(telegram_id: int) -> bool:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT is_active FROM users WHERE telegram_id = $1", telegram_id
        )
        return bool(row and row["is_active"])


async def get_all_users() -> list[dict]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM users ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]


async def revoke_user(telegram_id: int):
    async with pool().acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_active = FALSE WHERE telegram_id = $1",
            telegram_id
        )


# ── Session queries ───────────────────────────────────────────────────────────

async def get_active_session(telegram_id: int) -> Optional[dict]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            SELECT * FROM sessions
            WHERE telegram_id = $1 AND is_active = TRUE
        """, telegram_id)
        return dict(row) if row else None


async def get_all_sessions(telegram_id: int) -> list[dict]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM sessions
            WHERE telegram_id = $1
            ORDER BY last_seen DESC
        """, telegram_id)
        return [dict(r) for r in rows]


async def create_session(telegram_id: int, github_username: str,
                         encrypted_token: str, encrypted_refresh: str = None,
                         email: str = None, plan: str = None):
    async with pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                UPDATE sessions SET is_active = FALSE
                WHERE telegram_id = $1
            """, telegram_id)
            await conn.execute("""
                INSERT INTO sessions
                    (telegram_id, github_username, github_email, github_plan,
                     encrypted_token, encrypted_refresh, is_active)
                VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                ON CONFLICT (telegram_id, github_username) DO UPDATE SET
                    encrypted_token  = EXCLUDED.encrypted_token,
                    encrypted_refresh= EXCLUDED.encrypted_refresh,
                    github_email     = EXCLUDED.github_email,
                    github_plan      = EXCLUDED.github_plan,
                    is_active        = TRUE,
                    last_seen        = NOW()
            """, telegram_id, github_username, email, plan,
                encrypted_token, encrypted_refresh)


async def switch_session(telegram_id: int, github_username: str):
    async with pool().acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE sessions SET is_active = FALSE WHERE telegram_id = $1",
                telegram_id
            )
            await conn.execute("""
                UPDATE sessions SET is_active = TRUE, last_seen = NOW()
                WHERE telegram_id = $1 AND github_username = $2
            """, telegram_id, github_username)


async def update_session(telegram_id: int, **kwargs):
    allowed = {
        "active_repo", "active_branch", "recent_repos",
        "pinned_repos", "encrypted_token", "last_seen"
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_parts = ", ".join(
        f"{k} = ${i+2}" for i, k in enumerate(fields)
    )
    values = list(fields.values())
    async with pool().acquire() as conn:
        await conn.execute(
            f"UPDATE sessions SET {set_parts}, last_seen = NOW()"
            f" WHERE telegram_id = $1 AND is_active = TRUE",
            telegram_id, *values
        )


async def delete_session(telegram_id: int, github_username: str):
    async with pool().acquire() as conn:
        await conn.execute("""
            DELETE FROM sessions
            WHERE telegram_id = $1 AND github_username = $2
        """, telegram_id, github_username)


async def add_to_recent(telegram_id: int, repo_name: str):
    async with pool().acquire() as conn:
        await conn.execute("""
            UPDATE sessions
            SET recent_repos = array_prepend(
                $2, array_remove(recent_repos, $2)
            )[1:10]
            WHERE telegram_id = $1 AND is_active = TRUE
        """, telegram_id, repo_name)


# ── Settings queries ──────────────────────────────────────────────────────────

async def get_settings(telegram_id: int) -> dict:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM settings WHERE telegram_id = $1", telegram_id
        )
        if not row:
            await conn.execute(
                "INSERT INTO settings (telegram_id) VALUES ($1)"
                " ON CONFLICT DO NOTHING", telegram_id
            )
            row = await conn.fetchrow(
                "SELECT * FROM settings WHERE telegram_id = $1", telegram_id
            )
        return dict(row) if row else {}


async def update_settings(telegram_id: int, **kwargs):
    if not kwargs:
        return
    await get_settings(telegram_id)  # ensure row exists
    cols = list(kwargs.keys())
    vals = list(kwargs.values())
    set_parts = ", ".join(f"{c} = ${i+2}" for i, c in enumerate(cols))
    async with pool().acquire() as conn:
        await conn.execute(
            f"UPDATE settings SET {set_parts}, updated_at = NOW()"
            f" WHERE telegram_id = $1",
            telegram_id, *vals
        )


# ── Commit messages ───────────────────────────────────────────────────────────

async def add_commit_message(telegram_id: int, github_username: str,
                              repo_name: str, message: str):
    async with pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO commit_messages
                (telegram_id, github_username, repo_name, message)
            VALUES ($1, $2, $3, $4)
        """, telegram_id, github_username, repo_name, message)
        # Keep only last 15 per repo
        await conn.execute("""
            DELETE FROM commit_messages
            WHERE id NOT IN (
                SELECT id FROM commit_messages
                WHERE telegram_id=$1 AND github_username=$2 AND repo_name=$3
                ORDER BY created_at DESC LIMIT 15
            )
            AND telegram_id=$1 AND github_username=$2 AND repo_name=$3
        """, telegram_id, github_username, repo_name)


async def get_commit_messages(telegram_id: int, github_username: str,
                               repo_name: str) -> list[str]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT message FROM commit_messages
            WHERE telegram_id=$1 AND github_username=$2 AND repo_name=$3
            ORDER BY created_at DESC LIMIT 10
        """, telegram_id, github_username, repo_name)
        return [r["message"] for r in rows]


# ── Templates ─────────────────────────────────────────────────────────────────

async def get_templates(telegram_id: int, github_username: str,
                        repo_name: str) -> list[dict]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT id, template FROM commit_templates
            WHERE telegram_id=$1 AND github_username=$2 AND repo_name=$3
            ORDER BY created_at DESC
        """, telegram_id, github_username, repo_name)
        return [dict(r) for r in rows]


async def add_template(telegram_id: int, github_username: str,
                       repo_name: str, template: str):
    async with pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO commit_templates
                (telegram_id, github_username, repo_name, template)
            VALUES ($1, $2, $3, $4)
        """, telegram_id, github_username, repo_name, template)


async def remove_template(template_id: int, telegram_id: int):
    async with pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM commit_templates WHERE id=$1 AND telegram_id=$2",
            template_id, telegram_id
        )


# ── Saved paths ───────────────────────────────────────────────────────────────

async def get_saved_paths(telegram_id: int, github_username: str,
                          repo_name: str) -> list[str]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT path FROM saved_paths
            WHERE telegram_id=$1 AND github_username=$2 AND repo_name=$3
            ORDER BY created_at DESC
        """, telegram_id, github_username, repo_name)
        return [r["path"] for r in rows]


async def add_saved_path(telegram_id: int, github_username: str,
                         repo_name: str, path: str):
    async with pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO saved_paths
                (telegram_id, github_username, repo_name, path)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT DO NOTHING
        """, telegram_id, github_username, repo_name, path)


async def remove_saved_path(telegram_id: int, github_username: str,
                            repo_name: str, path: str):
    async with pool().acquire() as conn:
        await conn.execute("""
            DELETE FROM saved_paths
            WHERE telegram_id=$1 AND github_username=$2
              AND repo_name=$3 AND path=$4
        """, telegram_id, github_username, repo_name, path)


# ── Aliases ───────────────────────────────────────────────────────────────────

async def get_aliases(telegram_id: int) -> list[dict]:
    async with pool().acquire() as conn:
        rows = await conn.fetch(
            "SELECT alias, command FROM aliases WHERE telegram_id=$1 ORDER BY alias",
            telegram_id
        )
        return [dict(r) for r in rows]


async def add_alias(telegram_id: int, alias: str, command: str):
    async with pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO aliases (telegram_id, alias, command)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id, alias) DO UPDATE SET command=EXCLUDED.command
        """, telegram_id, alias, command)


async def remove_alias(telegram_id: int, alias: str):
    async with pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM aliases WHERE telegram_id=$1 AND alias=$2",
            telegram_id, alias
        )


# ── Notifications ─────────────────────────────────────────────────────────────

async def store_notification(telegram_id: int, event_type: str,
                              repo_name: str, title: str, body: str = None,
                              actor: str = None, url: str = None):
    async with pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO notifications
                (telegram_id, event_type, repo_name, title, body, actor, url)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
        """, telegram_id, event_type, repo_name, title, body, actor, url)
        # Keep only last 200 notifications per user
        await conn.execute("""
            DELETE FROM notifications
            WHERE telegram_id=$1 AND id NOT IN (
                SELECT id FROM notifications
                WHERE telegram_id=$1
                ORDER BY created_at DESC LIMIT 200
            )
        """, telegram_id)


async def get_notifications(telegram_id: int, unread_only: bool = False,
                             limit: int = 8, offset: int = 0) -> list[dict]:
    async with pool().acquire() as conn:
        where = "WHERE telegram_id=$1"
        if unread_only:
            where += " AND is_read=FALSE"
        rows = await conn.fetch(
            f"SELECT * FROM notifications {where}"
            f" ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            telegram_id, limit, offset
        )
        return [dict(r) for r in rows]


async def count_unread(telegram_id: int) -> int:
    async with pool().acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM notifications"
            " WHERE telegram_id=$1 AND is_read=FALSE",
            telegram_id
        ) or 0


async def mark_notifications_read(telegram_id: int, notif_id: int = None):
    async with pool().acquire() as conn:
        if notif_id:
            await conn.execute(
                "UPDATE notifications SET is_read=TRUE"
                " WHERE telegram_id=$1 AND id=$2",
                telegram_id, notif_id
            )
        else:
            await conn.execute(
                "UPDATE notifications SET is_read=TRUE WHERE telegram_id=$1",
                telegram_id
            )


# ── Invites ───────────────────────────────────────────────────────────────────

async def create_invite(token: str, created_by: int, expires_at) -> dict:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO invites (token, created_by, expires_at)
            VALUES ($1, $2, $3)
            RETURNING *
        """, token, created_by, expires_at)
        return dict(row)


async def get_invite(token: str) -> Optional[dict]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM invites WHERE token=$1", token
        )
        return dict(row) if row else None


async def use_invite(token: str, used_by: int):
    async with pool().acquire() as conn:
        await conn.execute("""
            UPDATE invites SET is_used=TRUE, used_by=$2
            WHERE token=$1
        """, token, used_by)


async def cancel_invite(token: str, created_by: int):
    async with pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM invites WHERE token=$1 AND created_by=$2",
            token, created_by
        )


async def get_pending_invites(created_by: int) -> list[dict]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM invites
            WHERE created_by=$1 AND is_used=FALSE
              AND expires_at > NOW()
            ORDER BY created_at DESC
        """, created_by)
        return [dict(r) for r in rows]


# ── Projects (offline workspace) ──────────────────────────────────────────────

async def get_projects(telegram_id: int) -> list[dict]:
    async with pool().acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM projects WHERE telegram_id=$1
            ORDER BY updated_at DESC
        """, telegram_id)
        return [dict(r) for r in rows]


async def get_project(telegram_id: int, name: str) -> Optional[dict]:
    async with pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM projects WHERE telegram_id=$1 AND name=$2",
            telegram_id, name
        )
        return dict(row) if row else None


async def create_project(telegram_id: int, name: str,
                         description: str = None) -> dict:
    async with pool().acquire() as conn:
        row = await conn.fetchrow("""
            INSERT INTO projects (telegram_id, name, description)
            VALUES ($1, $2, $3)
            RETURNING *
        """, telegram_id, name, description)
        return dict(row)


async def update_project_files(telegram_id: int, name: str, files: dict):
    async with pool().acquire() as conn:
        await conn.execute("""
            UPDATE projects SET files=$3, updated_at=NOW()
            WHERE telegram_id=$1 AND name=$2
        """, telegram_id, name, orjson.dumps(files).decode())


async def delete_project(telegram_id: int, name: str):
    async with pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM projects WHERE telegram_id=$1 AND name=$2",
            telegram_id, name
        )


# ── Stats (admin) ─────────────────────────────────────────────────────────────

async def get_bot_stats() -> dict:
    async with pool().acquire() as conn:
        active_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE is_active=TRUE"
        )
        total_sessions = await conn.fetchval(
            "SELECT COUNT(*) FROM sessions"
        )
        total_commits = await conn.fetchval(
            "SELECT COUNT(*) FROM commit_messages"
        )
        total_notifs = await conn.fetchval(
            "SELECT COUNT(*) FROM notifications"
        )
        return {
            "active_users": active_users or 0,
            "total_sessions": total_sessions or 0,
            "total_commits": total_commits or 0,
            "total_notifications": total_notifs or 0,
        }
