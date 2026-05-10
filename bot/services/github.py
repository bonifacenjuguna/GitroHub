"""
GitHub API Service — GitroHub v2.0
All GitHub operations. Uses PyGithub + aiohttp for async HTTP.
Parallel calls via asyncio.gather(). Redis caching on all reads.
"""
import asyncio
import base64
import logging
import secrets
import time
from typing import Any, Optional

import aiohttp
from github import Github, GithubException, UnknownObjectException

from bot.services.cache import (
    cache_get, cache_set, cache_delete, cache_delete_pattern,
    store_rate_limit, invalidate_repo_cache,
)
from config import settings
from utils.crypto import decrypt
from utils.formatters import auto_commit_message

logger = logging.getLogger(__name__)

# Shared aiohttp session — reused across all requests
_http_session: Optional[aiohttp.ClientSession] = None


async def init_http():
    global _http_session
    connector = aiohttp.TCPConnector(
        limit=50,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )
    _http_session = aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=15),
        headers={"Accept": "application/vnd.github.v3+json"},
    )
    logger.info("✅ HTTP session initialized")


async def close_http():
    global _http_session
    if _http_session:
        await _http_session.close()


def _http() -> aiohttp.ClientSession:
    if _http_session is None:
        raise RuntimeError("HTTP session not initialized")
    return _http_session


# ── Client factory ────────────────────────────────────────────────────────────

def _gh(token: str) -> Github:
    return Github(token, per_page=100)


def _token_from_session(session: dict) -> str:
    return decrypt(session["encrypted_token"])


# ── Rate limit tracking ───────────────────────────────────────────────────────

async def _track_rate_limit(gh: Github, telegram_id: int):
    try:
        rl = gh.get_rate_limit()
        await store_rate_limit(
            telegram_id,
            rl.core.remaining,
            rl.core.limit,
            rl.core.reset.timestamp(),
        )
    except Exception:
        pass


# ── OAuth ─────────────────────────────────────────────────────────────────────

def build_oauth_url(state: str, force_reauth: bool = False) -> str:
    """Build GitHub OAuth URL. force_reauth=True forces account picker."""
    params = (
        f"client_id={settings.github_client_id}"
        f"&redirect_uri={settings.github_redirect_uri}"
        f"&scope=repo,user,delete_repo,admin:repo_hook,gist"
        f"&state={state}"
    )
    if force_reauth:
        params += "&prompt=select_account&login="
    return f"https://github.com/login/oauth/authorize?{params}"


async def exchange_oauth_code(code: str) -> Optional[dict]:
    """Exchange OAuth code for access token."""
    async with _http().post(
        "https://github.com/login/oauth/access_token",
        json={
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
            "redirect_uri": settings.github_redirect_uri,
        },
        headers={"Accept": "application/json"},
    ) as resp:
        if resp.status != 200:
            return None
        data = await resp.json(content_type=None)
        return data if data.get("access_token") else None


async def get_github_user_info(token: str) -> Optional[dict]:
    """Fetch authenticated user info."""
    async with _http().get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        if resp.status != 200:
            return None
        return await resp.json(content_type=None)


# ── User / Profile ────────────────────────────────────────────────────────────

async def get_profile(session: dict, telegram_id: int) -> Optional[dict]:
    cached = await cache_get(telegram_id, "profile")
    if cached:
        return cached

    token = _token_from_session(session)
    gh = _gh(token)

    try:
        user = gh.get_user()
        repos = list(user.get_repos())
        total_stars = sum(r.stargazers_count for r in repos)

        lang_count: dict[str, int] = {}
        for repo in repos:
            if repo.language:
                lang_count[repo.language] = lang_count.get(repo.language, 0) + 1
        top_lang = max(lang_count, key=lang_count.get) if lang_count else None

        data = {
            "login": user.login,
            "name": user.name or "",
            "bio": user.bio or "",
            "company": user.company or "",
            "location": user.location or "",
            "blog": user.blog or "",
            "twitter_username": user.twitter_username or "",
            "email": user.email or "",
            "hireable": user.hireable,
            "public_repos": user.public_repos,
            "followers": user.followers,
            "following": user.following,
            "total_stars": total_stars,
            "top_language": top_lang,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "plan": user.plan.name if user.plan else "free",
            "avatar_url": user.avatar_url,
        }
        await cache_set(telegram_id, "profile", data, settings.ttl_profile)
        asyncio.create_task(_track_rate_limit(gh, telegram_id))
        return data
    except GithubException:
        return None


async def update_profile(session: dict, telegram_id: int, **kwargs) -> bool:
    """Update GitHub profile fields."""
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        user = gh.get_user()
        update_kwargs = {}
        field_map = {
            "name": "name", "bio": "bio", "company": "company",
            "location": "location", "blog": "blog",
            "twitter_username": "twitter_username",
            "hireable": "hireable",
        }
        for key, gh_key in field_map.items():
            if key in kwargs:
                update_kwargs[gh_key] = kwargs[key]
        if update_kwargs:
            user.edit(**update_kwargs)
        await cache_delete(telegram_id, "profile")
        return True
    except GithubException:
        return False


