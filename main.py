"""
GitroHub Bot v2.1 — Main Entry Point
aiogram 3.x + uvloop + aiohttp webhook + Redis + asyncpg
"""
import asyncio
import logging
import os
import secrets
import sys
import time as _time

import uvloop
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import settings
from database.pool import init_pool, close_pool
from bot.services.cache import init_redis, close_redis, r as get_redis
from bot.services.github import init_http, close_http
from bot.middlewares.auth import AuthMiddleware, LoggingMiddleware, ErrorMiddleware

logging.basicConfig(
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    level=logging.DEBUG if settings.debug else logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

_start_time = _time.time()


async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Welcome & dashboard"),
        BotCommand(command="help", description="Help & all commands"),
        BotCommand(command="cancel", description="Cancel current action"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    logger.info("✅ Bot commands registered")


def create_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dp = Dispatcher(storage=storage)

    # Register middlewares (order matters)
    dp.message.middleware(ErrorMiddleware())
    dp.callback_query.middleware(ErrorMiddleware())
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Register all routers
    from bot.handlers.start import router as start_router
    from bot.handlers.auth import router as auth_router
    from bot.handlers.repos import router as repos_router
    from bot.handlers.files import router as files_router
    from bot.handlers.upload import router as upload_router
    from bot.handlers.branches import router as branches_router
    from bot.handlers.history import router as history_router
    from bot.handlers.pulls import router as pulls_router
    from bot.handlers.issues import router as issues_router
    from bot.handlers.releases import router as releases_router
    from bot.handlers.actions import router as actions_router
    from bot.handlers.forks import router as forks_router
    from bot.handlers.account import router as account_router
    from bot.handlers.notifications import router as notifs_router
    from bot.handlers.settings import router as settings_router
    from bot.handlers.explore import router as explore_router
    from bot.handlers.projects import router as projects_router
    from bot.handlers.security import router as security_router
    from bot.handlers.system import router as system_router
    from bot.handlers.admin import router as admin_router
    from bot.handlers.gists import router as gists_router
    from bot.handlers.callbacks import router as callbacks_router

    # Callbacks router last — catches all remaining callback_data
    for r in [
        start_router, auth_router, repos_router, files_router,
        upload_router, branches_router, history_router, pulls_router,
        issues_router, releases_router, actions_router, forks_router,
        account_router, notifs_router, settings_router, explore_router,
        projects_router, security_router, system_router, admin_router,
        gists_router, callbacks_router,
    ]:
        dp.include_router(r)

    return dp


async def build_oauth_success_page(username: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>GitroHub — Connected</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{min-height:100vh;background:#0d1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#e6edf3}}
    .bg{{position:fixed;inset:0;background:radial-gradient(ellipse at 20% 50%,rgba(33,139,255,.08) 0%,transparent 60%),radial-gradient(ellipse at 80% 20%,rgba(46,160,67,.06) 0%,transparent 60%);z-index:0}}
    .card{{position:relative;z-index:1;background:#161b22;border:1px solid #30363d;border-radius:16px;padding:48px 40px;max-width:440px;width:90%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.4)}}
    .logo{{font-size:22px;font-weight:700;background:linear-gradient(135deg,#58a6ff,#2ea043);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:32px}}
    .icon-wrap{{width:80px;height:80px;border-radius:50%;background:rgba(46,160,67,.1);border:2px solid rgba(46,160,67,.3);display:flex;align-items:center;justify-content:center;margin:0 auto 28px;animation:pulse 2s ease infinite}}
    @keyframes pulse{{0%,100%{{box-shadow:0 0 0 0 rgba(46,160,67,.2)}}50%{{box-shadow:0 0 0 12px rgba(46,160,67,0)}}}}
    .check{{width:36px;height:36px;stroke:#2ea043;stroke-width:2.5;fill:none;stroke-dasharray:60;stroke-dashoffset:60;animation:draw .6s ease .3s forwards}}
    @keyframes draw{{to{{stroke-dashoffset:0}}}}
    h1{{font-size:24px;font-weight:600;margin-bottom:10px}}
    .sub{{color:#8b949e;margin-bottom:32px;font-size:15px}}
    .sub span{{color:#58a6ff;font-weight:500}}
    .pills{{display:flex;flex-direction:column;gap:10px;margin-bottom:36px;text-align:left}}
    .pill{{display:flex;align-items:center;gap:12px;background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:12px 16px;font-size:14px;color:#8b949e;opacity:0;animation:slide .4s ease forwards}}
    .pill:nth-child(1){{animation-delay:.4s}}.pill:nth-child(2){{animation-delay:.6s}}.pill:nth-child(3){{animation-delay:.8s}}
    @keyframes slide{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
    .dot{{width:8px;height:8px;border-radius:50%;background:#2ea043;flex-shrink:0}}
    .pill strong{{color:#e6edf3;font-weight:500}}
    .divider{{height:1px;background:#21262d;margin:28px 0}}
    .cta{{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,#1f6feb,#388bfd);color:#fff;text-decoration:none;padding:14px 28px;border-radius:8px;font-size:15px;font-weight:600;width:100%;justify-content:center;border:none;cursor:pointer;transition:opacity .2s,transform .2s}}
    .cta:hover{{opacity:.9;transform:translateY(-1px)}}
    .countdown{{margin-top:16px;font-size:13px;color:#484f58}}
    .footer{{position:relative;z-index:1;margin-top:24px;font-size:13px;color:#484f58}}
  </style>
</head>
<body>
<div class="bg"></div>
<div class="card">
  <div class="logo">🤖 GitroHub</div>
  <div class="icon-wrap">
    <svg class="check" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
  </div>
  <h1>Successfully connected!</h1>
  <p class="sub">GitHub account <span>@{username}</span> is now linked to GitroHub</p>
  <div class="pills">
    <div class="pill"><div class="dot"></div><div><strong>Session saved</strong> — encrypted &amp; secure</div></div>
    <div class="pill"><div class="dot"></div><div><strong>Permissions granted</strong> — repo · user · gist · actions</div></div>
    <div class="pill"><div class="dot"></div><div><strong>Ready</strong> — go back to Telegram to continue</div></div>
  </div>
  <div class="divider"></div>
  <a href="https://t.me/{settings.bot_username}" class="cta">Open GitroHub in Telegram</a>
  <p class="countdown">Closing in <span id="t">5</span>s</p>
</div>
<p class="footer">GitroHub · Your GitHub inside Telegram</p>
<script>
let s=5;const el=document.getElementById('t');
const iv=setInterval(()=>{{s--;el.textContent=s;if(s<=0){{clearInterval(iv);window.close();setTimeout(()=>window.location.href='https://t.me/{settings.bot_username}',300)}}}},1000);
</script>
</body></html>"""


async def build_oauth_error_page(reason: str = "Authorization failed") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>GitroHub — Error</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{min-height:100vh;background:#0d1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;color:#e6edf3}}
    .card{{background:#161b22;border:1px solid #f8515940;border-radius:16px;padding:48px 40px;max-width:440px;width:90%;text-align:center;box-shadow:0 8px 32px rgba(0,0,0,.4)}}
    .icon{{font-size:48px;margin-bottom:24px}}
    h1{{color:#f85149;font-size:22px;margin-bottom:12px}}
    p{{color:#8b949e;margin-bottom:28px}}
    .reason{{background:#0d1117;border:1px solid #21262d;border-radius:8px;padding:12px;font-size:13px;color:#8b949e;margin-bottom:28px}}
    .cta{{display:inline-block;background:#21262d;color:#e6edf3;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:14px}}
  </style>
</head>
<body>
<div class="card">
  <div class="icon">❌</div>
  <h1>Connection Failed</h1>
  <p>Could not connect your GitHub account to GitroHub.</p>
  <div class="reason">{reason}</div>
  <a href="https://t.me/{settings.bot_username}" class="cta">Back to Telegram — try /login again</a>
</div>
</body></html>"""


async def main():
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    logger.info(f"🚀 Starting GitroHub v{settings.bot_version}")

    # Init connections
    await init_pool()
    await init_redis()
    await init_http()

    # Ensure admin user exists
    from database.pool import create_user, get_user
    admin = await get_user(settings.admin_id)
    if not admin:
        await create_user(settings.admin_id, role="admin")
        logger.info(f"✅ Admin user created: {settings.admin_id}")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher()
    await setup_bot_commands(bot)

    if settings.webhook_url:
        # ── Webhook mode ──────────────────────────────────────────────────────

        async def webhook_handler(request: web.Request) -> web.Response:
            # Verify secret
            secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if secret != settings.webhook_secret:
                return web.Response(status=403, text="Forbidden")

            # Immediate 200 — process in background
            data = await request.json()
            from aiogram.types import Update
            update = Update.model_validate(data)
            asyncio.create_task(dp.process_update(update))
            return web.Response(text="OK")

        async def oauth_callback(request: web.Request) -> web.Response:
            code = request.rel_url.query.get("code")
            state = request.rel_url.query.get("state")
            error = request.rel_url.query.get("error")

            if error or not code or not state:
                reason = error or "Missing parameters"
                html = await build_oauth_error_page(reason)
                return web.Response(content_type="text/html", text=html)

            from bot.handlers.auth import handle_oauth_callback
            success, result = await handle_oauth_callback(code, state, bot)

            if success:
                html = await build_oauth_success_page(result)
            else:
                html = await build_oauth_error_page(result)
            return web.Response(content_type="text/html", text=html)

        async def health_check(request: web.Request) -> web.Response:
            return web.Response(
                content_type="text/html",
                text=f"<h2>🤖 GitroHub v{settings.bot_version}</h2><p>Running ✅</p>",
            )

        async def follow_user_cb(request: web.Request) -> web.Response:
            """Handle follow/unfollow callbacks that come from explore."""
            return web.Response(text="OK")

        web_app = web.Application()
        web_app.router.add_post("/webhook", webhook_handler)
        web_app.router.add_get("/auth/github/callback", oauth_callback)
        web_app.router.add_get("/callback", oauth_callback)  # legacy fallback
        web_app.router.add_get("/", health_check)
        web_app.router.add_get("/health", health_check)

        # Set webhook
        webhook_url = f"{settings.webhook_url}/webhook"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=settings.webhook_secret,
            allowed_updates=["message", "callback_query", "inline_query"],
            drop_pending_updates=True,
        )
        logger.info(f"✅ Webhook set: {webhook_url}")
        logger.info(f"✅ OAuth callback: {settings.github_redirect_uri}")

        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", settings.port)
        await site.start()
        logger.info(f"🌐 Server running on port {settings.port}")
        logger.info(f"🤖 GitroHub v{settings.bot_version} is live!")

        # Keep alive
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    else:
        # ── Polling mode (local dev) ──────────────────────────────────────────
        logger.info("🔄 Running in polling mode (local development)")
        await bot.delete_webhook(drop_pending_updates=True)
        try:
            await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
        finally:
            pass

    # Cleanup
    await close_http()
    await close_redis()
    await close_pool()
    await bot.session.close()
    logger.info("👋 GitroHub shut down cleanly")


if __name__ == "__main__":
    asyncio.run(main())
