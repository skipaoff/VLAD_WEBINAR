"""Доставляет сообщения продавца от живого аккаунта через Telethon.

Отличий от бота два, и оба важные:

1. Переписка выглядит как переписка с человеком: имя, аватарка, «был в сети».
   Клиент не видит слова «бот» и не может нажать «Заблокировать бота».
2. Владелец и продавец — один и тот же Telegram. Поэтому пульт живёт
   в «Избранном», а если владелец пишет клиенту сам со своего телефона,
   продавец это видит, записывает реплику и в диалоге замолкает.

Канал рассчитан на отдельный рабочий аккаунт: продавец отвечает всем, кто пишет
в личку. Первый запуск требует авторизации: python tools/login-userbot.py
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient, events

from .. import admin
from ..config import TELEGRAM_MESSAGE_LIMIT, Settings
from .base import Channel

log = logging.getLogger("seller")

SAVED_MESSAGES = "me"      # «Избранное» — пульт и эскалации, когда id не задан
SENT_IDS_KEPT = 4000       # помним свои сообщения, чтобы не спутать их с ручными
SENT_IDS_TRIMMED_TO = 2000
TYPING = "typing"
RECORDING = "record-voice"


class UserbotChannel(Channel):
    name = "живой аккаунт"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.owner = settings.admin_chat_id or SAVED_MESSAGES
        self.client = TelegramClient(
            str(settings.session_path), settings.tg_api_id, settings.tg_api_hash
        )
        self.engine = None  # ставится в bot.py, до запуска
        self._sent_ids: set[int] = set()
        self._me_id: int | None = None

    @property
    def has_owner(self) -> bool:
        return True  # «Избранное» есть всегда

    # ─── исходящее ─────────────────────────────────────────────────────────

    def _mark_sent(self, message: Any) -> None:
        """Своё сообщение не должно выглядеть как ручная реплика владельца."""
        message_id = getattr(message, "id", None)
        if message_id is None:
            return
        self._sent_ids.add(message_id)
        if len(self._sent_ids) > SENT_IDS_KEPT:
            self._sent_ids = set(sorted(self._sent_ids)[-SENT_IDS_TRIMMED_TO:])

    async def send_text(self, uid: int, text: str) -> None:
        self._mark_sent(await self.client.send_message(uid, text))

    async def send_voice(self, uid: int, ogg: Path) -> bool:
        try:
            self._mark_sent(await self.client.send_file(uid, str(ogg), voice_note=True))
            return True
        except Exception as exc:  # noqa: BLE001 — отправим текстом
            log.error("голосовое не ушло %s: %s", uid, exc)
            return False

    async def _hold_action(self, uid: int, action: str, seconds: float) -> None:
        """Telethon сам продлевает индикатор, пока открыт контекст."""
        try:
            async with self.client.action(uid, action):
                await asyncio.sleep(seconds)
        except Exception as exc:  # noqa: BLE001 — индикатор не повод не ответить
            log.debug("индикатор %s не показался %s: %s", action, uid, exc)
            await asyncio.sleep(seconds)

    async def show_typing(self, uid: int, seconds: float) -> None:
        await self._hold_action(uid, TYPING, seconds)

    async def show_recording(self, uid: int, seconds: float) -> None:
        await self._hold_action(uid, RECORDING, seconds)

    async def notify_owner(self, html_text: str) -> None:
        try:
            self._mark_sent(
                await self.client.send_message(
                    self.owner, html_text[:TELEGRAM_MESSAGE_LIMIT], parse_mode="html"
                )
            )
        except Exception as exc:  # noqa: BLE001
            log.error("не смог написать владельцу: %s", exc)

    async def forward_to_owner(self, raw_message: Any) -> None:
        if raw_message is None:
            return
        try:
            self._mark_sent(await self.client.forward_messages(self.owner, raw_message))
        except Exception as exc:  # noqa: BLE001
            log.error("не переслал вложение: %s", exc)

    async def fetch_voice(self, raw_message: Any, dest: Path) -> bool:
        try:
            await self.client.download_media(raw_message, file=str(dest))
            return dest.exists() and dest.stat().st_size > 0
        except Exception as exc:  # noqa: BLE001
            log.error("голосовое не скачалось: %s", exc)
            return False

    # ─── входящее ──────────────────────────────────────────────────────────

    @staticmethod
    def _card(sender: Any) -> dict:
        if sender is None:
            return {}
        names = (getattr(sender, "first_name", ""), getattr(sender, "last_name", ""))
        return {
            "name": " ".join(part for part in names if part),
            "username": getattr(sender, "username", "") or "",
            "lang": getattr(sender, "lang_code", "") or "",
        }

    @staticmethod
    def _media_kind(message: Any) -> str | None:
        if message.photo:
            return "фото"
        if message.video:
            return "видео"
        if message.audio:
            return "аудио"
        if message.document:
            return "документ"
        return None

    async def on_incoming(self, event: Any) -> None:
        """Личка от живого человека. Каналы, группы и другие боты — мимо."""
        if not event.is_private:
            return
        sender = await event.get_sender()
        if sender is None or getattr(sender, "bot", False):
            return

        uid = event.sender_id
        message = event.message
        card = self._card(sender)

        if message.voice or message.video_note:
            size = getattr(message.file, "size", 0) or 0
            await self.engine.on_client_voice(uid, message, size=size, card=card)
            return

        kind = self._media_kind(message)
        if kind:
            await self.engine.on_client_media(
                uid, message, kind, (message.raw_text or "").strip()
            )
            return

        text = (message.raw_text or "").strip()
        if not text:
            return
        if text.startswith("/start"):
            await self.engine.on_client_start(uid, text[len("/start"):].strip(), card)
            return
        await self.engine.on_client_text(uid, text, card)

    async def on_outgoing(self, event: Any) -> None:
        """Что владелец отправил сам: в «Избранное» — команда, клиенту — перехват."""
        message = event.message
        if message.id in self._sent_ids:
            return

        text = (message.raw_text or "").strip()
        if not text:
            return

        if event.chat_id == self._me_id:
            await self._run_command(text)
            return
        if event.is_private:
            await self.engine.on_owner_wrote(event.chat_id, text)

    async def _run_command(self, text: str) -> None:
        if not admin.looks_like_command(text):
            return
        answer = await admin.handle(self.engine, text)
        if not answer:
            return
        self._mark_sent(
            await self.client.send_message(
                self.owner, answer[:TELEGRAM_MESSAGE_LIMIT], parse_mode="html"
            )
        )

    # ─── запуск ────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.client.loop.run_until_complete(self._boot())
        self.client.run_until_disconnected()

    async def _boot(self) -> None:
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise SystemExit(
                "Аккаунт не авторизован. Запусти один раз: python tools/login-userbot.py"
            )

        me = await self.client.get_me()
        self._me_id = me.id
        self.name = f"аккаунт @{me.username}" if me.username else f"аккаунт {me.id}"
        log.info("поднялся как %s (id %s)", self.name, me.id)

        self.client.add_event_handler(self.on_incoming, events.NewMessage(incoming=True))
        self.client.add_event_handler(self.on_outgoing, events.NewMessage(outgoing=True))

        asyncio.create_task(self.engine.followup_loop())
        await self.notify_owner(
            "🟢 Продавец поднялся на живом аккаунте.\n"
            f"Пульт — здесь, в «Избранном». {admin.HELP}"
        )
