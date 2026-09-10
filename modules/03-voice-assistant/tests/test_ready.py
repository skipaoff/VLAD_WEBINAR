"""Готов ли модуль к эфиру.

На чистом шаблоне эти тесты зелёные: шаблон и должен быть с метками. Модуль считается
заполненным, как только в `brand.json` вписано название бизнеса, — с этого момента
проверки становятся строгими. Смысл прежний: ассистент не должен прочитать вслух
метку вида {{НАЗВАНИЕ}}, а незаполненная половина — это красный тест, а не «почти готово».
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
KB_DIR = MODULE_ROOT / "kb"
CONFIG = MODULE_ROOT / "worker" / "config.json"
BRAND = MODULE_ROOT / "brand.json"

PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")


def _kb_files() -> list[Path]:
    return sorted(KB_DIR.glob("*.md"))


def business_filled() -> bool:
    """Заполнение начинают с `brand.json` — по названию бизнеса и судим о модуле.

    Пока метка на месте — перед нами шаблон из репозитория, и требовать от него
    заполненности нечего. Как только имя вписано, спрос полный.
    """
    try:
        brand = json.loads(BRAND.read_text(encoding="utf-8")).get("brand", "")
    except json.JSONDecodeError:
        return True  # битый файл — пусть тест скажет об этом громко, а не промолчит
    return bool(str(brand).strip()) and not PLACEHOLDER.search(str(brand))


def skip_if_template() -> None:
    if not business_filled():
        pytest.skip("модуль ещё не заполнен под бизнес — в brand.json стоит метка")


# ─── структура: проверяется всегда, шаблон это или боевой модуль ─────────


def test_kb_files_exist() -> None:
    assert _kb_files(), "в kb/ нет ни одного файла базы знаний"


def test_config_valid() -> None:
    """Конфиг разбирается схемой и ссылается на существующие файлы."""
    from bot.settings import VoiceSettings

    settings = VoiceSettings.model_validate(json.loads(CONFIG.read_text(encoding="utf-8")))
    for name in settings.kb_files:
        assert (MODULE_ROOT / settings.kb_root / name).is_file(), f"нет файла {name}"


def test_rules_go_last() -> None:
    """Файл с границами обязан быть последним: он перекрывает всё, что выше."""
    from bot.settings import VoiceSettings

    settings = VoiceSettings.model_validate(json.loads(CONFIG.read_text(encoding="utf-8")))
    assert settings.kb_files[-1].endswith("rules.md"), (
        f"последним в kb_files должен идти файл правил, сейчас {settings.kb_files[-1]}"
    )


def test_kb_assembles() -> None:
    """База знаний собирается в один промпт — тем же кодом, что и в бою."""
    from bot.kb_loader import load_kb
    from bot.settings import VoiceSettings

    settings = VoiceSettings.model_validate(json.loads(CONFIG.read_text(encoding="utf-8")))
    prompt = load_kb(MODULE_ROOT / settings.kb_root, settings.kb_files)
    assert len(prompt) > 500, "промпт подозрительно короткий — база знаний пустая?"


# ─── заполненность: спрашивается с модуля, объявленного боевым ───────────


@pytest.mark.parametrize("path", _kb_files(), ids=lambda p: p.name)
def test_kb_has_no_placeholders(path: Path) -> None:
    skip_if_template()
    left = PLACEHOLDER.findall(path.read_text(encoding="utf-8"))
    assert not left, f"{path.name}: не заполнено {len(left)} мест — {left[:3]}"


def test_brand_filled() -> None:
    skip_if_template()
    left = PLACEHOLDER.findall(BRAND.read_text(encoding="utf-8"))
    assert not left, f"brand.json: не заполнено — {left}"


def test_config_filled() -> None:
    skip_if_template()
    left = PLACEHOLDER.findall(CONFIG.read_text(encoding="utf-8"))
    assert not left, f"config.json: остались метки {{...}} — {left}"


def test_prompt_bez_metok() -> None:
    """Последняя черта: собранный промпт не содержит меток — их бы озвучили вслух."""
    skip_if_template()
    from bot.kb_loader import load_kb
    from bot.settings import VoiceSettings

    settings = VoiceSettings.model_validate(json.loads(CONFIG.read_text(encoding="utf-8")))
    prompt = load_kb(MODULE_ROOT / settings.kb_root, settings.kb_files)
    assert "{{" not in prompt


SECRET_HINTS = (
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),          # Google API key
    re.compile(r"sk-[0-9A-Za-z]{20,}"),             # OpenAI-подобный
    # Значение обязано стоять на той же строке: пустое поле в .env.example — не секрет.
    re.compile(r"API(?:_|-)?KEY[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"SECRET[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{16,}"),
)


def test_no_secrets_committed() -> None:
    """Ни один ключ не должен попасть в файлы модуля."""
    skip = {".env", "leads.jsonl"}
    for path in MODULE_ROOT.rglob("*"):
        if not path.is_file() or path.name in skip:
            continue
        if any(part in {".venv", "__pycache__", "node_modules", ".git"} for part in path.parts):
            continue
        if path.suffix not in {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".md", ".txt", ".css", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_HINTS:
            found = pattern.search(text)
            assert not found, f"похоже на секрет в {path.relative_to(MODULE_ROOT)}: {found.group()[:20]}…"


# ─── рецепты подключения ────────────────────────────────────────────────
INSTALL_DIR = MODULE_ROOT / "web" / "install"
WEB_PATH = re.compile(r"web/[\w./-]+\.(?:jsx|tsx|css|ts|js)(?![\w])")


def test_install_recipes_exist() -> None:
    """Под каждый стек лежит готовый рецепт — агенту нечего изобретать."""
    expected = {
        "README.md",
        "static-html.md",
        "next-app-router.md",
        "next-pages-router.md",
        "vite-react.md",
        "other.md",
    }
    actual = {p.name for p in INSTALL_DIR.glob("*.md")}
    assert expected <= actual, f"нет рецептов: {sorted(expected - actual)}"


@pytest.mark.parametrize(
    "recipe", sorted(INSTALL_DIR.glob("*.md")), ids=lambda p: p.name
)
def test_recipe_paths_are_real(recipe: Path) -> None:
    """Каждый файл, на который ссылается рецепт, действительно лежит в модуле."""
    for rel in set(WEB_PATH.findall(recipe.read_text(encoding="utf-8"))):
        assert (MODULE_ROOT / rel).is_file(), f"{recipe.name} ссылается на {rel}, а его нет"
