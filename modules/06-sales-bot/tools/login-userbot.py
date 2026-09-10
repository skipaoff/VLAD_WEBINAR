#!/usr/bin/env python3
"""Разово авторизует живой аккаунт и кладёт сессию в session/<имя>.session.

Запускается руками, один раз, на той же машине, где потом будет жить продавец:

    python tools/login-userbot.py

Telegram спросит номер телефона, пришлёт код в приложение, при включённой
двухфакторке — пароль. Всё это вводится здесь, в терминале, и никуда
не пересылается.

Файл сессии — ключ от аккаунта. Он в .gitignore: не коммить его и не пересылай
в мессенджерах, тот, у кого он есть, читает и пишет от твоего имени.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seller import config  # noqa: E402


def main() -> None:
    settings = config.load()
    if not (settings.tg_api_id and settings.tg_api_hash):
        raise SystemExit(
            "В .env нет TG_API_ID и TG_API_HASH.\n"
            "Взять на my.telegram.org → API development tools → создать приложение."
        )

    try:
        from telethon import TelegramClient
    except ImportError:
        raise SystemExit(
            "Нет Telethon: .venv/bin/pip install -r requirements.txt"
        ) from None

    config.SESSION_DIR.mkdir(exist_ok=True)
    session_file = settings.session_path.with_suffix(".session")
    if session_file.exists():
        print(f"Сессия уже есть: {session_file}")
        print("Войти другим аккаунтом — удали этот файл и запусти скрипт заново.")

    with TelegramClient(
        str(settings.session_path), settings.tg_api_id, settings.tg_api_hash
    ) as client:
        me = client.get_me()
        name = f"@{me.username}" if me.username else me.first_name
        print(f"\nГотово. Продавец будет писать от имени {name} (id {me.id}).")
        print(f"Сессия: {session_file}")
        print('\nДальше: в config.json поставь "channel": "userbot" и запусти python bot.py')
        print("Пульт управления будет в «Избранном» этого аккаунта.")


if __name__ == "__main__":
    main()
