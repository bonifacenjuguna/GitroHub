import io
import logging
import zipfile
import tempfile
import os
import base64
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_active_session, set_state, clear_state
from utils.github_helper import (
    get_github_client, get_error_message,
    format_size, format_time_ago, get_language_bar
)
from handlers.core import escape_md
from github import GithubException

logger = logging.getLogger(__name__)


# ── Stats ─────────────────────────────────────────────────────────────────────

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo. Use /use first.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        languages = repo.get_languages()
        lang_bar = get_language_bar(languages)

        # Commit count
        commits = repo.get_commits()
        total_commits = commits.totalCount

        # Contributor stats for most committed files
        try:
            contrib_stats = list(repo.get_stats_contributors() or [])
        except Exception:
            contrib_stats = []

        # Calculate streak (days with commits in last 30)
        from datetime import datetime, timezone, timedelta
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_commits = list(repo.get_commits(since=thirty_days_ago))
        commit_days = set(c.commit.author.date.date() for c in recent_commits)
        streak = 0
        today = datetime.now(timezone.utc).date()
        for i in range(30):
            day = today - timedelta(days=i)
            if day in commit_days:
                streak += 1
            else:
                if i > 0:
                    break

        text = (
            f"📊 *{escape_md(repo.name)} — Stats*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 {escape_md(format_size(repo.size))}  "
            f"•  📝 {total_commits} commits  "
            f"•  🔥 {streak} day streak\n"
            f"⭐ {repo.stargazers_count} stars  "
            f"•  🍴 {repo.forks_count} forks\n\n"
            f"🌍 *Languages:*\n{escape_md(lang_bar)}\n\n"
        )

        # Top contributors
        if contrib_stats:
            contrib_stats.sort(key=lambda x: x.total, reverse=True)
            text += "👥 *Top contributors:*\n"
            for c in contrib_stats[:3]:
                text += f"• {escape_md(c.author.login)}  →  {c.total} commits\n"
            text += "\n"

        text += f"📅 Created: {repo.created_at.strftime('%b %Y')}\n"
        text += f"🔄 Updated: {escape_md(format_time_ago(repo.updated_at))}"

        keyboard = [[
            InlineKeyboardButton("👁 Traffic", callback_data="traffic"),
            InlineKeyboardButton("⭐ Stargazers", callback_data="stargazers"),
            InlineKeyboardButton("👥 Contributors", callback_data="contributors"),
        ], [
            InlineKeyboardButton("⬅️ Back", callback_data="home")
        ]]

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    gh = get_github_client(telegram_id)
    session = get_active_session(telegram_id)
    if not gh:
        await update.message.reply_text("❌ Not logged in.")
        return

    try:
        user = gh.get_user()
        repos = list(user.get_repos())
        public_repos = sum(1 for r in repos if not r.private)
        total_stars = sum(r.stargazers_count for r in repos)

        # Top language
        lang_count = {}
        for repo in repos:
            if repo.language:
                lang_count[repo.language] = lang_count.get(repo.language, 0) + 1
        top_lang = max(lang_count, key=lang_count.get) if lang_count else "Unknown"

        text = (
            f"👤 *{escape_md(user.login)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 {user.public_repos} public repos\n"
            f"⭐ {total_stars} stars received\n"
            f"👥 {user.followers} followers  "
            f"•  {user.following} following\n"
            f"🏆 Top language: {escape_md(top_lang)}\n"
            f"📅 Joined: {user.created_at.strftime('%b %Y')}\n"
        )

        if user.bio:
            text += f"\n📝 {escape_md(user.bio)}\n"
        if user.company:
            text += f"🏢 {escape_md(user.company)}\n"
        if user.location:
            text += f"📍 {escape_md(user.location)}\n"

        keyboard = [[
            InlineKeyboardButton("📦 My Repos", callback_data="repos"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ]]

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def cmd_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        views = repo.get_views_traffic()
        clones = repo.get_clones_traffic()

        text = (
            f"👁 *Traffic — {escape_md(repo.name)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"*Views \\(last 14 days\\):*\n"
            f"Total: {views.get('count', 0)}\n"
            f"Unique: {views.get('uniques', 0)}\n\n"
            f"*Clones \\(last 14 days\\):*\n"
            f"Total: {clones.get('count', 0)}\n"
            f"Unique: {clones.get('uniques', 0)}\n"
        )

        keyboard = [[
            InlineKeyboardButton("📊 Full Stats", callback_data="stats"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ]]

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def cmd_contributors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        contributors = list(repo.get_contributors())[:15]
        username = session["github_username"]

        text = (
            f"👥 *Contributors — {escape_md(repo.name)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for i, contrib in enumerate(contributors):
            you = " \\(you\\)" if contrib.login == username else ""
            text += f"{i+1}\\. *{escape_md(contrib.login)}*{you}  →  {contrib.contributions} commits\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"👤 {contrib.login}",
                    url=f"https://github.com/{contrib.login}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton("📊 Stats", callback_data="stats"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ])

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def cmd_stargazers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        stargazers = list(repo.get_stargazers())[:10]

        text = (
            f"⭐ *Stargazers — {escape_md(repo.name)}*\n"
            f"Total: {repo.stargazers_count} stars\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        for sg in stargazers:
            text += f"• [{escape_md(sg.login)}](https://github.com/{sg.login})\n"

        if repo.stargazers_count > 10:
            text += f"\n_\\.\\.\\. and {repo.stargazers_count - 10} more_"

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


# ── Download ──────────────────────────────────────────────────────────────────

async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)

    if context.args:
        target = context.args[0]
        await do_download(update.message, telegram_id, target, context)
        return

    if not session or not session.get("active_repo"):
        await update.message.reply_text(
            "Usage: /download <repo> or /download <user/repo> or /download <URL>"
        )
        return

    # Download active repo
    await do_download(update.message, telegram_id,
                      session["active_repo"], context)


async def do_download(message, telegram_id: int, target: str, context):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)

    # Parse target
    if target.startswith("https://github.com/"):
        repo_name = target.replace("https://github.com/", "").rstrip("/")
    else:
        repo_name = target
        if "/" not in repo_name and session:
            repo_name = f"{session['github_username']}/{repo_name}"

    await message.reply_text(
        f"⏳ *Packaging* `{escape_md(repo_name)}`\\.\\.\\.",
        parse_mode="MarkdownV2"
    )

    try:
        repo = gh.get_repo(repo_name)

        # Size check
        size_mb = repo.size / 1024
        if size_mb > 500:
            await message.reply_text(
                f"⚠️ *Large repo detected*\n"
                f"Size: {size_mb:.0f} MB\n\n"
                f"This may take a while and could exceed Telegram's 50MB limit\\.\n"
                f"Continue anyway?",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Continue",
                        callback_data=f"dl_{repo_name}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel")
                ]])
            )
            return

        branch = repo.default_branch
        is_own = session and repo.owner.login == session.get("github_username")

        # Download as ZIP via GitHub API
        import aiohttp
        zip_url = f"https://api.github.com/repos/{repo_name}/zipball/{branch}"
        token = None
        if session:
            from utils.encryption import decrypt
            from database.db import get_active_session
            s = get_active_session(telegram_id)
            token = decrypt(s["encrypted_token"])

        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(zip_url, headers=headers) as resp:
                if resp.status != 200:
                    await message.reply_text(
                        f"❌ *Download failed*\n"
                        f"Reason: GitHub returned status {resp.status}\\.\n\n"
                        f"Fix: Check repo name and try again\\.",
                        parse_mode="MarkdownV2"
                    )
                    return

                content = await resp.read()

        zip_name = f"{repo_name.replace('/', '-')}.zip"
        zip_bytes = io.BytesIO(content)
        zip_bytes.name = zip_name
        size_actual = len(content) / (1024 * 1024)

        # Telegram limit check
        if size_actual > 50:
            await message.reply_text(
                f"⚠️ *ZIP exceeds 50MB*\n"
                f"Size: {size_actual:.1f} MB\n\n"
                f"Reason: Telegram limits file uploads to 50MB\\.\n"
                f"Fix: Consider downloading specific folders instead\\.",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("📂 Browse repo", callback_data="browse"),
                    InlineKeyboardButton("🏠 Home", callback_data="home"),
                ]])
            )
            return

        caption = (
            f"📦 *{escape_md(repo.name)}*\n"
            f"{'🔒 Private' if repo.private else '🌍 Public'}  •  "
            f"{escape_md(repo.language or '?')}  •  "
            f"⭐ {repo.stargazers_count}\n"
            f"Branch: `{escape_md(branch)}`\n"
            f"Size: {size_actual:.1f} MB"
        )

        keyboard = [[
            InlineKeyboardButton("📂 Add to Projects",
                callback_data=f"open_repo_{repo_name}") if not is_own else
            InlineKeyboardButton("📂 Open Project",
                callback_data=f"open_repo_{repo_name}"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ]]

        await message.reply_document(
            document=zip_bytes,
            filename=zip_name,
            caption=caption,
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        if e.status == 404:
            await message.reply_text(
                f"❌ *Repo not found*\n"
                f"Reason: `{escape_md(repo_name)}` doesn't exist or is private\\.\n\n"
                f"Fix: Check the name or URL and try again\\.",
                parse_mode="MarkdownV2"
            )
        else:
            await message.reply_text(get_error_message(e.status))


# ── Issues ────────────────────────────────────────────────────────────────────

async def cmd_issues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        issues = list(repo.get_issues(state="open"))[:10]

        if not issues:
            await update.message.reply_text(
                f"📝 *No open issues* in `{escape_md(session['active_repo'])}`\n\n"
                f"Everything is clean\\! 🎉",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Create Issue",
                        callback_data="create_issue"),
                    InlineKeyboardButton("🏠 Home", callback_data="home"),
                ]])
            )
            return

        text = (
            f"📝 *Open Issues — {escape_md(repo.name)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for issue in issues:
            when = format_time_ago(issue.created_at)
            text += f"#{issue.number} {escape_md(issue.title[:40])}\n"
            text += f"    {escape_md(when)}\n\n"
            keyboard.append([
                InlineKeyboardButton(f"#{issue.number} Close",
                    callback_data=f"close_issue_{issue.number}"),
                InlineKeyboardButton("🔗 View",
                    url=issue.html_url),
            ])

        keyboard.append([
            InlineKeyboardButton("➕ New Issue", callback_data="create_issue"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ])

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


# ── Releases ──────────────────────────────────────────────────────────────────

async def cmd_releases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await update.message.reply_text("❌ No active repo.")
        return

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        releases = list(repo.get_releases())[:5]

        if not releases:
            await update.message.reply_text(
                f"🚀 *No releases yet* in `{escape_md(session['active_repo'])}`",
                parse_mode="MarkdownV2",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Create Release",
                        callback_data="create_release"),
                    InlineKeyboardButton("🏠 Home", callback_data="home"),
                ]])
            )
            return

        text = (
            f"🚀 *Releases — {escape_md(repo.name)}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )

        keyboard = []
        for release in releases:
            pre = "🔖 Pre-release" if release.prerelease else "🚀 Release"
            when = format_time_ago(release.created_at)
            text += (
                f"{pre} `{escape_md(release.tag_name)}`\n"
                f"{escape_md(release.title or release.tag_name)}\n"
                f"{escape_md(when)}\n\n"
            )
            keyboard.append([
                InlineKeyboardButton(f"🔗 {release.tag_name}", url=release.html_url),
                InlineKeyboardButton("🗑️ Delete",
                    callback_data=f"delete_release_{release.id}"),
            ])

        keyboard.append([
            InlineKeyboardButton("➕ New Release", callback_data="create_release"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ])

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


# ── Stars ─────────────────────────────────────────────────────────────────────

async def cmd_star(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /star <user/repo>")
        return

    repo_name = context.args[0]
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(repo_name)
        gh.get_user().add_to_starred(repo)
        await update.message.reply_text(
            f"⭐ *Starred\\!*\n`{escape_md(repo_name)}`",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔗 View repo", url=repo.html_url),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def cmd_unstar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /unstar <user/repo>")
        return

    repo_name = context.args[0]
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(repo_name)
        gh.get_user().remove_from_starred(repo)
        await update.message.reply_text(
            f"✅ *Unstarred* `{escape_md(repo_name)}`",
            parse_mode="MarkdownV2"
        )
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


async def cmd_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    gh = get_github_client(telegram_id)
    try:
        user = gh.get_user()
        starred = list(user.get_starred())[:10]

        text = "⭐ *Your Starred Repos*\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []

        for repo in starred:
            text += (
                f"• *{escape_md(repo.full_name)}*\n"
                f"  ⭐ {repo.stargazers_count}  •  "
                f"{escape_md(repo.language or '?')}\n\n"
            )
            keyboard.append([
                InlineKeyboardButton(repo.name, url=repo.html_url),
                InlineKeyboardButton("⬇️ Download",
                    callback_data=f"dl_{repo.full_name}"),
            ])

        keyboard.append([
            InlineKeyboardButton("🏠 Home", callback_data="home")
        ])

        await update.message.reply_text(
            text, parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))


# ── Clone ─────────────────────────────────────────────────────────────────────

async def cmd_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text(
            "Usage: /clone <user/repo> or /clone <github URL>"
        )
        return

    target = context.args[0]
    if target.startswith("https://github.com/"):
        repo_name = target.replace("https://github.com/", "").rstrip("/")
    else:
        repo_name = target

    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(repo_name)

        keyboard = [[
            InlineKeyboardButton("📂 Add to Projects",
                callback_data=f"open_repo_{repo_name}"),
            InlineKeyboardButton("⬇️ Download as ZIP",
                callback_data=f"dl_{repo_name}"),
        ], [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]]

        await update.message.reply_text(
            f"✅ *Found* `{escape_md(repo.full_name)}`\n\n"
            f"{'🔒 Private' if repo.private else '🌍 Public'}  •  "
            f"{escape_md(repo.language or '?')}  •  "
            f"⭐ {repo.stargazers_count}\n\n"
            f"What do you want to do?",
            parse_mode="MarkdownV2",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status))
