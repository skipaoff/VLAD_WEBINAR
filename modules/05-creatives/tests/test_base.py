"""Проверка базы промптов.

Агент читает файлы по структуре, а не по смыслу: если в файле нет блока с промптом или
таблицы языков, он молча сделает не то. Тест держит структуру одинаковой во всех нишах.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
PROMPTS_DIR = MODULE_ROOT / "prompts"
README = MODULE_ROOT / "README.md"

PROMPT_FILES = sorted(p for p in PROMPTS_DIR.rglob("*.md") if p.name != "README.md")


def test_base_is_not_empty() -> None:
    assert PROMPT_FILES, "в prompts/ нет ни одного поста"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_structure(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# "), "нет заголовка поста в первой строке"
    assert "**Что на выходе:**" in text, "нет подписи, что получится на выходе"
    assert "**Формат:**" in text, "не указан формат"

    blocks = re.findall(r"```text\n(.*?)```", text, re.S)
    assert len(blocks) == 1, f"ожидается ровно один блок с промптом, найдено {len(blocks)}"
    assert len(blocks[0]) > 400, "промпт подозрительно короткий"

    assert "## Текст на других языках" in text, "нет таблицы с языками"
    assert "| EN (по умолчанию) |" in text, "нет английской строки — она основная"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_listed_in_readme(path: Path) -> None:
    """Каждый пост попал в таблицу — иначе агент его не покажет ведущему."""
    rel = path.relative_to(MODULE_ROOT).as_posix()
    assert rel in README.read_text(encoding="utf-8"), f"{rel} не указан в README"


@pytest.mark.parametrize("path", PROMPT_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_cyrillic_on_image(path: Path) -> None:
    """Внутри промпта текст на картинке — латиницей. Кириллица живёт в таблице языков ниже."""
    prompt = re.findall(r"```text\n(.*?)```", path.read_text(encoding="utf-8"), re.S)[0]
    quoted = re.findall(r'"([^"]+)"', prompt)
    for line in quoted:
        assert not re.search(r"[А-Яа-яЇїІіЄєҐґ]", line), (
            f"в промпте осталась кириллица на картинке: {line[:40]}"
        )
