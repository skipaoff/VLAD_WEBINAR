#!/usr/bin/env python3
"""Готовы ли ключи к эфиру. Показывает только, заполнено или нет, — сами значения не печатает.

    python3 check_env.py
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = [ROOT / ".env", Path.home() / ".config" / "vlad-webinar" / ".env"]

NEEDED = {
    "03 Видеоконсультант": ["TAVUS_API_KEY"],
    "05 Реклама": ["META_AD_ACCOUNT_ID", "META_ACCESS_TOKEN", "META_APP_SECRET", "META_APP_ID"],
    "06 Продавец": ["TELEGRAM_BOT_TOKEN", "ANTHROPIC_API_KEY"],
    "07 Консьерж": ["TG_API_ID", "TG_API_HASH"],
}
OPTIONAL = {"06 Продавец": ["ELEVENLABS_API_KEY"]}


def read(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    merged: dict[str, str] = {}
    for src in reversed(SOURCES):          # ближний файл главнее
        merged.update({k: v for k, v in read(src).items() if v})
    merged.update({k: v for k, v in os.environ.items() if k in sum(NEEDED.values(), [])})

    found = [str(s).replace(str(Path.home()), "~") for s in SOURCES if s.exists()]
    print("Файлы с ключами:", ", ".join(found) if found else "не найдено ни одного")
    print()

    ready = True
    for module, keys in NEEDED.items():
        missing = [k for k in keys if not merged.get(k) or merged.get(k) == "act_"]
        mark = "готово" if not missing else "не хватает: " + ", ".join(missing)
        ready &= not missing
        print(f"  {'✓' if not missing else '✗'} {module:22} {mark}")
        for k in OPTIONAL.get(module, []):
            if not merged.get(k):
                print(f"    · {k} пуст — модуль работает без него")

    session = ROOT / "modules" / "07-concierge" / "session" / "concierge.session"
    print(f"\n  {'✓' if session.exists() else '✗'} Консьерж: вход в аккаунт Telegram "
          f"{'выполнен' if session.exists() else 'не выполнен — python modules/07-concierge/concierge.py login'}")

    print("\nК эфиру готово." if ready and session.exists() else "\nЕсть что доделать до эфира.")


if __name__ == "__main__":
    main()
