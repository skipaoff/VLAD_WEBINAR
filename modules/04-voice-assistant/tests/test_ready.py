"""Готов ли модуль к эфиру.

На чистом шаблоне эти тесты КРАСНЫЕ — так и задумано: они зеленеют только когда
модуль заполнен под конкретный бизнес. Красный тест перед деплоем означает, что
ассистент начнёт читать вслух метки вида {{НАЗВАНИЕ}}.
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


def test_kb_files_exist() -> None:
    assert _kb_files(), "в kb/ нет ни одного файла базы знаний"


@pytest.mark.parametrize("path", _kb_files(), ids=lambda p: p.name)
def test_kb_has_no_placeholders(path: Path) -> None:
    left = PLACEHOLDER.findall(path.read_text(encoding="utf-8"))
    assert not left, f"{path.name}: не заполнено {len(left)} мест — {left[:3]}"


def test_brand_filled() -> None:
    left = PLACEHOLDER.findall(BRAND.read_text(encoding="utf-8"))
    assert not left, f"brand.json: не заполнено — {left}"


def test_config_filled_and_valid() -> None:
    raw = CONFIG.read_text(encoding="utf-8")
    assert not PLACEHOLDER.findall(raw), "config.json: остались метки {{...}}"

    from bot.settings import VoiceSettings

    settings = VoiceSettings.model_validate(json.loads(raw))
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
        if path.suffix not in {".py", ".js", ".json", ".md", ".txt", ".css", ".example"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_HINTS:
            found = pattern.search(text)
            assert not found, f"похоже на секрет в {path.relative_to(MODULE_ROOT)}: {found.group()[:20]}…"
