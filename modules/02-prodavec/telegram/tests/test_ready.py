"""Готов ли продавец к запуску.

На чистом шаблоне красный: в знаниях стоят метки. Зеленеет, когда обе папки заполнены
и в репозиторий не попал токен.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
TENANT = MODULE_ROOT / "tenant.json"

PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")


def business_filled() -> bool:
    """Заполнение начинают с бренда — по нему и судим, шаблон это или боевой модуль."""
    try:
        brand = json.loads(TENANT.read_text(encoding="utf-8")).get("brand_name", "")
    except json.JSONDecodeError:
        return True  # битый файл — пусть тест скажет об этом громко
    return bool(str(brand).strip()) and not PLACEHOLDER.search(str(brand))


def skip_if_template() -> None:
    if not business_filled():
        pytest.skip("модуль ещё не заполнен под бизнес — в tenant.json стоит метка")


def tenant() -> dict:
    return json.loads(TENANT.read_text(encoding="utf-8"))


def knowledge_files() -> list[Path]:
    out: list[Path] = []
    for folder in tenant()["knowledge_order"]:
        out.extend(sorted((MODULE_ROOT / folder).rglob("*.md")))
    return out


def test_two_knowledge_folders() -> None:
    """Папки знаний ровно две: что продавать и как продавать."""
    order = tenant()["knowledge_order"]
    assert len(order) == 2, f"ожидаются две папки знаний, сейчас {order}"
    assert order[0].endswith("what-to-sell"), "первой идёт папка про то, что продаём"
    assert order[1].endswith("how-to-sell"), "правила разговора идут последними"
    for folder in order:
        path = MODULE_ROOT / folder
        assert path.is_dir(), f"папки нет: {folder}"
        assert list(path.rglob("*.md")), f"папка пуста: {folder}"


def test_what_to_sell_is_structured() -> None:
    """Что продаём разложено по разделам, а не свалено в один файл."""
    root = MODULE_ROOT / "knowledge" / "what-to-sell"
    sections = {p.name for p in root.iterdir() if p.is_dir()}
    expected = {"offer", "product", "prices", "audience", "terms"}
    assert expected <= sections, f"нет разделов: {sorted(expected - sections)}"


def test_knowledge_filled() -> None:
    skip_if_template()
    for path in knowledge_files():
        left = PLACEHOLDER.findall(path.read_text(encoding="utf-8"))
        assert not left, f"{path.relative_to(MODULE_ROOT)}: не заполнено {len(left)} мест"


def test_tenant_filled() -> None:
    skip_if_template()
    raw = TENANT.read_text(encoding="utf-8")
    assert not PLACEHOLDER.findall(raw), "tenant.json: остались метки"
    data = json.loads(raw)
    for key in ("brand_name", "seller_name", "language", "owner_telegram", "site_url"):
        assert data.get(key), f"в tenant.json пусто поле {key}"


def test_voice_profile() -> None:
    skip_if_template()
    """Если голос включён — сказано, какой именно голос и какой он."""
    voice = tenant()["voice"]
    if not voice.get("enabled"):
        return
    for key in ("voice_id", "whose_voice", "character"):
        value = str(voice.get(key, ""))
        assert value and not PLACEHOLDER.search(value), (
            f"голос включён, но не заполнено {key} — бот не будет знать, чьим голосом говорить"
        )


def test_code_knows_nothing_about_business() -> None:
    """В коде не должно быть продуктовых фактов — только загрузка файлов."""
    code = (MODULE_ROOT / "bot.py").read_text(encoding="utf-8")
    for word in ("грн", "руб", "скидк", "консультаци"):
        assert word not in code.lower(), (
            f"в bot.py просочился бизнес-факт ({word}) — его место в knowledge/"
        )


SECRET_HINTS = (
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
)


def test_no_secrets_committed() -> None:
    for path in MODULE_ROOT.rglob("*"):
        if not path.is_file() or path.name == ".env":
            continue
        if any(p in {"__pycache__", ".git", ".venv", "state", ".pytest_cache"} for p in path.parts):
            continue
        if path.suffix not in {".py", ".json", ".md", ".txt", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_HINTS:
            assert not pattern.search(text), f"похоже на секрет в {path.relative_to(MODULE_ROOT)}"
