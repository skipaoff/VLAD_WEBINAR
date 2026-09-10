"""Ведёт диалог с клиентом: копит реплики, спрашивает модель, отвечает в темпе.

Про транспорт не знает ничего — работает через Channel. Поэтому бот от @BotFather
и живой аккаунт через Telethon продают одинаково, отличается только доставка.
"""

from __future__ import annotations

import asyncio
import html
import logging
import random
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .brain import ESCALATE_RE, Brain, split_reply
from .channels.base import Channel
from .config import (
    MAX_INCOMING_CHARS,
    MAX_VOICE_BYTES,
    TEST_UID,
    Settings,
)
from .memory import CLIENT, SELLER, Memory, remember
from .safety import scrub
from .voice import Voice

log = logging.getLogger("seller")

SECONDS_PER_HOUR = 3600
VOICE_SUFFIX = ".ogg"

NUDGE = (
    "Клиент замолчал и не отвечает больше суток. Напиши одно короткое сообщение: "
    "напомни о себе по-человечески, дай пользу или уточни, актуально ли ещё, "
    "и закончи вопросом. Без «ну что вы решили» и без давления."
)

ASK_FOR_TEXT = "Напишите, пожалуйста, текстом — так быстрее отвечу"
VOICE_TOO_LONG = "Слишком длинное голосовое, не осилю. Можно короче или текстом?"
VOICE_UNCLEAR = "Не расслышал голосовое, напишите текстом, пожалуйста"


