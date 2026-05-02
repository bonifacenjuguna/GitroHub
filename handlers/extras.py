"""Stats, download, issues, releases, stars — GitroHub v1.2"""
import io
import logging

import aiohttp
from github import GithubException
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from database.db import clear_state, get_active_session, set_state
from utils.github_helper import format_size, format_time_ago, get_error_message, get_github_client, get_language_bar, h

logger = logging.getLogger(__name__)


# ── Each function accepts a `message` param so it works from both command & callback ──

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_stats(update.message, update.effective_user.id)


async def _send_stats(message, telegram_id: int):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo. Use /use first.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        languages = repo.get_languages()
        lang_bar = get_language_bar(languages)
        total_commits = repo.get_commits().totalCount
        from datetime import datetime, timezone, timedelta
        thirty_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent = list(repo.get_commits(since=thirty_ago))
        commit_days = set(c.commit.author.date.date() for c in recent)
        streak = 0
        today = datetime.now(timezone.utc).date()
        for i in range(30):
            if today - timedelta(days=i) in commit_days:
                streak += 1
            elif i > 0:
                break
        try:
            contribs = list(repo.get_stats_contributors() or [])
            contribs.sort(key=lambda x: x.total, reverse=True)
        except Exception:
            contribs = []

        text = (
            f"📊 <b>{h(repo.name)} — Stats</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📦 {h(format_size(repo.size))}  •  📝 {total_commits} commits  •  🔥 {streak} day streak\n"
            f"⭐ {repo.stargazers_count} stars  •  🍴 {repo.forks_count} forks\n\n"
            f"🌍 <b>Languages:</b>\n{h(lang_bar)}\n\n"
        )
        if contribs:
            text += "👥 <b>Top contributors:</b>\n"
            for c in contribs[:3]:
                text += f"• {h(c.author.login)}  →  {c.total} commits\n"
        text += f"\n📅 Created: {repo.created_at.strftime('%b %Y')}"
        await message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("👁 Traffic", callback_data="traffic"),
                InlineKeyboardButton("⭐ Stargazers", callback_data="stargazers"),
                InlineKeyboardButton("👥 Contributors", callback_data="contributors"),
            ], [InlineKeyboardButton("⬅️ Back", callback_data="home")]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_profile(update.message, update.effective_user.id)


async def _send_profile(message, telegram_id: int):
    gh = get_github_client(telegram_id)
    if not gh:
        await message.reply_text("❌ Not logged in.", parse_mode="HTML")
        return
    try:
        user = gh.get_user()
        repos = list(user.get_repos())
        total_stars = sum(r.stargazers_count for r in repos)
        lang_count = {}
        for r in repos:
            if r.language:
                lang_count[r.language] = lang_count.get(r.language, 0) + 1
        top_lang = max(lang_count, key=lang_count.get) if lang_count else "Unknown"
        text = (
            f"👤 <b>{h(user.login)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 {user.public_repos} public repos\n"
            f"⭐ {total_stars} stars received\n"
            f"👥 {user.followers} followers  •  {user.following} following\n"
            f"🏆 Top language: {h(top_lang)}\n"
            f"📅 Joined: {user.created_at.strftime('%b %Y')}\n"
        )
        if user.bio:
            text += f"\n📝 {h(user.bio)}\n"
        await message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📦 My Repos", callback_data="repos"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_traffic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_traffic(update.message, update.effective_user.id)


async def _send_traffic(message, telegram_id: int):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        views = repo.get_views_traffic()
        clones = repo.get_clones_traffic()
        text = (
            f"👁 <b>Traffic — {h(repo.name)}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Views (last 14 days):</b>\n"
            f"Total: {views.get('count', 0)}\nUnique: {views.get('uniques', 0)}\n\n"
            f"<b>Clones (last 14 days):</b>\n"
            f"Total: {clones.get('count', 0)}\nUnique: {clones.get('uniques', 0)}\n"
        )
        await message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_contributors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_contributors(update.message, update.effective_user.id)


async def _send_contributors(message, telegram_id: int):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        contributors = list(repo.get_contributors())[:15]
        username = session["github_username"]
        text = f"👥 <b>Contributors — {h(repo.name)}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []
        for i, c in enumerate(contributors):
            you = " (you)" if c.login == username else ""
            text += f"{i+1}. <b>{h(c.login)}</b>{you}  →  {c.contributions} commits\n"
            keyboard.append([InlineKeyboardButton(f"👤 {c.login}", url=f"https://github.com/{c.login}")])
        keyboard.append([InlineKeyboardButton("📊 Stats", callback_data="stats"), InlineKeyboardButton("🏠 Home", callback_data="home")])
        await message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_stargazers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_stargazers(update.message, update.effective_user.id)


