from github import Github, GithubException, UnknownObjectException
from github.Repository import Repository
from utils.encryption import decrypt
from database.db import get_active_session, update_session
import logging
import base64
import os

logger = logging.getLogger(__name__)

# ── Error messages ────────────────────────────────────────────────────────────

GITHUB_ERRORS = {
    401: (
        "❌ GitHub rejected your credentials\n"
        "Reason: Your access token has expired or was manually revoked on GitHub.\n\n"
        "Fix: Reconnect your account so a fresh token is issued."
    ),
    403: (
        "❌ GitHub refused this action\n"
        "Reason: You don't have permission to do this on this repo. "
        "It may be owned by someone else or your token lacks the required scope.\n\n"
        "Fix: Check repo ownership or reconnect with full permissions."
    ),
    404: (
        "❌ GitHub couldn't find this\n"
        "Reason: The repo, file or branch you're looking for doesn't exist "
        "or was deleted on GitHub.\n\n"
        "Fix: Check the name and try again."
    ),
    409: (
        "❌ Commit conflict detected\n"
        "Reason: The file on GitHub was changed by someone else after you last "
        "fetched it. Your version is now behind GitHub's version.\n\n"
        "Fix: Read the current file first, then re-upload your changes."
    ),
    422: (
        "❌ GitHub rejected this data\n"
        "Reason: Something in your request is invalid — this usually happens "
        "with repo names containing special characters or branch names with spaces.\n\n"
        "Fix: Use only letters, numbers, hyphens and underscores."
    ),
    500: (
        "❌ GitHub is having internal issues\n"
        "Reason: This is on GitHub's side — not your connection or your data. "
        "Nothing was changed in your repo.\n\n"
        "Fix: Wait a few minutes and retry.\n"
        "Check: githubstatus.com"
    ),
    503: (
        "❌ GitHub is temporarily down\n"
        "Reason: GitHub's servers are under maintenance or experiencing an outage. "
        "Your repo and data are completely safe.\n\n"
        "Fix: Check githubstatus.com for estimated recovery time."
    ),
}


def get_error_message(status: int) -> str:
    return GITHUB_ERRORS.get(status, f"❌ GitHub API error (status {status})\nReason: Unexpected error from GitHub.\n\nFix: Try again in a moment.")


def get_github_client(telegram_id: int) -> Github | None:
    session = get_active_session(telegram_id)
    if not session:
        return None
    token = decrypt(session["encrypted_token"])
    return Github(token)


def get_repo(telegram_id: int, repo_name: str = None) -> Repository | None:
    session = get_active_session(telegram_id)
    if not session:
        return None
    gh = get_github_client(telegram_id)
    if not gh:
        return None
    name = repo_name or session.get("active_repo")
    if not name:
        return None
    try:
        return gh.get_repo(name)
    except GithubException:
        return None


def format_size(size_kb: int) -> str:
    if size_kb < 1024:
        return f"{size_kb} KB"
    return f"{size_kb / 1024:.1f} MB"


def format_time_ago(dt) -> str:
    from datetime import datetime, timezone
    import humanize
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return humanize.naturaltime(datetime.now(timezone.utc) - dt)


def get_file_diff(old_content: str, new_content: str,
                  filename: str = "") -> str:
    """Generate a simple diff between two file contents."""
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()

    diff_lines = []
    import difflib
    differ = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"current/{filename}",
        tofile=f"new/{filename}",
        lineterm=""
    )

    changed = 0
    for line in differ:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            diff_lines.append("─────────────────────")
            continue
        if line.startswith("+"):
            diff_lines.append(f"+ {line[1:]}")
            changed += 1
        elif line.startswith("-"):
            diff_lines.append(f"- {line[1:]}")
            changed += 1
        else:
            diff_lines.append(f"  {line[1:]}")

    if not diff_lines:
        return "", 0

    # Limit to 30 lines for Telegram
    if len(diff_lines) > 30:
        shown = diff_lines[:30]
        shown.append(f"... and {len(diff_lines) - 30} more lines")
        diff_lines = shown

    return "\n".join(diff_lines), changed


def build_tree(contents, prefix="", changed_files=None,
               new_files=None, deleted_files=None) -> str:
    """Build a visual file tree string."""
    changed_files = changed_files or set()
    new_files = new_files or set()
    deleted_files = deleted_files or set()

    lines = []
    items = sorted(contents, key=lambda x: (x.type != "dir", x.name))

    for i, item in enumerate(items):
        is_last = i == len(items) - 1
        connector = "└── " if is_last else "├── "
        path = item.path

        if item.type == "dir":
            lines.append(f"{prefix}{connector}📁 {item.name}/")
        else:
            icon = "📄"
            suffix = ""
            if path in new_files:
                icon = "✨"
                suffix = "  ← new"
            elif path in changed_files:
                icon = "🟡"
                suffix = "  ← modified"
            elif path in deleted_files:
                icon = "🗑️"
                suffix = "  ← will be deleted"
            lines.append(f"{prefix}{connector}{icon} {item.name}{suffix}")

    return "\n".join(lines)


def is_sensitive_file(filename: str) -> bool:
    sensitive = {".env", ".env.local", ".env.production",
                 ".env.development", "secrets.json", "credentials.json",
                 "id_rsa", "id_ed25519", ".pem", ".key"}
    name = filename.lower()
    return any(name == s or name.endswith(s) for s in sensitive)


def sanitize_path(path: str) -> str:
    """Prevent path traversal attacks."""
    import posixpath
    # Normalize and remove any traversal attempts
    clean = posixpath.normpath(path)
    # Remove leading slashes and traversal
    while clean.startswith(("/", "..", "./", "../")):
        clean = clean.lstrip("/")
        if clean.startswith(".."):
            clean = clean[2:].lstrip("/")
    return clean


def get_language_bar(languages: dict) -> str:
    """Build a language breakdown string."""
    if not languages:
        return "Unknown"
    total = sum(languages.values())
    parts = []
    for lang, count in sorted(languages.items(),
                               key=lambda x: x[1], reverse=True)[:4]:
        pct = (count / total) * 100
        parts.append(f"{lang} {pct:.0f}%")
    return "  •  ".join(parts)