class Engine:
    """Один экземпляр на запуск. Собирается в bot.py вместе с каналом."""

    def __init__(
        self,
        channel: Channel,
        settings: Settings,
        brain: Brain,
        voice: Voice,
        memory: Memory,
    ) -> None:
        self.channel = channel
        self.settings = settings
        self.pace = settings.pace
        self.brain = brain
        self.voice = voice
        self.memory = memory
        self.secrets = settings.secrets_to_scrub()

        self.started_at = time.time()
        self.paused = False
        self.pending: dict[int, list[str]] = defaultdict(list)
        self.timers: dict[int, asyncio.Task] = {}
        self.locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    def safe(self, text: object) -> str:
        """Текст ошибки без ключей и токенов — годится для лога и для владельца."""
        return scrub(text, self.secrets)

    # ─── вход ──────────────────────────────────────────────────────────────

    async def on_client_text(self, uid: int, text: str, card: dict | None = None) -> None:
        """Реплика клиента. Копится и уходит в модель одним куском."""
        await self._touch_client(uid, card, spoke_by_voice=False)
        clean = text.strip()[:MAX_INCOMING_CHARS]
        self.pending[uid].append(clean)
        log.info("вход %s: %s", uid, clean[:120].replace("\n", " "))
        self.schedule(uid)

    async def on_client_start(self, uid: int, mark: str, card: dict | None = None) -> None:
        """Клиент открыл диалог. Метку из ссылки кладём в карточку — это источник."""
        extra = dict(card or {})
        if mark:
            extra["entry"] = mark
        await self._touch_client(uid, extra, spoke_by_voice=False, mark=mark)
        self.pending[uid].append(
            "[клиент открыл диалог и нажал «Начать»]" + (f" метка: {mark}" if mark else "")
        )
        self.schedule(uid)

    async def on_client_voice(
        self, uid: int, raw_message: Any, size: int = 0, card: dict | None = None
    ) -> None:
        """Голосовое: расшифровываем и дальше ведём как обычную реплику."""
        if not self.voice.listens:
            await self.channel.send_text(uid, ASK_FOR_TEXT)
            await self.channel.forward_to_owner(raw_message)
            return
        if size and size > MAX_VOICE_BYTES:
            await self.channel.send_text(uid, VOICE_TOO_LONG)
            return

        text = await self._voice_to_text(uid, raw_message)
        if not text:
            await self.channel.send_text(uid, VOICE_UNCLEAR)
            await self.channel.forward_to_owner(raw_message)
            return

        await self._touch_client(uid, card, spoke_by_voice=True)
        log.info("голосовое %s: %s", uid, text[:120].replace("\n", " "))
        self.pending[uid].append(text[:MAX_INCOMING_CHARS])
        self.schedule(uid)

    async def on_client_media(
        self, uid: int, raw_message: Any, kind: str, caption: str = ""
    ) -> None:
        """Фото, файл, видео: владельцу — как есть, клиенту — словами."""
        await self.channel.forward_to_owner(raw_message)
        await self.channel.notify_owner(
            f"📎 {kind} от <code>{uid}</code>. "
            f"Ответить самому: <code>/say {uid} текст</code>"
        )
        self.pending[uid].append(
            f"[клиент прислал {kind}" + (f' с подписью: "{caption}"' if caption else "") + "]"
        )
        self.schedule(uid)

    async def on_owner_wrote(self, uid: int, text: str) -> None:
        """Владелец написал клиенту сам, минуя продавца.

        Бывает только на живом аккаунте: там владелец и продавец — один Telegram.
        Реплику запоминаем и в этом диалоге замолкаем, чтобы двое не писали
        клиенту одновременно.
        """
        mem = self.memory.load(uid)
        remember(mem, SELLER, text)
        was_muted = mem.get("muted")
        mem["muted"] = True
        self.memory.save(uid, mem)

        self.cancel_pending(uid)
        if not was_muted:
            await self.channel.notify_owner(
                f"✋ Ты написал <code>{uid}</code> сам — в этом диалоге я замолчал.\n"
                f"Вернуть меня: <code>/unmute {uid}</code>"
            )

    async def _touch_client(
        self, uid: int, card: dict | None, spoke_by_voice: bool, mark: str = ""
    ) -> None:
        """Обновляет карточку и, если диалог новый, сообщает о нём владельцу."""
        mem = self.memory.load(uid)
        first_contact = not mem.get("messages")
        if card:
            mem["client"] = {**mem.get("client", {}), **card}
        mem["voice"] = spoke_by_voice
        self.memory.save(uid, mem)
        if first_contact:
            await self.announce_new(uid, mem, mark)

    async def _voice_to_text(self, uid: int, raw_message: Any) -> str:
        await self.channel.show_typing(uid, self.pace.min_delay)
        tmp = Path(tempfile.mkstemp(suffix=VOICE_SUFFIX)[1])
        try:
            if not await self.channel.fetch_voice(raw_message, tmp):
                return ""
            return await self.voice.transcribe(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    # ─── ответ ─────────────────────────────────────────────────────────────

    def schedule(self, uid: int) -> None:
        """Ставит отложенный ответ, отменив предыдущий: клиент ещё пишет."""
        self.cancel_pending(uid, keep_messages=True)
        self.timers[uid] = asyncio.create_task(self.reply_later(uid))

    def cancel_pending(self, uid: int, keep_messages: bool = False) -> None:
        timer = self.timers.get(uid)
        if timer and not timer.done():
            timer.cancel()
        if not keep_messages:
            self.pending.pop(uid, None)
            self.timers.pop(uid, None)

    async def reply_later(self, uid: int) -> None:
        """Ждём, вдруг клиент дописывает, и отвечаем один раз на всё сразу."""
        try:
            await asyncio.sleep(self.pace.debounce_sec)
        except asyncio.CancelledError:
            return

        async with self.locks[uid]:
            fresh = self.pending.pop(uid, [])
            self.timers.pop(uid, None)
            if not fresh:
                return
            await self._answer(uid, fresh)

    async def _answer(self, uid: int, fresh: list[str]) -> None:
        mem = self.memory.load(uid)
        mem["last_client_at"] = time.time()
        mem["followups"] = 0

        if mem.get("muted") or self.paused:
            self._store_client_lines(mem, fresh)
            self.memory.save(uid, mem)
            return

        try:
            reply = await self.brain.ask(self.memory.as_messages(mem, fresh))
        except Exception as exc:  # noqa: BLE001 — клиента придержим, владельцу расскажем
            log.exception("генерация упала для %s", uid)
            self._store_client_lines(mem, fresh)
            await self.hold_on(uid, mem)
            await self._report_no_answer(uid, f"Не смог ответить: {self.safe(exc)[:800]}")
            return

        self._store_client_lines(mem, fresh)
        parts, escalations = split_reply(reply, self.pace.max_parts)
        if not parts:
            log.warning("пустой ответ для %s", uid)
            await self.hold_on(uid, mem)
            await self._report_no_answer(uid, "Модель вернула пустой ответ.")
            return

        await self.deliver(uid, mem, parts)
        self.memory.save(uid, mem)
        if escalations:
            await self._report_escalations(uid, mem, escalations)

    @staticmethod
    def _store_client_lines(mem: dict, fresh: list[str]) -> None:
        for text in fresh:
            remember(mem, CLIENT, text)

    async def _report_no_answer(self, uid: int, reason: str) -> None:
        await self.channel.notify_owner(
            f"⚠️ Клиент <code>{uid}</code>. {html.escape(reason)}\n"
            f"Клиенту ушло: «{html.escape(self.settings.holding_line)}». "
            f"Дописать: <code>/say {uid} текст</code>"
        )

    async def _report_escalations(self, uid: int, mem: dict, escalations: list[str]) -> None:
        body = "\n".join(f"• {html.escape(item)}" for item in escalations)
        name = html.escape(str(mem.get("client", {}).get("name") or uid))
        await self.channel.notify_owner(
            f"❓ Нужен ты: <b>{name}</b> (<code>{uid}</code>)\n{body}\n\n"
            f"Ответить самому: <code>/say {uid} текст</code>"
        )

    async def deliver(self, uid: int, mem: dict, parts: list[str]) -> None:
        """Голосом — только тому, кто сам пишет голосом. Иначе текстом, в темпе."""
        if mem.get("voice") and self.voice.speaks:
            if await self.say_aloud(uid, "\n\n".join(parts)):
                for part in parts:
                    remember(mem, SELLER, part)
                return

        for index, part in enumerate(parts):
            try:
                await self.type_and_send(uid, part, first=(index == 0))
            except Exception as exc:  # noqa: BLE001 — доставка не должна ронять диалог
                log.error("не отправилось клиенту %s: %s", uid, self.safe(exc))
                await self.channel.notify_owner(
                    f"⚠️ Не смог отправить сообщение <code>{uid}</code>: "
                    f"{html.escape(self.safe(exc))[:400]}"
                )
                break
            remember(mem, SELLER, part)

    def pause_for(self, text: str, first: bool) -> float:
        """Сколько «печатать»: по длине текста, с разбросом и паузой на чтение."""
        pace = self.pace
        delay = min(pace.max_delay, pace.min_delay + len(text) / pace.typing_cps)
        delay *= random.uniform(*pace.jitter)
        return delay + (random.uniform(*pace.reading_pause) if first else 0)

    async def type_and_send(self, uid: int, text: str, first: bool) -> None:
        await self.channel.show_typing(uid, self.pause_for(text, first))
        await self.channel.send_text(uid, text)

    async def say_aloud(self, uid: int, text: str) -> bool:
        spoken = ESCALATE_RE.sub("", text).replace("\n\n", " ").strip()
        ogg = await self.voice.synthesize(spoken)
        if not ogg:
            return False
        try:
            await self.channel.show_recording(uid, self.pause_for(text, first=True))
            return await self.channel.send_voice(uid, ogg)
        finally:
            ogg.unlink(missing_ok=True)

    async def hold_on(self, uid: int, mem: dict) -> None:
        """Модель не ответила — клиента не бросаем в тишине."""
        line = self.settings.holding_line
        try:
            await self.channel.send_text(uid, line)
            remember(mem, SELLER, line)
        except Exception as exc:  # noqa: BLE001
            log.error("даже придержать не вышло %s: %s", uid, self.safe(exc))
        self.memory.save(uid, mem)

    async def announce_new(self, uid: int, mem: dict, mark: str = "") -> None:
        card = mem.get("client", {})
        name = html.escape(card.get("name") or str(uid))
        tag = f", @{card['username']}" if card.get("username") else ""
        await self.channel.notify_owner(
            f"🆕 Новый диалог: <b>{name}</b> (<code>{uid}</code>{tag})"
            + (f"\nМетка: {html.escape(mark)}" if mark else "")
        )

    # ─── напоминания ───────────────────────────────────────────────────────

    def needs_followup(self, uid: int, mem: dict, now: float) -> bool:
        """Одно-два касания на диалог и всё. Глубоких цепочек здесь нет намеренно."""
        if uid == TEST_UID or self.paused:
            return False
        if not mem.get("messages") or mem.get("muted"):
            return False
        if mem.get("followups", 0) >= self.settings.followup.max_touches:
            return False
        if now - mem.get("last_client_at", 0) < self.settings.followup.hours * SECONDS_PER_HOUR:
            return False
        # последнее слово за клиентом — сначала ответим, потом уже напоминаем
        return mem["messages"][-1]["role"] == SELLER

    async def check_followups(self) -> None:
        now = time.time()
        for path in self.memory.dialogs():
            try:
                uid = int(path.stem)
            except ValueError:
                continue
            if self.locks[uid].locked():
                continue
            mem = self.memory.load(uid)
            if not self.needs_followup(uid, mem, now):
                continue
            async with self.locks[uid]:
                await self._send_followup(uid, mem, now)

    async def _send_followup(self, uid: int, mem: dict, now: float) -> None:
        try:
            reply = await self.brain.ask(self.memory.as_messages(mem, [], note=NUDGE))
        except Exception as exc:  # noqa: BLE001
            log.error("напоминание не сгенерировалось для %s: %s", uid, self.safe(exc))
            return
        parts, _ = split_reply(reply, self.pace.max_parts)
        if not parts:
            return
        try:
            await self.type_and_send(uid, parts[0], first=True)
        except Exception as exc:  # noqa: BLE001
            log.error("напоминание не ушло %s: %s", uid, self.safe(exc))
            return
        remember(mem, SELLER, parts[0])
        mem["followups"] = mem.get("followups", 0) + 1
        mem["last_client_at"] = now  # следующее касание отсчитываем отсюда
        self.memory.save(uid, mem)
        log.info("напоминание отправлено %s (%s-е)", uid, mem["followups"])

    async def followup_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.followup.check_every_sec)
            try:
                await self.check_followups()
            except Exception:  # noqa: BLE001 — цикл переживает любую ошибку внутри
                log.exception("цикл напоминаний")
