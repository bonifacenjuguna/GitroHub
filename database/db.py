import psycopg2
import psycopg2.extras
import os
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

@contextmanager
def db_cursor():
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def init_db():
    with db_cursor() as cur:
        # Sessions table — one row per GitHub account per Telegram user
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                github_username TEXT NOT NULL,
                github_email TEXT,
                encrypted_token TEXT NOT NULL,
                encrypted_refresh_token TEXT,
                active_repo TEXT,
                active_branch TEXT DEFAULT 'main',
                recent_repos TEXT[] DEFAULT '{}',
                pinned_repos TEXT[] DEFAULT '{}',
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_seen TIMESTAMP DEFAULT NOW(),
                UNIQUE(telegram_id, github_username)
            )
        """)

        # Settings table — one row per Telegram user
        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                telegram_id BIGINT PRIMARY KEY,
                theme TEXT DEFAULT 'dark',
                time_format TEXT DEFAULT '24hr',
                date_format TEXT DEFAULT 'DD/MM/YYYY',
                timezone TEXT DEFAULT 'UTC',
                language TEXT DEFAULT 'en',
                private_message TEXT,
                private_message_owner TEXT,
                private_message_link TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Commit message history
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commit_history (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                github_username TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Saved paths per repo
        cur.execute("""
            CREATE TABLE IF NOT EXISTS saved_paths (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                github_username TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(telegram_id, github_username, repo_name, path)
            )
        """)

        # Command aliases
        cur.execute("""
            CREATE TABLE IF NOT EXISTS aliases (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                alias TEXT NOT NULL,
                command TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(telegram_id, alias)
            )
        """)

        # Commit message templates per repo
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commit_templates (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT NOT NULL,
                github_username TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                template TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Bot state — tracks current action per user
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                telegram_id BIGINT PRIMARY KEY,
                state TEXT DEFAULT 'idle',
                state_data JSONB DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        logger.info("✅ Database initialized successfully")

# ── Session helpers ──────────────────────────────────────────────────────────

def get_active_session(telegram_id: int) -> dict | None:
    with db_cursor() as cur:
        cur.execute("""
            SELECT * FROM sessions
            WHERE telegram_id = %s AND is_active = TRUE
        """, (telegram_id,))
        return cur.fetchone()

def get_all_sessions(telegram_id: int) -> list:
    with db_cursor() as cur:
        cur.execute("""
            SELECT * FROM sessions
            WHERE telegram_id = %s
            ORDER BY last_seen DESC
        """, (telegram_id,))
        return cur.fetchall()

def create_session(telegram_id: int, github_username: str,
                   encrypted_token: str, encrypted_refresh_token: str = None,
                   email: str = None):
    with db_cursor() as cur:
        # Deactivate all other sessions first
        cur.execute("""
            UPDATE sessions SET is_active = FALSE
            WHERE telegram_id = %s
        """, (telegram_id,))
        # Insert or update
        cur.execute("""
            INSERT INTO sessions (telegram_id, github_username, github_email,
                encrypted_token, encrypted_refresh_token, is_active, last_seen)
            VALUES (%s, %s, %s, %s, %s, TRUE, NOW())
            ON CONFLICT (telegram_id, github_username)
            DO UPDATE SET
                encrypted_token = EXCLUDED.encrypted_token,
                encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
                github_email = EXCLUDED.github_email,
                is_active = TRUE,
                last_seen = NOW()
        """, (telegram_id, github_username, email,
              encrypted_token, encrypted_refresh_token))

def switch_session(telegram_id: int, github_username: str):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE sessions SET is_active = FALSE
            WHERE telegram_id = %s
        """, (telegram_id,))
        cur.execute("""
            UPDATE sessions SET is_active = TRUE, last_seen = NOW()
            WHERE telegram_id = %s AND github_username = %s
        """, (telegram_id, github_username))

