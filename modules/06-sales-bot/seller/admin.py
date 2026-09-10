"""Выполняет команды владельца и возвращает ему готовый ответ текстом.

Логика команд одна на оба канала, отличается только доставка: в канале bot
команды приходят боту в личку, в userbot — в «Избранное».
"""

from __future__ import annotations

import html
import logging
import time
from typing import TYPE_CHECKING, Awaitable, Callable

from .brain import split_reply
from .config import TELEGRAM_MESSAGE_LIMIT, TEST_UID
from .memory import CLIENT, SELLER, remember

if TYPE_CHECKING:
    from .engine import Engine

log = logging.getLogger("seller")

COMMANDS = {
    "status": "как дела у продавца",
    "asclient": "прогнать реплику как от клиента",
    "hist": "последние реплики диалога",
    "say": "написать клиенту от лица продавца",
    "mute": "замолчать в диалоге",
    "unmute": "снова отвечать",
    "pause": "пауза во всех диалогах",
    "resume": "продолжить",
    "reload": "перечитать знания",
}

HELP = "Пульт: " + " ".join(f"/{name}" for name in COMMANDS)

HISTORY_SHOWN = 12        # реплик в /hist
REPLY_PREVIEW_CHARS = 400  # длина реплики в /hist
MUTED_SCANNED = 50        # сколько свежих диалогов проверяем на mute в /status

_HANDLERS: dict[str, Callable[["Engine", str], Awaitable[str]]] = {}


def command(name: str):
    """Регистрирует обработчик команды, чтобы список был в одном месте."""

    def wrap(func):
        _HANDLERS[name] = func
        return func

    return wrap


def looks_like_command(text: str) -> bool:
    head = text.strip().split(None, 1)[0] if text.strip() else ""
    return head.lstrip("/").split("@")[0] in COMMANDS


async def handle(engine: "Engine", text: str) -> str | None:
    """Ответ владельцу, или None если это была не команда."""
    parts = text.strip().split(None, 1)
    if not parts:
        return None
    name = parts[0].lstrip("/").split("@")[0]
    handler = _HANDLERS.get(name)
    if handler is None:
        return None
    argument = parts[1].strip() if len(parts) > 1 else ""
    try:
        return await handler(engine, argument)
    except ValueError as exc:
        return f"Не понял: {html.escape(str(exc))}"
    except Exception as exc:  # noqa: BLE001 — пульт не должен ронять продавца
        log.exception("команда /%s упала", name)
        return f"Команда упала: {html.escape(engine.safe(exc))[:300]}"


def parse_dialog(argument: str) -> tuple[int, str]:
    """Первое слово — id диалога, остальное — хвост."""
    bits = argument.split(None, 1)
    if not bits:
        raise ValueError("нужен id диалога")
    try:
        return int(bits[0]), (bits[1] if len(bits) > 1 else "")
    except ValueError:
        raise ValueError(f"«{bits[0]}» не похоже на id диалога") from None


@command("status")
async def cmd_status(engine: "Engine", argument: str) -> str:
    uptime = int(time.time() - engine.started_at)
    dialogs = engine.memory.dialogs()
    muted = [
        path.stem
        for path in dialogs[:MUTED_SCANNED]
        if engine.memory.load(int(path.stem)).get("muted")
    ] if dialogs else []

    settings = engine.settings
    try:
        size = len(engine.brain.knowledge.prompt())
        knowledge_line = f"Знания: {size // 1000} тыс. символов, бизнес «{settings.business}»"
    except SystemExit as exc:
        knowledge_line = f"⚠️ Знания не собираются: {exc}"

    lines = [
        f"🟢 Работаю {uptime // 3600} ч {uptime % 3600 // 60} мин"
        if not engine.paused else "⏸ На паузе",
        f"Канал: {settings.channel} · {engine.channel.name}",
        f"Модель: {settings.model}, усилие {settings.effort}",
        knowledge_line,
        f"Голосовые: слушаю {engine.voice.backend or 'нет'}, "
        f"отвечаю {'да' if engine.voice.speaks else 'нет'}",
        f"Диалогов: {len(dialogs)}",
    ]
    if dialogs:
        lines.append(f"Последний: <code>{dialogs[0].stem}</code>")
    if muted:
        lines.append("Молчу в: " + ", ".join(muted))
    return "\n".join(lines)