async def _send_stargazers(message, telegram_id: int):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        stargazers = list(repo.get_stargazers())[:10]
        text = f"⭐ <b>Stargazers — {h(repo.name)}</b>\nTotal: {repo.stargazers_count}\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        for sg in stargazers:
            text += f"• <a href='https://github.com/{sg.login}'>{h(sg.login)}</a>\n"
        if repo.stargazers_count > 10:
            text += f"\n... and {repo.stargazers_count - 10} more"
        await message.reply_text(
            text, parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📊 Stats", callback_data="stats"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    session = get_active_session(telegram_id)
    if context.args:
        await do_download(update.message, telegram_id, context.args[0], context)
        return
    if not session or not session.get("active_repo"):
        await update.message.reply_text("Usage: /download &lt;repo&gt; or /download &lt;user/repo&gt; or /download &lt;URL&gt;", parse_mode="HTML")
        return
    await do_download(update.message, telegram_id, session["active_repo"], context)


async def do_download(message, telegram_id: int, target: str, context):
    session = get_active_session(telegram_id)
    gh = get_github_client(telegram_id)
    if target.startswith("https://github.com/"):
        repo_name = target.replace("https://github.com/", "").rstrip("/")
    else:
        repo_name = target
        if "/" not in repo_name and session:
            repo_name = f"{session['github_username']}/{repo_name}"
    await message.reply_text(f"⏳ <b>Packaging</b> <code>{h(repo_name)}</code>...", parse_mode="HTML")
    try:
        repo = gh.get_repo(repo_name)
        if repo.size / 1024 > 500:
            await message.reply_text(
                f"⚠️ <b>Large repo</b> ({repo.size//1024} MB)\nThis may exceed Telegram's 50MB limit.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Continue anyway", callback_data=f"dl_{repo_name}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]])
            )
            return
        branch = repo.default_branch
        token_header = {}
        if session:
            from utils.encryption import decrypt
            from database.db import get_active_session as gas
            s = gas(telegram_id)
            if s:
                token_header = {"Authorization": f"token {decrypt(s['encrypted_token'])}"}
        zip_url = f"https://api.github.com/repos/{repo_name}/zipball/{branch}"
        async with aiohttp.ClientSession() as http_session:
            async with http_session.get(zip_url, headers={**token_header, "Accept": "application/vnd.github.v3+json"}) as resp:
                if resp.status != 200:
                    await message.reply_text(f"❌ Download failed (status {resp.status}).", parse_mode="HTML")
                    return
                content = await resp.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > 50:
            await message.reply_text(
                f"⚠️ <b>ZIP too large</b> ({size_mb:.1f} MB)\nTelegram limits file uploads to 50MB.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📂 Browse instead", callback_data="browse")]])
            )
            return
        zip_name = f"{repo_name.replace('/', '-')}.zip"
        zip_bytes = io.BytesIO(content)
        zip_bytes.name = zip_name
        is_own = session and repo.owner.login == session.get("github_username")
        await message.reply_document(
            document=zip_bytes,
            filename=zip_name,
            caption=f"📦 <b>{h(repo.name)}</b>\n{'🔒 Private' if repo.private else '🌍 Public'}  •  {h(repo.language or '?')}  •  ⭐{repo.stargazers_count}\nSize: {size_mb:.1f} MB",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📂 Open Project", callback_data=f"open_repo_{repo_name}"),
                InlineKeyboardButton("🏠 Home", callback_data="home"),
            ]])
        )
    except GithubException as e:
        if e.status == 404:
            await message.reply_text("❌ <b>Repo not found</b>\nCheck the name or URL.", parse_mode="HTML")
        else:
            await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_issues(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_issues(update.message, update.effective_user.id)


async def _send_issues(message, telegram_id: int):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        issues = list(repo.get_issues(state="open"))[:10]
        if not issues:
            await message.reply_text(
                f"📝 <b>No open issues</b> in <code>{h(session['active_repo'])}</code> 🎉",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Create Issue", callback_data="create_issue"),
                    InlineKeyboardButton("🏠 Home", callback_data="home"),
                ]])
            )
            return
        text = f"📝 <b>Open Issues — {h(repo.name)}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []
        for issue in issues:
            text += f"#{issue.number} {h(issue.title[:40])}\n    {h(format_time_ago(issue.created_at))}\n\n"
            keyboard.append([
                InlineKeyboardButton(f"#{issue.number} Close", callback_data=f"close_issue_{issue.number}"),
                InlineKeyboardButton("🔗 View", url=issue.html_url),
            ])
        keyboard.append([
            InlineKeyboardButton("➕ New Issue", callback_data="create_issue"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ])
        await message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_releases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_releases(update.message, update.effective_user.id)


async def _send_releases(message, telegram_id: int):
    session = get_active_session(telegram_id)
    if not session or not session.get("active_repo"):
        await message.reply_text("❌ No active repo.", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(session["active_repo"])
        releases = list(repo.get_releases())[:5]
        if not releases:
            await message.reply_text(
                f"🚀 <b>No releases yet</b> in <code>{h(session['active_repo'])}</code>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("➕ Create Release", callback_data="create_release"),
                    InlineKeyboardButton("🏠 Home", callback_data="home"),
                ]])
            )
            return
        text = f"🚀 <b>Releases — {h(repo.name)}</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []
        for release in releases:
            pre = "🔖 Pre-release" if release.prerelease else "🚀 Release"
            text += f"{pre} <code>{h(release.tag_name)}</code>\n{h(release.title or release.tag_name)}\n{h(format_time_ago(release.created_at))}\n\n"
            keyboard.append([
                InlineKeyboardButton(f"🔗 {release.tag_name}", url=release.html_url),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_release_{release.id}"),
            ])
        keyboard.append([
            InlineKeyboardButton("➕ New Release", callback_data="create_release"),
            InlineKeyboardButton("🏠 Home", callback_data="home"),
        ])
        await message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except GithubException as e:
        await message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_star(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /star &lt;user/repo&gt;", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(context.args[0])
        gh.get_user().add_to_starred(repo)
        await update.message.reply_text(
            f"⭐ <b>Starred!</b>\n<code>{h(context.args[0])}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔗 View", url=repo.html_url), InlineKeyboardButton("🏠 Home", callback_data="home")]])
        )
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_unstar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /unstar &lt;user/repo&gt;", parse_mode="HTML")
        return
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(context.args[0])
        gh.get_user().remove_from_starred(repo)
        await update.message.reply_text(f"✅ Unstarred <code>{h(context.args[0])}</code>", parse_mode="HTML")
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_stars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    gh = get_github_client(telegram_id)
    try:
        starred = list(gh.get_user().get_starred())[:10]
        text = "⭐ <b>Your Starred Repos</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []
        for repo in starred:
            text += f"• <b>{h(repo.full_name)}</b>\n  ⭐{repo.stargazers_count}  •  {h(repo.language or '?')}\n\n"
            keyboard.append([
                InlineKeyboardButton(repo.name, url=repo.html_url),
                InlineKeyboardButton("⬇️ Download", callback_data=f"dl_{repo.full_name}"),
            ])
        keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /clone &lt;user/repo&gt; or /clone &lt;github URL&gt;", parse_mode="HTML")
        return
    target = context.args[0]
    repo_name = target.replace("https://github.com/", "").rstrip("/") if target.startswith("https://") else target
    gh = get_github_client(telegram_id)
    try:
        repo = gh.get_repo(repo_name)
        await update.message.reply_text(
            f"✅ <b>Found</b> <code>{h(repo.full_name)}</code>\n\n"
            f"{'🔒 Private' if repo.private else '🌍 Public'}  •  {h(repo.language or '?')}  •  ⭐{repo.stargazers_count}\n\n"
            f"What do you want to do?",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📂 Add to Projects", callback_data=f"open_repo_{repo_name}"),
                InlineKeyboardButton("⬇️ Download as ZIP", callback_data=f"dl_{repo_name}"),
            ], [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])
        )
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")


async def cmd_gists(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    gh = get_github_client(telegram_id)
    try:
        gists = list(gh.get_user().get_gists())[:10]
        if not gists:
            await update.message.reply_text("📋 <b>No gists yet.</b>", parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Home", callback_data="home")]]))
            return
        text = "📋 <b>Your Gists</b>\n━━━━━━━━━━━━━━━━━━━━━\n\n"
        keyboard = []
        for gist in gists:
            desc = gist.description or "No description"
            text += f"• {h(desc[:40])}\n"
            keyboard.append([
                InlineKeyboardButton("🔗 View", url=gist.html_url),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_gist_{gist.id}"),
            ])
        keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    except GithubException as e:
        await update.message.reply_text(get_error_message(e.status), parse_mode="HTML")
