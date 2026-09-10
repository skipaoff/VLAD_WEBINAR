#!/usr/bin/env python3
"""Запускает продавца: собирает все зависимости в одном месте и отдаёт управление каналу.

Слои, и каждый знает о соседе ровно столько, сколько нужно:

    seller/channels/  транспорт — бот от @BotFather или живой аккаунт через Telethon
    seller/engine.py  как продаём: дебаунс, темп, эскалации, напоминания
    playbook/         методология продаж, одна для любого бизнеса
    business/<имя>/   что продаём, своё под каждого клиента

Канал выбирается строкой в config.json — логика продажи от этого не меняется.

Запуск: python bot.py
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from seller import config
from seller.brain import Brain
from seller.channels.base import Channel
from seller.config import LOG_DIR, PLAYBOOK_DIR, STATE_DIR, Settings
from seller.engine import Engine
from seller.knowledge import Knowledge
from seller.memory import Memory
from seller.voice import Voice

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_MAX_BYTES = 5_000_000
LOG_BACKUPS = 5
QUIET_LIBRARIES = ("httpx", "httpcore", "telegram", "telethon", "openai", "anthropic")

log = logging.getLogger("seller")


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            RotatingFileHandler(
                LOG_DIR / "seller.log",
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUPS,
                encoding="utf-8",
            ),
            logging.StreamHandler(sys.stdout),
        ],
    )
    for library in QUIET_LIBRARIES:
        logging.getLogger(library).setLevel(logging.WARNING)


def build_channel(settings: Settings) -> Channel:
    """Транспорт по config.json.

    Импортируем только выбранный: канал bot не требует установленного Telethon,
    и наоборот.
    """
    if settings.channel == "userbot":
        from seller.channels.userbot import UserbotChannel

        return UserbotChannel(settings)

    from seller.channels.botapi import BotChannel

    return BotChannel(settings)


def build_engine(settings: Settings, channel: Channel) -> Engine:
    """Единственная точка сборки: всё создаётся здесь и передаётся дальше."""
    roots = {"business": settings.business_dir, "playbook": PLAYBOOK_DIR}
    knowledge = Knowledge(
        sections=[(name, roots[name]) for name in settings.knowledge_order],
        voice=settings.voice,
        speaks_voice=settings.speaks_voice,
    )
    brain = Brain(
        api_key=settings.anthropic_key,
        model=settings.model,
        effort=settings.effort,
        knowledge=knowledge,
    )
    voice = Voice(
        backend=settings.stt_backend,
        openai_key=settings.openai_key,
        eleven_key=settings.eleven_key,
        settings=settings.voice,
        speaks=settings.speaks_voice,
    )
    memory = Memory(state_dir=STATE_DIR, history_limit=settings.pace.history_limit)
    return Engine(channel, settings, brain, voice, memory)


def main() -> None:
    setup_logging()
    settings = config.load()
    config.check(settings)
    STATE_DIR.mkdir(exist_ok=True)

    channel = build_channel(settings)
    engine = build_engine(settings, channel)
    channel.engine = engine

    size = len(engine.brain.knowledge.prompt())  # падаем сразу, а не на первом клиенте
    if settings.channel == "bot" and not settings.admin_chat_id:
        log.warning("ADMIN_CHAT_ID не задан: эскалации и вложения уйдут в лог, а не тебе")

    log.info(
        "запускаю: канал %s, бизнес %s, модель %s, знания %d тыс. символов, "
        "слушаю голос %s, отвечаю голосом %s",
        settings.channel, settings.business, settings.model, size // 1000,
        settings.stt_backend or "нет", settings.speaks_voice,
    )
    channel.run()


if __name__ == "__main__":
    main()