@command("pause")
async def cmd_pause(engine: "Engine", argument: str) -> str:
    engine.paused = True
    return "⏸ Пауза. Сообщения копятся в память, ответы не уходят."


@command("resume")
async def cmd_resume(engine: "Engine", argument: str) -> str:
    engine.paused = False
    return "▶️ Работаю дальше."


@command("mute")
async def cmd_mute(engine: "Engine", argument: str) -> str:
    uid, _ = parse_dialog(argument)
    _set_muted(engine, uid, True)
    return f"🔇 В диалоге {uid} молчу, переписку ведёшь ты."


@command("unmute")
async def cmd_unmute(engine: "Engine", argument: str) -> str:
    uid, _ = parse_dialog(argument)
    _set_muted(engine, uid, False)
    return f"🔊 В диалоге {uid} снова отвечаю."


def _set_muted(engine: "Engine", uid: int, muted: bool) -> None:
    mem = engine.memory.load(uid)
    mem["muted"] = muted
    engine.memory.save(uid, mem)


@command("say")
async def cmd_say(engine: "Engine", argument: str) -> str:
    uid, text = parse_dialog(argument)
    if not text:
        return "Как: /say 123456789 текст сообщения"
    try:
        await engine.channel.send_text(uid, text)
    except Exception as exc:  # noqa: BLE001 — владельцу важна причина, а не трейс
        return f"Не ушло: {html.escape(engine.safe(exc))[:300]}"
    mem = engine.memory.load(uid)
    remember(mem, SELLER, text)
    engine.memory.save(uid, mem)
    return "✅ Отправлено и записано в память диалога."


@command("hist")
async def cmd_hist(engine: "Engine", argument: str) -> str:
    uid, _ = parse_dialog(argument)
    tail = engine.memory.load(uid).get("messages", [])[-HISTORY_SHOWN:]
    if not tail:
        return "Пусто."
    body = "\n".join(
        f"<b>{'Клиент' if item['role'] == CLIENT else 'Продавец'}:</b> "
        f"{html.escape(item['text'][:REPLY_PREVIEW_CHARS])}"
        for item in tail
    )
    return body[:TELEGRAM_MESSAGE_LIMIT]


@command("reload")
async def cmd_reload(engine: "Engine", argument: str) -> str:
    engine.brain.knowledge.invalidate()
    try:
        size = len(engine.brain.knowledge.prompt())
    except SystemExit as exc:
        return f"⚠️ Не собралось: {exc}"
    return f"♻️ Знания перечитаны: {size // 1000} тыс. символов."


@command("asclient")
async def cmd_asclient(engine: "Engine", argument: str) -> str:
    """Прогон реплики от лица клиента: ответ придёт владельцу, клиенту не уйдёт."""
    if not argument:
        return (
            "Как: <code>/asclient привет, а сколько стоит?</code>\n"
            "Диалог копится. Начать заново: <code>/asclient reset</code>"
        )
    if argument.lower() == "reset":
        engine.memory.forget(TEST_UID)
        return "Тестовый диалог очищен."

    mem = engine.memory.load(TEST_UID)
    mem["client"] = {"name": "тестовый клиент"}
    started = time.time()
    try:
        reply = await engine.brain.ask(engine.memory.as_messages(mem, [argument]))
    except Exception as exc:  # noqa: BLE001
        return f"Не сгенерировалось: {html.escape(engine.safe(exc))[:500]}"

    remember(mem, CLIENT, argument)
    parts, escalations = split_reply(reply, engine.pace.max_parts)
    for part in parts:
        remember(mem, SELLER, part)
    engine.memory.save(TEST_UID, mem)

    body = "\n\n".join(f"💬 {html.escape(part)}" for part in parts) or "(пусто)"
    if escalations:
        body += "\n\n⚑ эскалация: " + "; ".join(html.escape(item) for item in escalations)
    return (body + f"\n\n<i>{time.time() - started:.1f} с</i>")[:TELEGRAM_MESSAGE_LIMIT]
