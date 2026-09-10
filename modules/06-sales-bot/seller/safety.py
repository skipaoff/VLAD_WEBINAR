"""Вычищает секреты из текста, который уходит в лог или владельцу.

Ошибка HTTP-клиента часто несёт в себе URL, а в URL Telegram лежит токен бота.
Без этой чистки токен уехал бы в лог и в личку — это и есть утечка.
"""

from __future__ import annotations

MASK = "···"


def scrub(text: object, secrets: list[str]) -> str:
    """Текст без секретов. Пустой список секретов ничего не меняет."""
    result = str(text)
    for secret in secrets:
        if secret:
            result = result.replace(secret, MASK)
    return result