def update_session(telegram_id: int, **kwargs):
    if not kwargs:
        return
    allowed = {'active_repo', 'active_branch', 'recent_repos',
                'pinned_repos', 'encrypted_token', 'last_seen'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [telegram_id]
    with db_cursor() as cur:
        cur.execute(f"""
            UPDATE sessions SET {set_clause}, last_seen = NOW()
            WHERE telegram_id = %s AND is_active = TRUE
        """, values)

def delete_session(telegram_id: int, github_username: str):
    with db_cursor() as cur:
        cur.execute("""
            DELETE FROM sessions
            WHERE telegram_id = %s AND github_username = %s
        """, (telegram_id, github_username))

def add_to_recent(telegram_id: int, repo_name: str):
    with db_cursor() as cur:
        cur.execute("""
            UPDATE sessions
            SET recent_repos = array_prepend(
                %s,
                array_remove(recent_repos, %s)
            )
            WHERE telegram_id = %s AND is_active = TRUE
        """, (repo_name, repo_name, telegram_id))

# ── Settings helpers ─────────────────────────────────────────────────────────

def get_settings(telegram_id: int) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM settings WHERE telegram_id = %s", (telegram_id,))
        row = cur.fetchone()
        if not row:
            cur.execute("""
                INSERT INTO settings (telegram_id) VALUES (%s)
                ON CONFLICT DO NOTHING
            """, (telegram_id,))
            return {"theme": "dark", "time_format": "24hr",
                    "date_format": "DD/MM/YYYY", "timezone": "UTC",
                    "language": "en", "private_message": None,
                    "private_message_owner": None, "private_message_link": None}
        return dict(row)

def update_settings(telegram_id: int, **kwargs):
    allowed = {'theme', 'time_format', 'date_format', 'timezone',
                'language', 'private_message', 'private_message_owner',
                'private_message_link'}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [telegram_id]
    with db_cursor() as cur:
        cur.execute(f"""
            INSERT INTO settings (telegram_id) VALUES (%s)
            ON CONFLICT (telegram_id) DO NOTHING
        """, (telegram_id,))
        cur.execute(f"""
            UPDATE settings SET {set_clause}, updated_at = NOW()
            WHERE telegram_id = %s
        """, values)

# ── Bot state helpers ────────────────────────────────────────────────────────

def get_state(telegram_id: int) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM bot_state WHERE telegram_id = %s", (telegram_id,))
        row = cur.fetchone()
        if not row:
            return {"state": "idle", "state_data": {}}
        return dict(row)

def set_state(telegram_id: int, state: str, state_data: dict = None):
    import json
    data = json.dumps(state_data or {})
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO bot_state (telegram_id, state, state_data, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (telegram_id) DO UPDATE SET
                state = EXCLUDED.state,
                state_data = EXCLUDED.state_data,
                updated_at = NOW()
        """, (telegram_id, state, data))

def clear_state(telegram_id: int):
    set_state(telegram_id, "idle", {})

# ── Commit history helpers ───────────────────────────────────────────────────

def add_commit_message(telegram_id: int, github_username: str,
                       repo_name: str, message: str):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO commit_history
            (telegram_id, github_username, repo_name, message)
            VALUES (%s, %s, %s, %s)
        """, (telegram_id, github_username, repo_name, message))
        # Keep only last 10 per repo
        cur.execute("""
            DELETE FROM commit_history
            WHERE id NOT IN (
                SELECT id FROM commit_history
                WHERE telegram_id = %s AND github_username = %s
                  AND repo_name = %s
                ORDER BY created_at DESC LIMIT 10
            )
            AND telegram_id = %s AND github_username = %s AND repo_name = %s
        """, (telegram_id, github_username, repo_name,
              telegram_id, github_username, repo_name))

def get_commit_history(telegram_id: int, github_username: str,
                       repo_name: str) -> list:
    with db_cursor() as cur:
        cur.execute("""
            SELECT message FROM commit_history
            WHERE telegram_id = %s AND github_username = %s AND repo_name = %s
            ORDER BY created_at DESC LIMIT 10
        """, (telegram_id, github_username, repo_name))
        return [row["message"] for row in cur.fetchall()]

# ── Saved paths helpers ──────────────────────────────────────────────────────

def get_saved_paths(telegram_id: int, github_username: str,
                    repo_name: str) -> list:
    with db_cursor() as cur:
        cur.execute("""
            SELECT path FROM saved_paths
            WHERE telegram_id = %s AND github_username = %s AND repo_name = %s
            ORDER BY created_at DESC
        """, (telegram_id, github_username, repo_name))
        return [row["path"] for row in cur.fetchall()]

def add_saved_path(telegram_id: int, github_username: str,
                   repo_name: str, path: str):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO saved_paths
            (telegram_id, github_username, repo_name, path)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (telegram_id, github_username, repo_name, path))

def remove_saved_path(telegram_id: int, github_username: str,
                      repo_name: str, path: str):
    with db_cursor() as cur:
        cur.execute("""
            DELETE FROM saved_paths
            WHERE telegram_id = %s AND github_username = %s
              AND repo_name = %s AND path = %s
        """, (telegram_id, github_username, repo_name, path))

# ── Aliases helpers ──────────────────────────────────────────────────────────

def get_aliases(telegram_id: int) -> list:
    with db_cursor() as cur:
        cur.execute("""
            SELECT alias, command FROM aliases
            WHERE telegram_id = %s ORDER BY alias
        """, (telegram_id,))
        return cur.fetchall()

def add_alias(telegram_id: int, alias: str, command: str):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO aliases (telegram_id, alias, command)
            VALUES (%s, %s, %s)
            ON CONFLICT (telegram_id, alias)
            DO UPDATE SET command = EXCLUDED.command
        """, (telegram_id, alias, command))

def remove_alias(telegram_id: int, alias: str):
    with db_cursor() as cur:
        cur.execute("""
            DELETE FROM aliases WHERE telegram_id = %s AND alias = %s
        """, (telegram_id, alias))

# ── Commit templates helpers ─────────────────────────────────────────────────

def get_templates(telegram_id: int, github_username: str,
                  repo_name: str) -> list:
    with db_cursor() as cur:
        cur.execute("""
            SELECT id, template FROM commit_templates
            WHERE telegram_id = %s AND github_username = %s AND repo_name = %s
            ORDER BY created_at DESC
        """, (telegram_id, github_username, repo_name))
        return cur.fetchall()

def add_template(telegram_id: int, github_username: str,
                 repo_name: str, template: str):
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO commit_templates
            (telegram_id, github_username, repo_name, template)
            VALUES (%s, %s, %s, %s)
        """, (telegram_id, github_username, repo_name, template))

def remove_template(template_id: int, telegram_id: int):
    with db_cursor() as cur:
        cur.execute("""
            DELETE FROM commit_templates
            WHERE id = %s AND telegram_id = %s
        """, (template_id, telegram_id))
