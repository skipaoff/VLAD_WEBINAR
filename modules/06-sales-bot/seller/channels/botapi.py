"""Доставляет сообщения продавца через обычного бота от @BotFather.

Long polling, python-telegram-bot. Ставится за пять минут, аккаунт человека
не трогает, банов не боится. Ограничение одно: клиент пишет боту первым.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .. import admin
from ..config import TELEGRAM_ACTION_TTL_SEC, TELEGRAM_MESSAGE_LIMIT, Settings
from .base import Channel

log = logging.getLogger("seller")

ERROR_NOTICE_COOLDOWN_SEC = 300  # чтобы шторм одинаковых ошибок не забил личку


class BotChannel(Channel):
    name = "бот от @BotFather"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.owner_id = settings.admin_chat_id
        self.app: Application = (
            ApplicationBuilder().token(settings.bot_token).post_init(self._post_init).build()
        )
        self.engine = None  # ставится в bot.py, до запуска
        self._last_notice: dict[str, float] = {}

    @property
    def has_owner(self) -> bool:
        return bool(self.owner_id)

    # ─── исходящее ─────────────────────────────────────────────────────────

    async def send_text(self, uid: int, text: str) -> None:
        await self.app.bot.send_message(uid, text)

    async def send_voice(self, uid: int, ogg: Path) -> bool:
        try:
            with open(ogg, "rb") as handle:
                await self.app.bot.send_voice(uid, handle)
            return True
        except TelegramError as exc:
            log.error("голосовое не ушло %s: %s", uid, exc)
            return False

    async def _hold_action(self, uid: int, action: str, seconds: float) -> None:
        """Telegram гасит индикатор через пять секунд — обновляем, пока ждём."""
        left = seconds
        while left > 0:
            try:
                await self.app.bot.send_chat_action(uid, action)
            except TelegramError as exc:
                log.debug("индикатор %s не показался %s: %s", action, uid, exc)
            step = min(TELEGRAM_ACTION_TTL_SEC, left)
            await asyncio.sleep(step)
            left -= step

    async def show_typing(self, uid: int, seconds: float) -> None:
        await self._hold_action(uid, ChatAction.TYPING, seconds)

    async def show_recording(self, uid: int, seconds: float) -> None:
        await self._hold_action(uid, ChatAction.RECORD_VOICE, seconds)

    async def notify_owner(self, html_text: str) -> None:
        if not self.owner_id:
            log.info("владельцу (некуда): %s", html_text[:200])
            return
        try:
            await self.app.bot.send_message(
                self.owner_id, html_text[:TELEGRAM_MESSAGE_LIMIT], parse_mode=ParseMode.HTML
            )
        except TelegramError as exc:
            log.error("не смог написать владельцу: %s", exc)

    async def forward_to_owner(self, raw_message: Any) -> None:
        if not self.owner_id or raw_message is None:
            return
        try:
            await raw_message.forward(self.owner_id)
        except TelegramError as exc:
            log.error("не переслал вложение: %s", exc)

    async def fetch_voice(self, raw_message: Any, dest: Path) -> bool:
        audio = raw_message.voice or raw_message.video_note
        try:
            tg_file = await self.app.bot.get_file(audio.file_id)
            await tg_file.download_to_drive(dest)
            return True
        except TelegramError as exc:
            log.error("голосовое не скачалось: %s", exc)
            return False

    # ─── входящее ──────────────────────────────────────────────────────────

    @staticmethod
    def _card(update: Update) -> dict:
        user = update.effective_user
        return {
            "name": " ".join(x for x in (user.first_name, user.last_name) if x) or "",
            "username": user.username or "",
            "lang": user.language_code or "",
        }

    def _is_owner(self, update: Update) -> bool:
        return bool(self.owner_id) and update.effective_user.id == self.owner_id

    async def on_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._is_owner(update):
            await update.message.reply_text("Админский вход. " + admin.HELP)
            return
        mark = " ".join(context.args) if context.args else ""
        await self.engine.on_client_start(
            update.effective_user.id, mark, self._card(update)
        )

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._is_owner(update):
            return
        await self.engine.on_client_text(
            update.effective_user.id, update.message.text or "", self._card(update)
        )

    async def on_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._is_owner(update):
            return
        message = update.message
        audio = message.voice or message.video_note
        await self.engine.on_client_voice(
            update.effective_user.id,
            message,
            size=audio.file_size or 0,
            card=self._card(update),
        )

    async def on_media(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._is_owner(update):
            return
        message = update.message
        kind = (
            "фото" if message.photo
            else "документ" if message.document
            else "видео" if message.video
            else "вложение"
        )
        await self.engine.on_client_media(
            update.effective_user.id, message, kind, (message.caption or "").strip()
        )

    async def on_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_owner(update):
            return
        answer = await admin.handle(self.engine, update.message.text or "")
        if answer:
            await update.message.reply_text(answer, parse_mode=ParseMode.HTML)

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.exception("необработанная ошибка", exc_info=context.error)
        key = f"unhandled:{type(context.error).__name__}"
        if time.time() - self._last_notice.get(key, 0) < ERROR_NOTICE_COOLDOWN_SEC:
            return
        self._last_notice[key] = time.time()
        await self.notify_owner(f"🔥 Ошибка: <code>{self.engine.safe(context.error)[:800]}</code>")

    # ─── запуск ────────────────────────────────────────────────────────────

    async def _post_init(self, app: Application) -> None:
        me = await app.bot.get_me()
        self.name = f"бот @{me.username}"
        await self._publish_commands(app)
        app.create_task(self.engine.followup_loop())
        log.info("поднялся как @%s", me.username)

    async def _publish_commands(self, app: Application) -> None:
        """Клиенту меню команд не показываем, владельцу — показываем."""
        try:
            await app.bot.set_my_commands([])
            if self.owner_id:
                await app.bot.set_my_commands(
                    [BotCommand(name, hint) for name, hint in admin.COMMANDS.items()],
                    scope=BotCommandScopeChat(chat_id=self.owner_id),
                )
        except TelegramError as exc:
            log.warning("не выставил меню команд: %s", exc)

    def run(self) -> None:
        private = filters.ChatType.PRIVATE
        self.app.add_handler(CommandHandler("start", self.on_start, filters=private))
        for name in admin.COMMANDS:
            self.app.add_handler(CommandHandler(name, self.on_command, filters=private))
        self.app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND & private, self.on_text)
        )
        self.app.add_handler(
            MessageHandler((filters.VOICE | filters.VIDEO_NOTE) & private, self.on_voice)
        )
        self.app.add_handler(
            MessageHandler(
                (filters.PHOTO | filters.Document.ALL | filters.VIDEO) & private, self.on_media
            )
        )
        self.app.add_error_handler(self.on_error)
        self.app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
