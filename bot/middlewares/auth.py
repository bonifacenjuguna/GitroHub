"""
Middleware — GitroHub v2.0
Auth check, debounce, activity tracking, alias resolution.
"""
import logging
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Any

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery, Message, TelegramObject, Update,
)

from bot.services.cache import check_debounce, wipe_user
from config import settings
from database.pool import (
    get_active_session, get_user, is_authorized,
    update_user_activity,
)

logger = logging.getLogger(__name__)

# Menu button texts that don't need debounce (navigation is always allowed)
NO_DEBOUNCE = {
    "📁 Repos", "👤 Account", "🔍 Explore",
    "⚙️ Settings", "🔔 Notifs", "🗂️ More",
    "⬅️ Back", "🏠 Home", "❌ Cancel",
    "🔗 Connect GitHub",
}


class AuthMiddleware(BaseMiddleware):
    """
    Checks every incoming update:
    1. If not authorized → show connect screen (except admin)
    2. Track last_active for all users
    3. Debounce rapid button taps
    4. Inject session + user into handler data
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Extract user ID from any event type
        telegram_id: Optional[int] = None
        is_callback = False
        message_text = ""

        if isinstance(event, Message):
            if event.from_user:
                telegram_id = event.from_user.id
                message_text = event.text or ""
        elif isinstance(event, CallbackQuery):
            if event.from_user:
                telegram_id = event.from_user.id
                is_callback = True

        if not telegram_id:
            return await handler(event, data)

        # ── Admin bypass ──────────────────────────────────────────────────────
        is_admin = telegram_id == settings.admin_id

        # ── Auth check ────────────────────────────────────────────────────────
        authorized = is_admin or await is_authorized(telegram_id)

        if not authorized:
            # Not an invited user — show private message
            if isinstance(event, Message):
                await _send_unauthorized(event, telegram_id)
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "❌ Access denied. You need an invitation to use this bot.",
                    show_alert=True,
                )
            return

        # ── Debounce (callbacks only, skip navigation buttons) ────────────────
        if is_callback and event.data not in (
            "noop", "cancel", "home", "help_back"
        ):
            # Skip debounce for navigation-like callbacks
            skip_debounce = any(
                event.data.startswith(p) for p in (
                    "notif_toggle:", "settings_set_",
                )
            ) or message_text in NO_DEBOUNCE

            if not skip_debounce:
                allowed = await check_debounce(telegram_id)
                if not allowed:
                    await event.answer()  # silently acknowledge
                    return

        # ── Load session + user into handler data ─────────────────────────────
        session = await get_active_session(telegram_id)
        user = await get_user(telegram_id)

        data["session"] = session
        data["user"] = user
        data["telegram_id"] = telegram_id
        data["is_admin"] = is_admin

        # ── Update activity (non-blocking background task) ────────────────────
        import asyncio
        asyncio.create_task(update_user_activity(telegram_id))

        # ── Session validity check ─────────────────────────────────────────────
        # If user has a session but token is expired, proactively warn
        if session and isinstance(event, Message):
            # Token expiry detected externally via GitHub 401 → handled in handlers
            pass

        return await handler(event, data)


async def _send_unauthorized(message: Message, telegram_id: int):
    """Send the customizable private message to unauthorized users."""
    from database.pool import get_settings as db_get_settings
    s = await db_get_settings(settings.admin_id)

    custom = s.get("private_message")
    owner = s.get("pm_owner") or "@GitroHubBot"
    link = s.get("pm_link") or ""

    if custom:
        from datetime import datetime
        text = (
            custom
            .replace("{owner}", owner)
            .replace("{botname}", "GitroHub")
            .replace("{date}", datetime.now().strftime("%b %d %Y"))
            .replace("{link}", link)
        )
        await message.answer(text)
        return

    from utils.formatters import panel, h
    lines = [
        "---",
        "This bot is privately owned",
        "and not open for public access.",
        "---",
        f"  👤  Owner       {h(owner)}",
        "---",
        "GitroHub is a personal GitHub",
        "management bot — commit code,",
        "manage repos, upload files",
        "and handle branches directly",
        "from Telegram.",
    ]
    if link:
        lines += ["---", f"  🔗  {h(link)}"]
    lines += ["---", "  ⚙️  Powered by @GitroHubBot"]

    text = "<pre>" + "\n".join(lines) + "</pre>"
    await message.answer(text, parse_mode="HTML")


class LoggingMiddleware(BaseMiddleware):
    """Structured logging for all updates."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        start = time.perf_counter()
        event_type = type(event).__name__

        try:
            result = await handler(event, data)
            elapsed = (time.perf_counter() - start) * 1000

            if elapsed > 500:
                # Log slow handlers
                identifier = ""
                if isinstance(event, CallbackQuery):
                    identifier = f"callback={event.data}"
                elif isinstance(event, Message):
                    identifier = f"text={event.text[:30] if event.text else 'file'}"
                logger.warning(
                    f"⚠️ Slow handler ({elapsed:.0f}ms) {event_type} {identifier}"
                )
            return result

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                f"❌ Handler error ({elapsed:.0f}ms) {event_type}: {e}",
                exc_info=True,
            )
            raise


class ErrorMiddleware(BaseMiddleware):
    """
    Global error catch — never lets exceptions crash the bot.
    Shows user-friendly error and logs full traceback.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Unhandled exception: {e}", exc_info=True)

            from utils.formatters import panel
            error_text = panel("❌  Error", [
                "---",
                "Something went wrong.",
                "---",
                f"  {type(e).__name__}",
                "---",
                "Please try again or use",
                "the ❌ Cancel button to reset.",
            ])

            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="❌ Cancel & Reset",
                                     callback_data="cancel"),
                InlineKeyboardButton(text="🏠 Home",
                                     callback_data="home"),
            ]])

            try:
                if isinstance(event, CallbackQuery):
                    await event.answer("❌ An error occurred.", show_alert=True)
                    await event.message.answer(
                        f"<pre>{error_text}</pre>",
                        parse_mode="HTML",
                        reply_markup=kb,
                    )
                elif isinstance(event, Message):
                    await event.answer(
                        f"<pre>{error_text}</pre>",
                        parse_mode="HTML",
                        reply_markup=kb,
                    )
            except Exception:
                pass  # If even error reporting fails, silently continue