async def get_social_links(session: dict, telegram_id: int) -> list[dict]:
    """Get GitHub profile social links via REST API."""
    token = _token_from_session(session)
    cached = await cache_get(telegram_id, "social_links")
    if cached:
        return cached

    async with _http().get(
        f"https://api.github.com/users/{session['github_username']}/social_accounts",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        if resp.status == 200:
            data = await resp.json(content_type=None)
            await cache_set(telegram_id, "social_links", data, 120)
            return data
        return []


async def update_social_links(session: dict, telegram_id: int,
                               links: list[str]) -> bool:
    """Replace all social links."""
    token = _token_from_session(session)
    payload = [{"value": link} for link in links if link]
    async with _http().put(
        "https://api.github.com/user/social_accounts",
        headers={"Authorization": f"token {token}"},
        json={"socials": payload},
    ) as resp:
        success = resp.status in (200, 204)
        if success:
            await cache_delete(telegram_id, "social_links")
        return success


# ── Repositories ──────────────────────────────────────────────────────────────

async def get_repos(session: dict, telegram_id: int,
                    sort: str = "pushed", page: int = 0,
                    per_page: int = 5) -> dict:
    cache_key = f"repos:{sort}:{page}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached

    token = _token_from_session(session)
    gh = _gh(token)

    try:
        user = gh.get_user()
        all_repos = list(user.get_repos())

        if sort == "stars":
            all_repos.sort(key=lambda r: r.stargazers_count, reverse=True)
        elif sort == "size":
            all_repos.sort(key=lambda r: r.size, reverse=True)
        elif sort == "name":
            all_repos.sort(key=lambda r: r.name.lower())
        else:
            all_repos.sort(
                key=lambda r: (r.pushed_at or r.updated_at), reverse=True
            )

        total = len(all_repos)
        public = sum(1 for r in all_repos if not r.private)
        private = total - public
        start = page * per_page
        page_repos = all_repos[start: start + per_page]

        data = {
            "total": total,
            "public": public,
            "private": private,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "repos": [_serialize_repo(r) for r in page_repos],
        }
        await cache_set(telegram_id, cache_key, data, settings.ttl_repos)
        asyncio.create_task(_track_rate_limit(gh, telegram_id))
        return data
    except GithubException as e:
        return {"error": e.status}


async def get_repo_detail(session: dict, telegram_id: int,
                          repo_name: str) -> Optional[dict]:
    cache_key = f"repo:{repo_name}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached

    token = _token_from_session(session)
    gh = _gh(token)

    try:
        repo = gh.get_repo(repo_name)
        languages = repo.get_languages()

        # Parallel fetch
        open_issues_count = repo.open_issues_count
        data = {
            **_serialize_repo(repo),
            "languages": languages,
            "open_prs": 0,  # separate call if needed
            "open_issues": open_issues_count,
            "network_count": repo.network_count,
            "subscribers_count": repo.subscribers_count,
            "has_issues": repo.has_issues,
            "has_wiki": repo.has_wiki,
            "has_discussions": repo.has_discussions,
            "is_template": repo.is_template,
            "homepage": repo.homepage or "",
            "topics": repo.get_topics(),
        }
        await cache_set(telegram_id, cache_key, data, settings.ttl_repo_detail)
        return data
    except GithubException as e:
        return {"error": e.status}


def _serialize_repo(repo) -> dict:
    return {
        "full_name": repo.full_name,
        "name": repo.name,
        "private": repo.private,
        "language": repo.language or "",
        "size": repo.size,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "default_branch": repo.default_branch,
        "description": repo.description or "",
        "pushed_at": repo.pushed_at.isoformat() if repo.pushed_at else None,
        "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
        "created_at": repo.created_at.isoformat() if repo.created_at else None,
        "html_url": repo.html_url,
        "clone_url": repo.clone_url,
        "archived": repo.archived,
        "disabled": repo.disabled,
        "owner_login": repo.owner.login,
        "open_issues_count": repo.open_issues_count,
        "watchers": repo.watchers_count,
    }


async def create_repo(session: dict, telegram_id: int, name: str,
                      private: bool = True, readme: bool = True,
                      gitignore: str = None, license_key: str = None,
                      description: str = "") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        user = gh.get_user()
        kwargs: dict[str, Any] = {
            "private": private,
            "auto_init": readme,
            "description": description,
        }
        if gitignore:
            kwargs["gitignore_template"] = gitignore
        if license_key and license_key != "none":
            kwargs["license_template"] = license_key
        repo = user.create_repo(name, **kwargs)
        await invalidate_repo_cache(telegram_id)
        return {"success": True, "repo": _serialize_repo(repo)}
    except GithubException as e:
        return {"error": e.status, "message": str(e)}


async def delete_repo(session: dict, telegram_id: int,
                      repo_name: str) -> bool:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.delete()
        await invalidate_repo_cache(telegram_id, repo_name)
        return True
    except GithubException:
        return False


async def rename_repo(session: dict, telegram_id: int,
                      repo_name: str, new_name: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.edit(name=new_name)
        await invalidate_repo_cache(telegram_id, repo_name)
        owner = repo_name.split("/")[0]
        return {"success": True, "new_full_name": f"{owner}/{new_name}"}
    except GithubException as e:
        return {"error": e.status}


async def set_repo_visibility(session: dict, telegram_id: int,
                               repo_name: str, private: bool) -> bool:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.edit(private=private)
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return True
    except GithubException:
        return False


async def set_repo_topics(session: dict, telegram_id: int,
                           repo_name: str, topics: list[str]) -> bool:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.replace_topics(topics)
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return True
    except GithubException:
        return False


async def set_repo_details(session: dict, telegram_id: int,
                            repo_name: str, **kwargs) -> bool:
    """Update description, homepage, etc."""
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.edit(**kwargs)
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return True
    except GithubException:
        return False


async def archive_repo(session: dict, telegram_id: int,
                        repo_name: str) -> bool:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.edit(archived=True)
        await invalidate_repo_cache(telegram_id, repo_name)
        return True
    except GithubException:
        return False


async def make_template_repo(session: dict, telegram_id: int,
                              repo_name: str) -> bool:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.edit(is_template=True)
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return True
    except GithubException:
        return False


async def transfer_repo(session: dict, telegram_id: int,
                         repo_name: str, new_owner: str) -> bool:
    token = _token_from_session(session)
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/transfer",
        headers={"Authorization": f"token {token}"},
        json={"new_owner": new_owner},
    ) as resp:
        success = resp.status in (200, 202)
        if success:
            await invalidate_repo_cache(telegram_id, repo_name)
        return success


async def get_repo_traffic(session: dict, telegram_id: int,
                            repo_name: str) -> dict:
    cache_key = f"traffic:{repo_name}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        views, clones = await asyncio.gather(
            asyncio.to_thread(lambda: repo.get_views_traffic()),
            asyncio.to_thread(lambda: repo.get_clones_traffic()),
        )
        data = {
            "views_count": views.get("count", 0),
            "views_uniques": views.get("uniques", 0),
            "clones_count": clones.get("count", 0),
            "clones_uniques": clones.get("uniques", 0),
        }
        await cache_set(telegram_id, cache_key, data, 300)
        return data
    except GithubException as e:
        return {"error": e.status}


