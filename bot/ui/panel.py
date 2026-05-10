"""
Panel Manager — GitroHub v2.0
Context-based message editing system.
Each context (dashboard, repos, files, etc.) owns ONE message.
Edit within context, send new when context changes.
"""
import logging
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InlineKeyboardMarkup, Message, CallbackQuery,
    ReplyKeyboardMarkup,
)

from bot.services.cache import get_panel, set_panel, delete_panel
from utils.formatters import h

logger = logging.getLogger(__name__)

# ── Context names ─────────────────────────────────────────────────────────────
CTX_DASHBOARD    = "dashboard"
CTX_REPOS        = "repos"
CTX_REPO         = "repo"
CTX_FILES        = "files"
CTX_UPLOAD       = "upload"
CTX_BRANCHES     = "branches"
CTX_HISTORY      = "history"
CTX_PULLS        = "pulls"
CTX_ISSUES       = "issues"
CTX_RELEASES     = "releases"
CTX_ACTIONS      = "actions"
CTX_SETTINGS     = "settings"
CTX_ACCOUNT      = "account"
CTX_NOTIFICATIONS= "notifications"
CTX_EXPLORE      = "explore"
CTX_PROFILE      = "profile"
CTX_FORKS        = "forks"
CTX_PROJECTS     = "projects"
CTX_SECURITY     = "security"
CTX_HEALTH       = "health"


class PanelManager:
    """
    Manages the lifecycle of context panels.

    Rules:
    - Within same context: EDIT the existing message
    - New context: SEND new message, store its ID
    - Edit fails (deleted/too old): SEND new, update stored ID
    - Content identical: SKIP edit silently
    """

    def __init__(self, bot: Bot):
        self.bot = bot

    async def update(
        self,
        telegram_id: int,
        chat_id: int,
        context: str,
        text: str,
        keyboard: Optional[InlineKeyboardMarkup] = None,
        reply_markup_override: Optional[ReplyKeyboardMarkup] = None,
        parse_mode: str = "HTML",
        force_new: bool = False,
    ) -> Optional[Message]:
        """
        Core method: edit existing panel or send new one.
        Returns the message that was sent/edited.
        """
        existing = await get_panel(telegram_id, context)

        if existing and not force_new:
            stored_chat_id, msg_id = existing
            try:
                await self.bot.edit_message_text(
                    chat_id=stored_chat_id,
                    message_id=msg_id,
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=parse_mode,
                )
                return None  # edited in place
            except TelegramBadRequest as e:
                err = str(e).lower()
                if "message is not modified" in err:
                    return None  # identical content, skip silently
                if any(x in err for x in [
                    "message to edit not found",
                    "message can't be edited",
                    "message_id_invalid",
                    "too old",
                ]):
                    # Fall through to send new
                    await delete_panel(telegram_id, context)
                else:
                    logger.warning(f"Edit failed ({context}): {e}")
                    return None

        # Send new message
        msg = await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
        )
        await set_panel(telegram_id, context, chat_id, msg.message_id)
        return msg

    async def from_callback(
        self,
        query: CallbackQuery,
        context: str,
        text: str,
        keyboard: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = "HTML",
    ) -> None:
        """
        Shortcut for callback handlers.
        Tries to edit the callback's own message first (fastest path).
        Falls back to panel registry if contexts differ.
        """
        telegram_id = query.from_user.id
        chat_id = query.message.chat.id
        current_msg_id = query.message.message_id

        # Check if this callback message IS the registered panel
        existing = await get_panel(telegram_id, context)
        if existing:
            stored_chat_id, stored_msg_id = existing
            if stored_msg_id == current_msg_id:
                # Same message — edit directly
                try:
                    await query.message.edit_text(
                        text=text,
                        reply_markup=keyboard,
                        parse_mode=parse_mode,
                    )
                    return
                except TelegramBadRequest as e:
                    if "message is not modified" in str(e).lower():
                        return
                    logger.warning(f"Callback edit failed: {e}")

        # Contexts differ or no panel — edit callback message and update registry
        try:
            await query.message.edit_text(
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
            )
            await set_panel(telegram_id, context, chat_id, current_msg_id)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                return
            # Edit failed — send new
            msg = await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=keyboard,
                parse_mode=parse_mode,
            )
            await set_panel(telegram_id, context, chat_id, msg.message_id)

    async def send_output(
        self,
        chat_id: int,
        text: str,
        keyboard: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = "HTML",
    ) -> Message:
        """
        Send a persistent output message (receipt, error, file, etc.).
        These are NOT registered as panels — they live in chat permanently.
        """
        return await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=keyboard,
            parse_mode=parse_mode,
        )

    async def send_document_output(
        self,
        chat_id: int,
        document,
        filename: str,
        caption: str = "",
        keyboard: Optional[InlineKeyboardMarkup] = None,
    ) -> Message:
        """Send a file (ZIP, edited file, etc.) as persistent output."""
        return await self.bot.send_document(
            chat_id=chat_id,
            document=document,
            filename=filename,
            caption=caption,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

    async def loading(
        self,
        query: CallbackQuery,
        context: str,
        message: str = "⏳  Loading...",
    ) -> None:
        """Show a loading state while processing."""
        try:
            await query.message.edit_text(
                text=message,
                parse_mode="HTML",
            )
            # Don't update registry — we'll overwrite this with real content
        except TelegramBadRequest:
            pass

    async def progress(
        self,
        chat_id: int,
        telegram_id: int,
        context: str,
        steps: list[str],
        current_step: int,
    ) -> None:
        """
        Update a panel to show progress through multi-step operation.
        Used for ZIP upload, clone, etc.
        """
        lines = []
        for i, step in enumerate(steps):
            if i < current_step:
                lines.append(f"  ✅  {step}")
            elif i == current_step:
                lines.append(f"  🔄  {step}")
            else:
                lines.append(f"  ⏳  {step}")
        text = "\n".join(lines)
        await self.update(telegram_id, chat_id, context, text)


# ── Progress step definitions ─────────────────────────────────────────────────

COMMIT_STEPS = [
    "Receiving file",
    "Analyzing changes",
    "Comparing with GitHub",
    "Committing",
    "Done",
]

ZIP_STEPS = [
    "ZIP received",
    "Extracting files",
    "Stripping wrapper folder",
    "Scanning files",
    "Comparing with GitHub",
    "Ready to commit",
]

DOWNLOAD_STEPS = [
    "Fetching repository",
    "Packaging files",
    "Compressing",
    "Sending to Telegram",
]

CLONE_STEPS = [
    "Finding repository",
    "Forking to your account",
    "Verifying fork",
    "Done",
]
