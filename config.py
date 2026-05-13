"""
GitroHub v2.1 — Configuration
All settings loaded from environment variables with validation.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # ── Telegram ──────────────────────────────────────────────────────────────
    bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    admin_id: int = Field(..., alias="TELEGRAM_ADMIN_ID")
    webhook_url: str = Field("", alias="WEBHOOK_URL")
    webhook_secret: str = Field("gitrohub_secret_2024", alias="WEBHOOK_SECRET")
    port: int = Field(8080, alias="PORT")

    # ── GitHub OAuth ──────────────────────────────────────────────────────────
    github_client_id: str = Field(..., alias="GITHUB_CLIENT_ID")
    github_client_secret: str = Field(..., alias="GITHUB_CLIENT_SECRET")

    @property
    def github_redirect_uri(self) -> str:
        base = self.webhook_url.rstrip("/")
        return f"{base}/auth/github/callback"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(..., alias="DATABASE_URL")
    db_min_connections: int = 2
    db_max_connections: int = 10

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field("redis://localhost:6379", alias="REDIS_URL")

    # ── Security ──────────────────────────────────────────────────────────────
    aes_key: str = Field(..., alias="AES_ENCRYPTION_KEY")

    # ── App ───────────────────────────────────────────────────────────────────
    bot_version: str = "2.2.0"
    bot_name: str = "GitroHub"
    bot_username: str = "GitroHubBot"
    debug: bool = Field(False, alias="DEBUG")

    # ── Cache TTL (seconds) ───────────────────────────────────────────────────
    ttl_repos: int = 60           # Repository list
    ttl_repo_detail: int = 30     # Single repo detail
    ttl_files: int = 30           # File browser
    ttl_branches: int = 30        # Branches list
    ttl_commits: int = 60         # Commits history
    ttl_profile: int = 120        # User profile
    ttl_notifications: int = 10   # Notifications (short — real-time)
    ttl_rate_limit: int = 60      # API rate limit status

    # ── Debounce ──────────────────────────────────────────────────────────────
    debounce_ms: int = 500        # Milliseconds between allowed actions

    # ── Pagination ────────────────────────────────────────────────────────────
    repos_per_page: int = 5
    commits_per_page: int = 8
    notifications_per_page: int = 8
    issues_per_page: int = 6
    pulls_per_page: int = 6

    # ── Invite system ─────────────────────────────────────────────────────────
    invite_expiry_hours: int = 24
    invite_single_use: bool = True

    class Config:
        env_file = ".env"
        populate_by_name = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
