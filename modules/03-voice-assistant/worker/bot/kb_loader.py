"""Сборка system prompt из файлов базы знаний.

Читает ровно те файлы, что перечислены в конфиге, в том же порядке, и склеивает
в одну строку. Никакой автоподгрузки каталогов «на всякий случай»: в промпт
попадает только утверждённый список — это и есть граница модуля.
"""

from __future__ import annotations

from pathlib import Path


class KBLoadError(Exception):
    pass


def load_kb(kb_root: Path, kb_files: list[str]) -> str:
    parts: list[str] = []
    for rel in kb_files:
        target = (kb_root / rel).resolve()
        if not target.is_file():
            raise KBLoadError(f"файл базы знаний не найден: {target}")
        parts.append(target.read_text(encoding="utf-8"))
    return "\n\n".join(parts)