async def get_contributors(session: dict, telegram_id: int,
                            repo_name: str) -> list[dict]:
    cache_key = f"contributors:{repo_name}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        contribs = list(repo.get_contributors())[:20]
        data = [
            {"login": c.login, "contributions": c.contributions,
             "avatar_url": c.avatar_url}
            for c in contribs
        ]
        await cache_set(telegram_id, cache_key, data, 300)
        return data
    except GithubException:
        return []


async def get_stargazers(session: dict, telegram_id: int,
                          repo_name: str, page: int = 0) -> dict:
    cache_key = f"stargazers:{repo_name}:{page}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        total = repo.stargazers_count
        stars = list(repo.get_stargazers())[page * 10: (page + 1) * 10]
        data = {
            "total": total,
            "page": page,
            "users": [{"login": s.login} for s in stars]
        }
        await cache_set(telegram_id, cache_key, data, 120)
        return data
    except GithubException as e:
        return {"error": e.status}


async def get_repo_stats(session: dict, telegram_id: int,
                          repo_name: str) -> dict:
    cache_key = f"stats:{repo_name}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached

    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)

        # Parallel fetch
        languages_task = asyncio.to_thread(lambda: repo.get_languages())
        commits_task = asyncio.to_thread(
            lambda: repo.get_commits().totalCount
        )
        languages, total_commits = await asyncio.gather(
            languages_task, commits_task
        )

        # Weekly activity (last 7 days)
        from datetime import datetime, timezone, timedelta
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent = list(repo.get_commits(since=week_ago))
        daily: dict[str, int] = {}
        for c in recent:
            day = c.commit.author.date.strftime("%a")
            daily[day] = daily.get(day, 0) + 1

        # Streak
        thirty_ago = datetime.now(timezone.utc) - timedelta(days=30)
        month_commits = list(repo.get_commits(since=thirty_ago))
        commit_days = set(c.commit.author.date.date() for c in month_commits)
        streak = 0
        today = datetime.now(timezone.utc).date()
        for i in range(30):
            if today - timedelta(days=i) in commit_days:
                streak += 1
            elif i > 0:
                break

        # Top committed files
        top_files: dict[str, int] = {}
        for c in list(repo.get_commits())[:50]:
            try:
                for f in c.files:
                    top_files[f.filename] = top_files.get(f.filename, 0) + 1
            except Exception:
                pass
        top_3 = sorted(top_files.items(), key=lambda x: x[1], reverse=True)[:3]

        data = {
            "total_commits": total_commits,
            "languages": languages,
            "streak": streak,
            "daily_activity": daily,
            "top_files": [{"path": p, "commits": c} for p, c in top_3],
            "stars": repo.stargazers_count,
            "forks": repo.forks_count,
            "size": repo.size,
            "open_issues": repo.open_issues_count,
        }
        await cache_set(telegram_id, cache_key, data, 300)
        return data
    except GithubException as e:
        return {"error": e.status}


# ── Files ─────────────────────────────────────────────────────────────────────

async def browse_files(session: dict, telegram_id: int,
                        repo_name: str, path: str = "",
                        branch: str = "main") -> dict:
    cache_key = f"files:{repo_name}:{branch}:{path}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached

    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        contents = repo.get_contents(path, ref=branch)
        if not isinstance(contents, list):
            contents = [contents]
        contents.sort(key=lambda x: (x.type != "dir", x.name.lower()))
        items = [
            {
                "name": c.name,
                "path": c.path,
                "type": c.type,
                "size": c.size,
                "sha": c.sha,
                "html_url": c.html_url,
            }
            for c in contents
        ]
        total_size = sum(c.size for c in contents if c.type == "file")
        data = {"items": items, "path": path, "total_size": total_size}
        await cache_set(telegram_id, cache_key, data, settings.ttl_files)
        return data
    except GithubException as e:
        return {"error": e.status}


async def read_file(session: dict, telegram_id: int,
                    repo_name: str, path: str,
                    branch: str = "main") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        fc = repo.get_contents(path, ref=branch)
        content = base64.b64decode(fc.content).decode("utf-8", errors="replace")
        return {"content": content, "sha": fc.sha, "size": fc.size,
                "html_url": fc.html_url, "path": path}
    except GithubException as e:
        return {"error": e.status}


