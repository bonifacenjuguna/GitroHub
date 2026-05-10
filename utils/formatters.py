"""
UI Formatters — GitroHub v2.0
HTML escaping, bar charts, time formatting, box drawing.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
import random
import string


# ── HTML escape ───────────────────────────────────────────────────────────────

def h(text) -> str:
    """Escape text for Telegram HTML parse_mode."""
    if text is None:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


# ── Time formatting ───────────────────────────────────────────────────────────

def time_ago(dt: Optional[datetime]) -> str:
    if dt is None:
        return "never"
    if hasattr(dt, "tzinfo") and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = now - dt
    secs = int(diff.total_seconds())
    if secs < 60:
        return "just now"
    elif secs < 3600:
        m = secs // 60
        return f"{m}m ago"
    elif secs < 86400:
        hrs = secs // 3600
        return f"{hrs}h ago"
    elif secs < 604800:
        days = diff.days
        return f"{days}d ago"
    elif secs < 2592000:
        weeks = diff.days // 7
        return f"{weeks}w ago"
    elif secs < 31536000:
        months = diff.days // 30
        return f"{months}mo ago"
    else:
        return dt.strftime("%b %Y")


def format_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def format_uptime(seconds: int) -> str:
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    return " ".join(parts) if parts else "< 1m"


# ── Size formatting ───────────────────────────────────────────────────────────

def format_size(size_kb: int) -> str:
    if size_kb == 0:
        return "0 KB"
    if size_kb < 1024:
        return f"{size_kb} KB"
    if size_kb < 1048576:
        return f"{size_kb / 1024:.1f} MB"
    return f"{size_kb / 1048576:.1f} GB"


def format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1048576:
        return f"{size_bytes / 1024:.1f} KB"
    if size_bytes < 1073741824:
        return f"{size_bytes / 1048576:.1f} MB"
    return f"{size_bytes / 1073741824:.1f} GB"


# ── Bar chart ─────────────────────────────────────────────────────────────────

def bar(value: float, total: float, width: int = 8) -> str:
    """Unicode bar chart. Returns filled + empty blocks."""
    if total == 0:
        return "░" * width
    filled = round((value / total) * width)
    filled = max(0, min(width, filled))
    return "▇" * filled + "░" * (width - filled)


def mini_bar(commits_per_day: list[int]) -> str:
    """7-bar sparkline for weekly activity."""
    chars = " ▁▂▃▄▅▆▇"
    if not commits_per_day:
        return "░" * 7
    max_val = max(commits_per_day) or 1
    result = []
    for val in commits_per_day[-7:]:
        idx = round((val / max_val) * (len(chars) - 1))
        result.append(chars[idx])
    return "".join(result)


# ── Language bar ──────────────────────────────────────────────────────────────

def language_bars(languages: dict, max_langs: int = 4) -> str:
    if not languages:
        return "  Unknown"
    total = sum(languages.values())
    lines = []
    for lang, count in sorted(
        languages.items(), key=lambda x: x[1], reverse=True
    )[:max_langs]:
        pct = (count / total) * 100
        b = bar(count, total, width=7)
        lines.append(f"  {h(lang):<12}  {pct:4.1f}%  {b}")
    return "\n".join(lines)


# ── Commit message auto-generator ─────────────────────────────────────────────

def auto_commit_message(
    new_files: list = None,
    modified_files: list = None,
    deleted_files: list = None,
    path: str = None,
) -> str:
    """Always generates a meaningful commit message — never empty."""
    new_files = new_files or []
    modified_files = modified_files or []
    deleted_files = deleted_files or []

    parts = []

    if path:
        fname = path.split("/")[-1]
        ext = fname.rsplit(".", 1)[-1] if "." in fname else ""
        verb = _verb_for_extension(ext)
        parts.append(f"{verb} {fname}")

    if new_files and not path:
        names = [f.split("/")[-1] for f in new_files[:2]]
        joined = ", ".join(names)
        suffix = f" and {len(new_files) - 2} more" if len(new_files) > 2 else ""
        parts.append(f"Add {joined}{suffix}")

    if modified_files and not path:
        names = [f.split("/")[-1] for f in modified_files[:2]]
        joined = ", ".join(names)
        suffix = f" and {len(modified_files) - 2} more" if len(modified_files) > 2 else ""
        parts.append(f"Update {joined}{suffix}")

    if deleted_files:
        names = [f.split("/")[-1] for f in deleted_files[:2]]
        joined = ", ".join(names)
        parts.append(f"Remove {joined}")

    if parts:
        return "; ".join(parts)

    # Guaranteed fallback — always generates
    tag = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"Update files [{tag}]"


def _verb_for_extension(ext: str) -> str:
    mapping = {
        "py": "Update", "js": "Update", "ts": "Update",
        "jsx": "Update", "tsx": "Update", "vue": "Update",
        "go": "Update", "rs": "Update", "java": "Update",
        "md": "Update docs for", "txt": "Update",
        "json": "Update config", "yaml": "Update config",
        "yml": "Update config", "toml": "Update config",
        "env": "Update env", "gitignore": "Update gitignore",
        "css": "Update styles for", "scss": "Update styles for",
        "html": "Update template", "sql": "Update schema",
        "sh": "Update script", "dockerfile": "Update Dockerfile",
        "lock": "Update lockfile",
    }
    return mapping.get(ext.lower(), "Update")


# ── Box drawing panels ────────────────────────────────────────────────────────

def panel(title: str, lines: list[str], width: int = 34) -> str:
    """
    Build a box-drawing panel.
    lines is list of strings OR tuples (label, value) for aligned rows.
    Special markers:
      "---" → ╠══╣ divider
      "···" → ├──┤ light divider
      str   → full-width content line
      (k,v) → "  k    v" aligned row
    """
    inner = width - 2  # inside the borders

    def top() -> str:
        return f"╔{'═' * inner}╗"

    def bot() -> str:
        return f"╚{'═' * inner}╝"

    def hdiv() -> str:
        return f"╠{'═' * inner}╣"

    def ldiv() -> str:
        return f"├{'─' * inner}┤"

    def row(text: str) -> str:
        # Truncate if too long
        if len(text) > inner:
            text = text[:inner - 1] + "…"
        return f"║{text:<{inner}}║"

    def kv_row(key: str, val: str) -> str:
        # "  key          val"
        key_part = f"  {key}"
        val_part = str(val)
        space = inner - len(key_part) - len(val_part)
        if space < 1:
            space = 1
            val_part = val_part[:inner - len(key_part) - 1]
        return f"║{key_part}{' ' * space}{val_part}║"

    # Title row — centered
    title_text = f"  {title}"
    result = [top(), row(title_text)]

    for line in lines:
        if line == "---":
            result.append(hdiv())
        elif line == "···":
            result.append(ldiv())
        elif isinstance(line, tuple) and len(line) == 2:
            result.append(kv_row(str(line[0]), str(line[1])))
        else:
            result.append(row(f"  {line}"))

    result.append(bot())
    return "\n".join(result)


# ── Status indicators ─────────────────────────────────────────────────────────

def status_dot(value: float, warn_threshold: float = 70,
               crit_threshold: float = 90) -> str:
    if value >= crit_threshold:
        return "🔴"
    if value >= warn_threshold:
        return "🟡"
    return "🟢"


def bool_status(active: bool) -> str:
    return "🟢" if active else "🔴"


def on_off(value: bool) -> str:
    return "✅  On" if value else "🔕  Off"


# ── Visibility ────────────────────────────────────────────────────────────────

def vis_icon(is_private: bool) -> str:
    return "🔒" if is_private else "🌍"


def vis_label(is_private: bool) -> str:
    return "🔒  Private" if is_private else "🌍  Public"


# ── Truncation ────────────────────────────────────────────────────────────────

def truncate(text: str, max_len: int = 40, suffix: str = "…") -> str:
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix


# ── Breadcrumb ────────────────────────────────────────────────────────────────

def breadcrumb(repo_name: str, path: str = "", branch: str = "main") -> str:
    short_repo = repo_name.split("/")[-1] if "/" in repo_name else repo_name
    parts = [short_repo]
    if path:
        parts.extend(path.rstrip("/").split("/"))
    crumb = "  ›  ".join(parts)
    return f"{crumb}  ·  🌿 {branch}"


# ── Diff formatting ───────────────────────────────────────────────────────────

def format_diff(diff_text: str, max_lines: int = 20) -> str:
    lines = diff_text.splitlines()
    result = []
    for line in lines:
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("@@"):
            result.append("  ─────────────────")
            continue
        if line.startswith("+"):
            result.append(f"  + {h(line[1:])}")
        elif line.startswith("-"):
            result.append(f"  - {h(line[1:])}")
        else:
            result.append(f"    {h(line[1:])}")

    if len(result) > max_lines:
        extra = len(result) - max_lines
        result = result[:max_lines]
        result.append(f"  … {extra} more lines")

    return "\n".join(result)


# ── Notification type labels ──────────────────────────────────────────────────

NOTIF_ICONS = {
    "star": "⭐",
    "fork": "🍴",
    "push": "📝",
    "pull_request": "🔀",
    "pull_request_review": "📋",
    "issues": "📝",
    "issue_comment": "💬",
    "release": "🚀",
    "workflow_run": "⚙️",
    "security_advisory": "🛡️",
    "dependabot_alert": "🛡️",
    "member": "👤",
    "create": "✨",
    "delete": "🗑️",
    "watch": "👀",
    "commit_comment": "💬",
}


def notif_icon(event_type: str) -> str:
    return NOTIF_ICONS.get(event_type, "🔔")


# ── PR/Issue state ────────────────────────────────────────────────────────────

def pr_state(state: str, draft: bool = False) -> str:
    if draft:
        return "⚫ Draft"
    mapping = {
        "open": "🟢 Open",
        "closed": "🔴 Closed",
        "merged": "🟣 Merged",
    }
    return mapping.get(state, state)


def issue_state(state: str) -> str:
    return "🟢 Open" if state == "open" else "🔴 Closed"


def workflow_state(conclusion: str) -> str:
    mapping = {
        "success": "✅",
        "failure": "❌",
        "cancelled": "⚪",
        "skipped": "⏭️",
        "timed_out": "⏰",
        "action_required": "⚠️",
        "in_progress": "🔄",
        "queued": "⏳",
        "waiting": "⏳",
        "neutral": "⚪",
    }
    return mapping.get(conclusion or "queued", "❓")
