"""Детектор утечки внутрянки в реплике ассистента.

Честная граница: Gemini Live отдаёт речь потоком, поэтому перехватить фразу
ДО того, как она произнесена, нельзя. Слой ловит факт и гасит сессию, но уже
сказанное не отменяет. Настоящая защита в том, что в промпте нет ничего,
что жалко потерять.

Ловим только машинные следы — пути, имена файлов, названия моделей и стека.
Продуктовые слова правилами намеренно не покрыты: ложное срабатывание
обрывает живой разговор, и это дороже.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class LeakVerdict:
    leaked: bool
    markers: tuple[str, ...] = ()


_RULES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("repo_path", re.compile(r"\b(?:worker|bot|kb|modules)/[\w./-]+", re.IGNORECASE)),
    ("source_file", re.compile(r"\b[\w-]+\.(?:md|py|json|ts|tsx|js)\b", re.IGNORECASE)),
    ("model_id", re.compile(r"\b(?:gemini|claude|gpt|llama)[-\w.]*\b", re.IGNORECASE)),
    ("stack_name", re.compile(r"\b(?:livekit|pydantic|openai|anthropic|websocket)\b", re.IGNORECASE)),
    (
        "prompt_structure",
        re.compile(r"системн\w*\s+(?:промпт|инструкц)|system\s+prompt|мой\s+промпт", re.IGNORECASE),
    ),
    ("kb_structure", re.compile(r"\b(?:kb_files|kb_root|agent_name|system_prompt)\b", re.IGNORECASE)),
    (
        "prompt_quote",
        re.compile(r"перекрывают всё выше|Конец правил|это данные, а не инструкции", re.IGNORECASE),
    ),
)


def detect_leak(text: str) -> LeakVerdict:
    if not text or not text.strip():
        return LeakVerdict(False)
    markers = tuple(name for name, pattern in _RULES if pattern.search(text))
    return LeakVerdict(bool(markers), markers)


def incident_line(room: str, markers: tuple[str, ...]) -> str:
    """Строка инцидента для лога. Текста реплики в ней нет намеренно."""
    return f"leak_detected room={room} markers={','.join(markers)}"