async def commit_file(session: dict, telegram_id: int,
                       repo_name: str, path: str, content: str,
                       message: str, branch: str = "main",
                       sha: str = None) -> dict:
    """Create or update a single file."""
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        if sha:
            result = repo.update_file(path, message, content, sha, branch=branch)
        else:
            # Check if exists
            try:
                existing = repo.get_contents(path, ref=branch)
                result = repo.update_file(
                    path, message, content, existing.sha, branch=branch
                )
            except GithubException:
                result = repo.create_file(path, message, content, branch=branch)
        await cache_delete_pattern(telegram_id, f"files:{repo_name}")
        await cache_delete(telegram_id, f"repo:{repo_name}")
        commit_sha = result["commit"].sha[:7]
        return {"success": True, "sha": commit_sha}
    except GithubException as e:
        return {"error": e.status, "message": str(e)}


async def commit_multiple_files(session: dict, telegram_id: int,
                                  repo_name: str,
                                  files: dict[str, str],
                                  message: str,
                                  branch: str = "main") -> dict:
    """Commit multiple files. Returns summary."""
    token = _token_from_session(session)
    gh = _gh(token)
    committed, skipped, failed = 0, 0, 0
    try:
        repo = gh.get_repo(repo_name)
        for path, content in files.items():
            try:
                try:
                    existing = repo.get_contents(path, ref=branch)
                    old = base64.b64decode(existing.content).decode(
                        "utf-8", errors="replace"
                    )
                    if old == content:
                        skipped += 1
                        continue
                    repo.update_file(path, message, content,
                                     existing.sha, branch=branch)
                except GithubException as ge:
                    if ge.status == 404:
                        repo.create_file(path, message, content, branch=branch)
                    else:
                        raise
                committed += 1
            except Exception as e:
                logger.error(f"Failed to commit {path}: {e}")
                failed += 1
        await cache_delete_pattern(telegram_id, f"files:{repo_name}")
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return {"success": True, "committed": committed,
                "skipped": skipped, "failed": failed}
    except GithubException as e:
        return {"error": e.status}


async def commit_zip_files(session: dict, telegram_id: int,
                            repo_name: str,
                            file_map: dict[str, str],
                            new_files: list, modified_files: list,
                            deleted_files: list,
                            existing_sha: dict,
                            message: str,
                            branch: str = "main") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    committed, deleted_count, failed = 0, 0, 0
    try:
        repo = gh.get_repo(repo_name)
        for path in new_files + modified_files:
            content = file_map.get(path)
            if content is None:
                continue
            try:
                if path in existing_sha and path in modified_files:
                    repo.update_file(path, message, content,
                                     existing_sha[path], branch=branch)
                else:
                    repo.create_file(path, message, content, branch=branch)
                committed += 1
            except GithubException as e:
                logger.error(f"ZIP commit {path}: {e}")
                failed += 1
        for path in deleted_files:
            sha = existing_sha.get(path)
            if sha:
                try:
                    repo.delete_file(path, message, sha, branch=branch)
                    deleted_count += 1
                except GithubException as e:
                    logger.error(f"ZIP delete {path}: {e}")
                    failed += 1
        await cache_delete_pattern(telegram_id, f"files:{repo_name}")
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return {"success": True, "committed": committed,
                "deleted": deleted_count, "failed": failed}
    except GithubException as e:
        return {"error": e.status}


async def delete_file(session: dict, telegram_id: int,
                       repo_name: str, path: str,
                       branch: str = "main") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        fc = repo.get_contents(path, ref=branch)
        repo.delete_file(path, f"Delete {path}", fc.sha, branch=branch)
        await cache_delete_pattern(telegram_id, f"files:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def move_file(session: dict, telegram_id: int,
                     repo_name: str, src: str, dst: str,
                     branch: str = "main") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        fc = repo.get_contents(src, ref=branch)
        content = base64.b64decode(fc.content).decode("utf-8", errors="replace")
        repo.create_file(dst, f"Move {src} to {dst}", content, branch=branch)
        repo.delete_file(src, f"Move {src} to {dst}", fc.sha, branch=branch)
        await cache_delete_pattern(telegram_id, f"files:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def get_file_history(session: dict, telegram_id: int,
                            repo_name: str, path: str) -> list[dict]:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        commits = list(repo.get_commits(path=path))[:10]
        return [
            {
                "sha": c.sha[:7],
                "message": c.commit.message.split("\n")[0][:50],
                "author": c.commit.author.name,
                "date": c.commit.author.date.isoformat(),
            }
            for c in commits
        ]
    except GithubException:
        return []


async def search_code(session: dict, telegram_id: int,
                       repo_name: str, query: str) -> list[dict]:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        results = list(gh.search_code(f"{query} repo:{repo_name}"))[:10]
        return [{"name": r.name, "path": r.path, "url": r.html_url}
                for r in results]
    except GithubException:
        return []


# ── Branches ──────────────────────────────────────────────────────────────────

async def get_branches(session: dict, telegram_id: int,
                        repo_name: str) -> list[dict]:
    cache_key = f"branches:{repo_name}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        branches = list(repo.get_branches())
        data = [
            {
                "name": b.name,
                "protected": b.protected,
                "sha": b.commit.sha[:7],
            }
            for b in branches
        ]
        await cache_set(telegram_id, cache_key, data, settings.ttl_branches)
        return data
    except GithubException:
        return []


