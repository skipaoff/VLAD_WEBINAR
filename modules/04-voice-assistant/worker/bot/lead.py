"""Заявка: имя и телефон, которые ассистент забрал в разговоре.

Пишется строкой в leads.jsonl рядом с воркером. Файл в git не попадает.
Это то, ради чего звонок вообще нужен бизнесу, поэтому запись максимально
тупая и надёжная: append одной строкой, без базы и без сети.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Coroutine
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from livekit.agents import function_tool

_DIGITS = re.compile(r"\d")


def make_lead_tool(
    leads_path: Path, room: str, log: logging.Logger
) -> Any:
    """Собирает инструмент save_lead под конкретную сессию."""

    @function_tool
    async def save_lead(name: str, phone: str, note: str = "") -> str:
        """Записать заявку от клиента.

        Вызывай только когда человек сам согласился оставить контакт и назвал телефон.
        Перед вызовом повтори номер вслух по цифрам и дождись подтверждения.

        Args:
            name: как зовут человека
            phone: телефон, как он его назвал
            note: чем интересовался — одной строкой
        """
        if len(_DIGITS.findall(phone)) < 7:
            return "Телефон записан не полностью — переспроси номер и повтори вызов."

        record = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "room": room,
            "name": name.strip()[:120],
            "phone": phone.strip()[:40],
            "note": note.strip()[:300],
        }
        try:
            leads_path.parent.mkdir(parents=True, exist_ok=True)
            with leads_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            log.exception("заявку не удалось записать: room=%s", room)
            return "Записать не получилось — скажи, что перезвонят, и продолжай разговор."

        log.info("заявка записана: room=%s", room)
        return "Заявка записана. Скажи, что передал и с человеком свяжутся."

    return save_lead
