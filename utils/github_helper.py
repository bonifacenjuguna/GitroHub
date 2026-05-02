"""GitHub API helpers — GitroHub v1.2"""
import base64
import difflib
import logging

from github import Github, GithubException

logger = logging.getLogger(__name__)


def h(text) -> str:
    """Escape for Telegram HTML parse_mode."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


GITHUB_ERRORS = {
    401: "❌ <b>GitHub rejected your credentials</b>\n<b>Reason:</b> Token expired or revoked.\n<b>Fix:</b> Use /login to reconnect.",
    403: "❌ <b>GitHub refused this action</b>\n<b>Reason:</b> No permission or token scope too narrow.\n<b>Fix:</b> Reconnect with /login.",
    404: "❌ <b>Not found on GitHub</b>\n<b>Reason:</b> Repo, file or branch doesn't exist.\n<b>Fix:</b> Check the name and try again.",
    409: "❌ <b>Commit conflict</b>\n<b>Reason:</b> File changed on GitHub since you last fetched it.\n<b>Fix:</b> Read the file first, then re-upload.",
    422: "❌ <b>GitHub rejected the data</b>\n<b>Reason:</b> Invalid name or duplicate branch.\n<b>Fix:</b> Use letters, numbers, hyphens only.",
    500: "❌ <b>GitHub internal error</b>\n<b>Reason:</b> GitHub's issue, not yours. Nothing changed.\n<b>Fix:</b> Wait and retry. Check githubstatus.com",
    503: "❌ <b>GitHub is down</b>\n<b>Reason:</b> Maintenance or outage.\n<b>Fix:</b> Check githubstatus.com",
}


def get_error_message(status: int) -> str:
    return GITHUB_ERRORS.get(
        status,
        f"❌ <b>GitHub API error ({status})</b>\n<b>Fix:</b> Try again in a moment."
    )


def get_github_client(telegram_id: int):
    from database.db import get_active_session
    from utils.encryption import decrypt
    session = get_active_session(telegram_id)
    if not session:
        return None
    token = decrypt(session["encrypted_token"])
    return Github(token)


def format_size(size_kb: int) -> str:
    if size_kb < 1024:
        return f"{size_kb} KB"
    return f"{size_kb / 1024:.1f} MB"


def format_time_ago(dt) -> str:
    if dt is None:
        return "unknown"
    from datetime import datetime, timezone
    if hasattr(dt, 'tzinfo') and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    days = diff.days
    if days == 0:
        hours = diff.seconds // 3600
        if hours == 0:
            mins = diff.seconds // 60
            return f"{mins}m ago"
        return f"{hours}h ago"
    elif days == 1:
        return "1 day ago"
    elif days < 7:
        return f"{days} days ago"
    elif days < 30:
        return f"{days // 7}w ago"
    return f"{days // 30}mo ago"


def get_language_bar(languages: dict) -> str:
    if not languages:
        return "Unknown"
    total = sum(languages.values())
    parts = []
    for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:4]:
        pct = (count / total) * 100
        parts.append(f"{lang} {pct:.0f}%")
    return "  •  ".join(parts)


def get_file_diff(old_content: str, new_content: str, filename: str = "") -> tuple:
    old_lines = old_content.splitlines()
    new_lines = new_content.splitlines()
    differ = difflib.unified_diff(old_lines, new_lines, fromfile=f"current/{filename}", tofile=f"new/{filename}", lineterm="")
    diff_lines = []
    changed = 0
    for line in differ:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            diff_lines.append("─────────────────")
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
    if len(diff_lines) > 25:
        diff_lines = diff_lines[:25] + [f"... {len(diff_lines)-25} more lines"]
    return "\n".join(diff_lines), changed


def build_tree(contents, changed_files=None, new_files=None, deleted_files=None) -> str:
    changed_files = changed_files or set()
    new_files = new_files or set()
    deleted_files = deleted_files or set()
    lines = []
    items = sorted(contents, key=lambda x: (x.type != "dir", x.name))
    for i, item in enumerate(items):
        connector = "└── " if i == len(items) - 1 else "├── "
        if item.type == "dir":
            lines.append(f"{connector}📁 {item.name}/")
        else:
            icon, suffix = "📄", ""
            if item.path in new_files:
                icon, suffix = "✨", " ← new"
            elif item.path in changed_files:
                icon, suffix = "🟡", " ← modified"
            elif item.path in deleted_files:
                icon, suffix = "🗑️", " ← deleted"
            lines.append(f"{connector}{icon} {item.name}{suffix}")
    return "\n".join(lines)


def is_sensitive_file(filename: str) -> bool:
    sensitive = {".env", ".env.local", ".env.production", ".env.development",
                 "secrets.json", "credentials.json", "id_rsa", "id_ed25519", ".pem", ".key"}
    name = filename.lower()
    return any(name == s or name.endswith(s) for s in sensitive)


def sanitize_path(path: str) -> str:
    import posixpath
    clean = posixpath.normpath(path.strip())
    while clean.startswith(("/", "..", "./", "../")):
        clean = clean.lstrip("/")
        if clean.startswith(".."):
            clean = clean[2:].lstrip("/")
    return clean
