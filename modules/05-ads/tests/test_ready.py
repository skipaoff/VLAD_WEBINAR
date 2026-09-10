"""Готов ли модуль к эфиру.

На чистом шаблоне зелёный: шаблон и должен быть с метками. Модуль считается заполненным,
как только в `account.json` вписано название бизнеса, — с этого момента спрос полный.
Незаполненная половина кабинета красная, и это главное, что тут ловится.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = MODULE_ROOT / "account.json"
KNOWLEDGE = MODULE_ROOT / "knowledge"

PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")


def business_filled() -> bool:
    """Заполнение начинают с названия бизнеса — по нему и судим о модуле.

    Пока метка на месте — перед нами шаблон из репозитория, и требовать от него
    заполненности нечего. Как только имя вписано, спрашиваем за весь кабинет.
    """
    try:
        name = json.loads(ACCOUNT.read_text(encoding="utf-8")).get("business_name", "")
    except json.JSONDecodeError:
        return True  # битый файл — пусть тест скажет об этом громко, а не промолчит
    return bool(str(name).strip()) and not PLACEHOLDER.search(str(name))


def skip_if_template() -> None:
    if not business_filled():
        pytest.skip("модуль ещё не заполнен под бизнес — в account.json стоит метка")


def test_account_filled() -> None:
    skip_if_template()
    left = PLACEHOLDER.findall(ACCOUNT.read_text(encoding="utf-8"))
    assert not left, f"account.json: не заполнено — {left}"


def test_account_has_required_fields() -> None:
    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    required = (
        "business_name", "site_url", "city", "city_key", "country_code", "language",
        "page_id", "currency", "timezone", "daily_budget", "age_min", "age_max",
    )
    missing = [k for k in required if k not in data]
    assert not missing, f"в account.json нет полей: {missing}"


def test_ad_account_id_shape() -> None:
    """Кабинет всегда с префиксом act_ — без него вызовы отвалятся."""
    env = MODULE_ROOT / ".env"
    if not env.exists():
        pytest.skip(".env ещё не создан")
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("META_AD_ACCOUNT_ID="):
            value = line.split("=", 1)[1].strip()
            if not value:
                pytest.skip("кабинет ещё не вписан")
            assert value.startswith("act_"), f"нужен префикс act_, сейчас {value}"


def test_budget_is_sane() -> None:
    """Бюджет в файле указан в целых единицах валюты, не в центах."""
    data = json.loads(ACCOUNT.read_text(encoding="utf-8"))
    budget = data["daily_budget"]
    assert isinstance(budget, (int, float)), "daily_budget должен быть числом"
    assert 2 <= budget <= 100, (
        f"daily_budget={budget}: здесь целые единицы валюты, а не мелкие. "
        "В API он умножается на 100 отдельно."
    )


def test_knowledge_complete() -> None:
    expected = {
        "01-api.md", "02-structure.md", "03-targeting.md",
        "04-copy.md", "05-naming.md", "06-safety.md", "07-errors.md",
    }
    actual = {p.name for p in KNOWLEDGE.glob("*.md")}
    assert expected <= actual, f"нет файлов базы знаний: {sorted(expected - actual)}"


def test_api_recipes_present() -> None:
    """В базе знаний есть все вызовы, без которых запуск не соберётся."""
    api = (KNOWLEDGE / "01-api.md").read_text(encoding="utf-8")
    for endpoint in ("/campaigns", "/adsets", "/adcreatives", "/ads", "/adimages",
                     "appsecret_proof", "special_ad_categories"):
        assert endpoint in api, f"в 01-api.md нет {endpoint}"


SECRET_HINTS = (
    re.compile(r"EAA[A-Za-z0-9]{20,}"),
    re.compile(r"APP_SECRET[\"\']?[ \t]*[:=][ \t]*[\"\']?[A-Za-z0-9]{16,}"),
    re.compile(r"ACCESS_TOKEN[\"\']?[ \t]*[:=][ \t]*[\"\']?[A-Za-z0-9]{16,}"),
)


def test_no_secrets_committed() -> None:
    for path in MODULE_ROOT.rglob("*"):
        if not path.is_file() or path.name == ".env":
            continue
        if any(part in {"__pycache__", ".git", ".pytest_cache"} for part in path.parts):
            continue
        if path.suffix not in {".py", ".json", ".md", ".txt", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_HINTS:
            found = pattern.search(text)
            assert not found, f"похоже на секрет в {path.relative_to(MODULE_ROOT)}"
