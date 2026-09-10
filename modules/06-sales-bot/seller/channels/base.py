"""Канал связи: всё, чем движок продаж трогает Telegram.

Каналов два — бот от @BotFather и живой аккаунт через Telethon. Логика продажи
у них одна и та же, поэтому она вынесена в engine.py и про транспорт не знает.
Здесь описано ровно то, что транспорт обязан уметь.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class Channel(ABC):
    """Транспорт. Движок вызывает только эти методы и ничего больше."""

    name: str = "?"

    @abstractmethod
    async def send_text(self, uid: int, text: str) -> None:
        """Отправить сообщение клиенту."""

    @abstractmethod
    async def send_voice(self, uid: int, ogg: Path) -> bool:
        """Отправить голосовое. False — не вышло, движок отправит текстом."""

    @abstractmethod
    async def show_typing(self, uid: int, seconds: float) -> None:
        """Показывать «печатает…» указанное время."""

    @abstractmethod
    async def show_recording(self, uid: int, seconds: float) -> None:
        """Показывать «записывает голосовое…» указанное время."""

    @abstractmethod
    async def notify_owner(self, html_text: str) -> None:
        """Написать владельцу: эскалация, новый диалог, ошибка."""

    @abstractmethod
    async def forward_to_owner(self, raw_message: Any) -> None:
        """Переслать владельцу вложение клиента как есть."""

    @abstractmethod
    async def fetch_voice(self, raw_message: Any, dest: Path) -> bool:
        """Скачать голосовое клиента в файл. False — не вышло."""

    @abstractmethod
    def run(self) -> None:
        """Подключиться и крутиться, пока не остановят.

        Синхронный намеренно: каждый транспорт держит свой цикл событий
        и запускает его сам.
        """

    @property
    @abstractmethod
    def has_owner(self) -> bool:
        """Есть ли куда писать владельцу. Нет — эскалации уходят только в лог."""