async def create_branch(session: dict, telegram_id: int,
                         repo_name: str, branch_name: str,
                         from_branch: str = "main") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        ref = repo.get_git_ref(f"heads/{from_branch}")
        repo.create_git_ref(f"refs/heads/{branch_name}", ref.object.sha)
        await cache_delete(telegram_id, f"branches:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def delete_branch(session: dict, telegram_id: int,
                         repo_name: str, branch_name: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        ref = repo.get_git_ref(f"heads/{branch_name}")
        ref.delete()
        await cache_delete(telegram_id, f"branches:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def merge_branch(session: dict, telegram_id: int,
                        repo_name: str, base: str, head: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        merge = repo.merge(base, head, f"Merge {head} into {base}")
        await cache_delete(telegram_id, f"branches:{repo_name}")
        if merge is None:
            return {"success": True, "nothing": True}
        return {"success": True, "sha": merge.sha[:7]}
    except GithubException as e:
        return {"error": e.status}


async def protect_branch(session: dict, telegram_id: int,
                          repo_name: str, branch_name: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        branch = repo.get_branch(branch_name)
        branch.edit_protection(
            required_approving_review_count=0,
            enforce_admins=False
        )
        await cache_delete(telegram_id, f"branches:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def compare_branches(session: dict, telegram_id: int,
                             repo_name: str, base: str,
                             head: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        comparison = repo.compare(base, head)
        files = list(comparison.files)[:10]
        return {
            "ahead_by": comparison.ahead_by,
            "behind_by": comparison.behind_by,
            "files": [
                {"filename": f.filename, "status": f.status,
                 "additions": f.additions, "deletions": f.deletions}
                for f in files
            ],
        }
    except GithubException as e:
        return {"error": e.status}


async def rename_branch(session: dict, telegram_id: int,
                         repo_name: str, old_name: str,
                         new_name: str) -> dict:
    token = _token_from_session(session)
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/branches/{old_name}/rename",
        headers={"Authorization": f"token {token}"},
        json={"new_name": new_name},
    ) as resp:
        if resp.status == 201:
            await cache_delete(telegram_id, f"branches:{repo_name}")
            return {"success": True}
        return {"error": resp.status}


async def set_default_branch(session: dict, telegram_id: int,
                               repo_name: str, branch: str) -> bool:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        repo.edit(default_branch=branch)
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return True
    except GithubException:
        return False


async def sync_fork(session: dict, telegram_id: int,
                     repo_name: str, branch: str = "main") -> dict:
    token = _token_from_session(session)
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/merge-upstream",
        headers={"Authorization": f"token {token}"},
        json={"branch": branch},
    ) as resp:
        if resp.status == 200:
            await cache_delete_pattern(telegram_id, f"commits:{repo_name}")
            return {"success": True}
        data = await resp.json(content_type=None)
        return {"error": resp.status, "message": data.get("message", "")}


# ── Commits ───────────────────────────────────────────────────────────────────

async def get_commits(session: dict, telegram_id: int,
                       repo_name: str, branch: str = "main",
                       page: int = 0, per_page: int = 8) -> dict:
    cache_key = f"commits:{repo_name}:{branch}:{page}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        all_commits = repo.get_commits(sha=branch)
        total = all_commits.totalCount
        start = page * per_page
        page_commits = list(all_commits)[start: start + per_page]
        data = {
            "total": total,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "commits": [
                {
                    "sha": c.sha,
                    "sha_short": c.sha[:7],
                    "message": c.commit.message.split("\n")[0][:60],
                    "author": c.commit.author.name,
                    "author_login": c.author.login if c.author else "",
                    "date": c.commit.author.date.isoformat(),
                    "html_url": c.html_url,
                }
                for c in page_commits
            ],
        }
        await cache_set(telegram_id, cache_key, data, settings.ttl_commits)
        return data
    except GithubException as e:
        return {"error": e.status}


async def get_commit_detail(session: dict, telegram_id: int,
                              repo_name: str, sha: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        commit = repo.get_commit(sha)
        files = list(commit.files)[:15]
        return {
            "sha": commit.sha,
            "sha_short": commit.sha[:7],
            "message": commit.commit.message.split("\n")[0],
            "full_message": commit.commit.message,
            "author": commit.commit.author.name,
            "date": commit.commit.author.date.isoformat(),
            "files": [
                {
                    "filename": f.filename,
                    "status": f.status,
                    "additions": f.additions,
                    "deletions": f.deletions,
                }
                for f in files
            ],
            "stats": {
                "additions": commit.stats.additions,
                "deletions": commit.stats.deletions,
                "total": commit.stats.total,
            },
            "html_url": commit.html_url,
        }
    except GithubException as e:
        return {"error": e.status}


async def revert_commit(session: dict, telegram_id: int,
                         repo_name: str, branch: str,
                         sha: str, parent_sha: str) -> dict:
    """Revert last commit by force-resetting to parent."""
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        ref = repo.get_git_ref(f"heads/{branch}")
        ref.edit(parent_sha, force=True)
        await cache_delete_pattern(telegram_id, f"commits:{repo_name}")
        await cache_delete(telegram_id, f"repo:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def reset_to_commit(session: dict, telegram_id: int,
                           repo_name: str, branch: str, sha: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        ref = repo.get_git_ref(f"heads/{branch}")
        ref.edit(sha, force=True)
        await cache_delete_pattern(telegram_id, f"commits:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


# ── Pull Requests ─────────────────────────────────────────────────────────────

async def get_pulls(session: dict, telegram_id: int,
                     repo_name: str, state: str = "open",
                     page: int = 0) -> dict:
    cache_key = f"pulls:{repo_name}:{state}:{page}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        all_pulls = list(repo.get_pulls(state=state))
        total = len(all_pulls)
        per_page = settings.pulls_per_page
        start = page * per_page
        data = {
            "total": total,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "pulls": [_serialize_pr(pr)
                      for pr in all_pulls[start: start + per_page]],
        }
        await cache_set(telegram_id, cache_key, data, 30)
        return data
    except GithubException as e:
        return {"error": e.status}


def _serialize_pr(pr) -> dict:
    return {
        "number": pr.number,
        "title": pr.title[:60],
        "state": pr.state,
        "draft": pr.draft,
        "user": pr.user.login,
        "head_ref": pr.head.ref,
        "base_ref": pr.base.ref,
        "created_at": pr.created_at.isoformat(),
        "updated_at": pr.updated_at.isoformat(),
        "html_url": pr.html_url,
        "mergeable": pr.mergeable,
        "merged": pr.merged,
        "comments": pr.comments,
        "review_comments": pr.review_comments,
    }


async def create_pull(session: dict, telegram_id: int,
                       repo_name: str, title: str,
                       head: str, base: str,
                       body: str = "") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        pr = repo.create_pull(title=title, body=body, head=head, base=base)
        await cache_delete_pattern(telegram_id, f"pulls:{repo_name}")
        return {"success": True, "number": pr.number, "url": pr.html_url}
    except GithubException as e:
        return {"error": e.status, "message": str(e)}


async def merge_pull(session: dict, telegram_id: int,
                      repo_name: str, pr_number: int,
                      merge_method: str = "merge") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        result = pr.merge(merge_method=merge_method)
        await cache_delete_pattern(telegram_id, f"pulls:{repo_name}")
        await cache_delete_pattern(telegram_id, f"commits:{repo_name}")
        return {"success": result.merged, "message": result.message}
    except GithubException as e:
        return {"error": e.status}


async def close_pull(session: dict, telegram_id: int,
                      repo_name: str, pr_number: int) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(pr_number)
        pr.edit(state="closed")
        await cache_delete_pattern(telegram_id, f"pulls:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


# ── Issues ────────────────────────────────────────────────────────────────────

async def get_issues(session: dict, telegram_id: int,
                      repo_name: str, state: str = "open",
                      page: int = 0) -> dict:
    cache_key = f"issues:{repo_name}:{state}:{page}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        all_issues = [i for i in repo.get_issues(state=state)
                      if i.pull_request is None]
        total = len(all_issues)
        per_page = settings.issues_per_page
        start = page * per_page
        data = {
            "total": total,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "issues": [
                {
                    "number": i.number,
                    "title": i.title[:60],
                    "state": i.state,
                    "user": i.user.login,
                    "labels": [la.name for la in i.labels],
                    "created_at": i.created_at.isoformat(),
                    "html_url": i.html_url,
                    "comments": i.comments,
                    "assignees": [a.login for a in i.assignees],
                }
                for i in all_issues[start: start + per_page]
            ],
        }
        await cache_set(telegram_id, cache_key, data, 30)
        return data
    except GithubException as e:
        return {"error": e.status}


async def create_issue(session: dict, telegram_id: int,
                        repo_name: str, title: str,
                        body: str = "") -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        issue = repo.create_issue(title=title, body=body)
        await cache_delete_pattern(telegram_id, f"issues:{repo_name}")
        return {"success": True, "number": issue.number, "url": issue.html_url}
    except GithubException as e:
        return {"error": e.status}


async def close_issue(session: dict, telegram_id: int,
                       repo_name: str, issue_number: int) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        issue.edit(state="closed")
        await cache_delete_pattern(telegram_id, f"issues:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def reopen_issue(session: dict, telegram_id: int,
                        repo_name: str, issue_number: int) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        issue.edit(state="open")
        await cache_delete_pattern(telegram_id, f"issues:{repo_name}")
        return {"success": True}
    except GithubException as e:
        return {"error": e.status}


async def comment_on_issue(session: dict, telegram_id: int,
                            repo_name: str, issue_number: int,
                            body: str) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        issue = repo.get_issue(issue_number)
        comment = issue.create_comment(body)
        return {"success": True, "id": comment.id}
    except GithubException as e:
        return {"error": e.status}


async def get_labels(session: dict, telegram_id: int,
                      repo_name: str) -> list[dict]:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        labels = list(repo.get_labels())
        return [{"name": la.name, "color": la.color,
                 "description": la.description or ""} for la in labels]
    except GithubException:
        return []


# ── Releases ──────────────────────────────────────────────────────────────────

async def get_releases(session: dict, telegram_id: int,
                        repo_name: str) -> list[dict]:
    cache_key = f"releases:{repo_name}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        releases = list(repo.get_releases())[:10]
        data = [
            {
                "id": r.id,
                "tag_name": r.tag_name,
                "name": r.title or r.tag_name,
                "body": r.body or "",
                "prerelease": r.prerelease,
                "draft": r.draft,
                "created_at": r.created_at.isoformat(),
                "assets_count": r.get_assets().totalCount,
                "html_url": r.html_url,
                "author": r.author.login if r.author else "",
            }
            for r in releases
        ]
        await cache_set(telegram_id, cache_key, data, 60)
        return data
    except GithubException:
        return []


async def create_release(session: dict, telegram_id: int,
                          repo_name: str, tag: str, name: str,
                          body: str = "", prerelease: bool = False,
                          draft: bool = False) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        release = repo.create_git_release(
            tag=tag, name=name, message=body,
            draft=draft, prerelease=prerelease,
        )
        await cache_delete(telegram_id, f"releases:{repo_name}")
        return {"success": True, "url": release.html_url}
    except GithubException as e:
        return {"error": e.status, "message": str(e)}


async def delete_release(session: dict, telegram_id: int,
                          repo_name: str, release_id: int) -> bool:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        release = repo.get_release(release_id)
        release.delete_release()
        await cache_delete(telegram_id, f"releases:{repo_name}")
        return True
    except GithubException:
        return False


# ── GitHub Actions ────────────────────────────────────────────────────────────

async def get_workflows(session: dict, telegram_id: int,
                         repo_name: str) -> list[dict]:
    cache_key = f"workflows:{repo_name}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    async with _http().get(
        f"https://api.github.com/repos/{repo_name}/actions/workflows",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json(content_type=None)
        workflows = data.get("workflows", [])
        result = [
            {
                "id": w["id"],
                "name": w["name"],
                "state": w["state"],
                "path": w["path"],
                "html_url": w["html_url"],
            }
            for w in workflows
        ]
        await cache_set(telegram_id, cache_key, result, 60)
        return result


async def get_workflow_runs(session: dict, telegram_id: int,
                             repo_name: str,
                             workflow_id: int = None) -> list[dict]:
    token = _token_from_session(session)
    url = f"https://api.github.com/repos/{repo_name}/actions/runs"
    if workflow_id:
        url = f"https://api.github.com/repos/{repo_name}/actions/workflows/{workflow_id}/runs"
    async with _http().get(
        url,
        headers={"Authorization": f"token {token}"},
        params={"per_page": 5},
    ) as resp:
        if resp.status != 200:
            return []
        data = await resp.json(content_type=None)
        runs = data.get("workflow_runs", [])
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "status": r["status"],
                "conclusion": r["conclusion"],
                "run_number": r["run_number"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "html_url": r["html_url"],
                "head_branch": r["head_branch"],
                "head_sha": r["head_sha"][:7],
            }
            for r in runs
        ]


async def trigger_workflow(session: dict, telegram_id: int,
                            repo_name: str, workflow_id: int,
                            ref: str = "main",
                            inputs: dict = None) -> bool:
    token = _token_from_session(session)
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/actions/workflows/{workflow_id}/dispatches",
        headers={"Authorization": f"token {token}"},
        json={"ref": ref, "inputs": inputs or {}},
    ) as resp:
        return resp.status == 204


async def cancel_workflow_run(session: dict, telegram_id: int,
                               repo_name: str, run_id: int) -> bool:
    token = _token_from_session(session)
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/actions/runs/{run_id}/cancel",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        return resp.status == 202


# ── Forks ─────────────────────────────────────────────────────────────────────

async def fork_repo(session: dict, telegram_id: int,
                     repo_name: str, organization: str = None) -> dict:
    token = _token_from_session(session)
    payload: dict[str, Any] = {}
    if organization:
        payload["organization"] = organization
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/forks",
        headers={"Authorization": f"token {token}"},
        json=payload,
    ) as resp:
        if resp.status == 202:
            data = await resp.json(content_type=None)
            await invalidate_repo_cache(telegram_id)
            return {"success": True, "full_name": data["full_name"],
                    "html_url": data["html_url"]}
        return {"error": resp.status}


async def get_my_forks(session: dict, telegram_id: int) -> list[dict]:
    cache_key = "forks:all"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        user = gh.get_user()
        forks = [r for r in user.get_repos() if r.fork]
        data = []
        for f in forks[:20]:
            parent = f.parent
            data.append({
                "full_name": f.full_name,
                "name": f.name,
                "parent_full_name": parent.full_name if parent else "",
                "parent_owner": parent.owner.login if parent else "",
                "pushed_at": f.pushed_at.isoformat() if f.pushed_at else None,
                "html_url": f.html_url,
                "default_branch": f.default_branch,
            })
        await cache_set(telegram_id, cache_key, data, 60)
        return data
    except GithubException:
        return []


async def get_repo_forks(session: dict, telegram_id: int,
                          repo_name: str, page: int = 0) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        total = repo.forks_count
        forks = list(repo.get_forks())[page * 10: (page + 1) * 10]
        return {
            "total": total,
            "page": page,
            "forks": [{"login": f.owner.login, "full_name": f.full_name,
                        "pushed_at": f.pushed_at.isoformat() if f.pushed_at else None}
                      for f in forks]
        }
    except GithubException as e:
        return {"error": e.status}


# ── Stars ─────────────────────────────────────────────────────────────────────

async def star_repo(session: dict, telegram_id: int,
                     repo_name: str) -> bool:
    token = _token_from_session(session)
    async with _http().put(
        f"https://api.github.com/user/starred/{repo_name}",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        return resp.status == 204


async def unstar_repo(session: dict, telegram_id: int,
                       repo_name: str) -> bool:
    token = _token_from_session(session)
    async with _http().delete(
        f"https://api.github.com/user/starred/{repo_name}",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        return resp.status == 204


async def get_starred_repos(session: dict, telegram_id: int,
                              page: int = 0) -> list[dict]:
    cache_key = f"starred:{page}"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        starred = list(gh.get_user().get_starred())[page * 10: (page + 1) * 10]
        data = [
            {
                "full_name": r.full_name,
                "name": r.name,
                "stars": r.stargazers_count,
                "language": r.language or "",
                "description": r.description or "",
                "html_url": r.html_url,
            }
            for r in starred
        ]
        await cache_set(telegram_id, cache_key, data, 120)
        return data
    except GithubException:
        return []


# ── Gists ─────────────────────────────────────────────────────────────────────

async def get_gists(session: dict, telegram_id: int) -> list[dict]:
    cache_key = "gists"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        gists = list(gh.get_user().get_gists())[:15]
        data = [
            {
                "id": g.id,
                "description": g.description or "No description",
                "files": list(g.files.keys())[:3],
                "public": g.public,
                "html_url": g.html_url,
                "created_at": g.created_at.isoformat(),
            }
            for g in gists
        ]
        await cache_set(telegram_id, cache_key, data, 60)
        return data
    except GithubException:
        return []


async def delete_gist(session: dict, telegram_id: int,
                       gist_id: str) -> bool:
    token = _token_from_session(session)
    async with _http().delete(
        f"https://api.github.com/gists/{gist_id}",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        if resp.status == 204:
            await cache_delete(telegram_id, "gists")
            return True
        return False


async def create_gist(session: dict, telegram_id: int,
                       filename: str, content: str,
                       description: str = "", public: bool = False) -> dict:
    token = _token_from_session(session)
    async with _http().post(
        "https://api.github.com/gists",
        headers={"Authorization": f"token {token}"},
        json={
            "description": description,
            "public": public,
            "files": {filename: {"content": content}},
        },
    ) as resp:
        if resp.status == 201:
            data = await resp.json(content_type=None)
            await cache_delete(telegram_id, "gists")
            return {"success": True, "url": data["html_url"], "id": data["id"]}
        return {"error": resp.status}


# ── Tags ──────────────────────────────────────────────────────────────────────

async def get_tags(session: dict, telegram_id: int,
                    repo_name: str) -> list[dict]:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        repo = gh.get_repo(repo_name)
        tags = list(repo.get_tags())[:10]
        return [
            {"name": t.name, "sha": t.commit.sha[:7],
             "html_url": f"https://github.com/{repo_name}/releases/tag/{t.name}"}
            for t in tags
        ]
    except GithubException:
        return []


# ── Security ──────────────────────────────────────────────────────────────────

async def get_dependabot_alerts(session: dict, telegram_id: int,
                                  repo_name: str) -> list[dict]:
    token = _token_from_session(session)
    async with _http().get(
        f"https://api.github.com/repos/{repo_name}/dependabot/alerts",
        headers={"Authorization": f"token {token}"},
        params={"state": "open", "per_page": 10},
    ) as resp:
        if resp.status != 200:
            return []
        alerts = await resp.json(content_type=None)
        return [
            {
                "number": a["number"],
                "severity": a["security_advisory"]["severity"],
                "summary": a["security_advisory"]["summary"][:60],
                "cve_id": a["security_advisory"].get("cve_id", ""),
                "package": a["dependency"]["package"]["name"],
                "vulnerable_version": a["dependency"].get("manifest_path", ""),
                "state": a["state"],
            }
            for a in alerts
        ]


# ── Social / Follow ───────────────────────────────────────────────────────────

async def follow_user(session: dict, username: str) -> bool:
    token = _token_from_session(session)
    async with _http().put(
        f"https://api.github.com/user/following/{username}",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        return resp.status == 204


async def unfollow_user(session: dict, username: str) -> bool:
    token = _token_from_session(session)
    async with _http().delete(
        f"https://api.github.com/user/following/{username}",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        return resp.status == 204


async def get_followers(session: dict, telegram_id: int,
                         page: int = 0) -> list[dict]:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        followers = list(gh.get_user().get_followers())[page*10:(page+1)*10]
        return [{"login": f.login, "avatar": f.avatar_url} for f in followers]
    except GithubException:
        return []


async def search_users(session: dict, query: str) -> list[dict]:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        users = list(gh.search_users(query))[:8]
        return [
            {
                "login": u.login,
                "name": u.name or "",
                "public_repos": u.public_repos,
                "followers": u.followers,
                "bio": u.bio or "",
            }
            for u in users
        ]
    except GithubException:
        return []


# ── Rate limit ────────────────────────────────────────────────────────────────

async def get_rate_limit_info(session: dict, telegram_id: int) -> dict:
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        rl = gh.get_rate_limit()
        data = {
            "remaining": rl.core.remaining,
            "limit": rl.core.limit,
            "reset": rl.core.reset.timestamp(),
            "search_remaining": rl.search.remaining,
            "search_limit": rl.search.limit,
        }
        await store_rate_limit(
            telegram_id, rl.core.remaining, rl.core.limit,
            rl.core.reset.timestamp()
        )
        return data
    except GithubException:
        return {}


# ── Webhooks (repo webhooks manager) ─────────────────────────────────────────

async def get_repo_webhooks(session: dict, telegram_id: int,
                             repo_name: str) -> list[dict]:
    token = _token_from_session(session)
    async with _http().get(
        f"https://api.github.com/repos/{repo_name}/hooks",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        if resp.status != 200:
            return []
        hooks = await resp.json(content_type=None)
        return [
            {
                "id": h["id"],
                "url": h["config"].get("url", ""),
                "events": h["events"],
                "active": h["active"],
            }
            for h in hooks
        ]


async def create_repo_webhook(session: dict, repo_name: str,
                               url: str, events: list[str],
                               secret: str = "") -> dict:
    token = _token_from_session(session)
    config = {"url": url, "content_type": "json"}
    if secret:
        config["secret"] = secret
    async with _http().post(
        f"https://api.github.com/repos/{repo_name}/hooks",
        headers={"Authorization": f"token {token}"},
        json={"name": "web", "active": True,
              "events": events, "config": config},
    ) as resp:
        if resp.status == 201:
            data = await resp.json(content_type=None)
            return {"success": True, "id": data["id"]}
        return {"error": resp.status}


async def delete_repo_webhook(session: dict, repo_name: str,
                               hook_id: int) -> bool:
    token = _token_from_session(session)
    async with _http().delete(
        f"https://api.github.com/repos/{repo_name}/hooks/{hook_id}",
        headers={"Authorization": f"token {token}"},
    ) as resp:
        return resp.status == 204


# ── Organizations ─────────────────────────────────────────────────────────────

async def get_orgs(session: dict, telegram_id: int) -> list[dict]:
    cache_key = "orgs"
    cached = await cache_get(telegram_id, cache_key)
    if cached:
        return cached
    token = _token_from_session(session)
    gh = _gh(token)
    try:
        user = gh.get_user()
        orgs = list(user.get_orgs())
        data = [
            {
                "login": o.login,
                "name": o.name or o.login,
                "description": o.description or "",
                "public_repos": o.public_repos,
                "avatar_url": o.avatar_url,
            }
            for o in orgs
        ]
        await cache_set(telegram_id, cache_key, data, 120)
        return data
    except GithubException:
        return []
