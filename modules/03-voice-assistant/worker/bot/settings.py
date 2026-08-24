"""Настройки воркера: то, что лежит в config.json.

Секретов здесь нет — ключи читаются отдельно, в composition_root.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class VoiceSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Путь к базе знаний относительно корня модуля (там, где лежат kb/ и worker/).
    kb_root: Path = Field(default=Path("kb"))
    # Порядок важен: последний файл перекрывает предыдущие.
    kb_files: list[str] = Field(default_factory=list, min_length=1)

    llm_model: str = Field(default="gemini-3.1-flash-live-preview")
    # Голоса Gemini Live: Kore, Puck, Charon, Fenrir, Leda, Aoede.
    voice: str = Field(default="Kore", min_length=1)
    # Язык разговора: ru, uk, en и т.д.
    language: str = Field(default="ru", min_length=2, max_length=5)
    # Первая фраза, которую ассистент говорит сам, до вопроса человека.
    greeting: str = Field(default="", min_length=1)

    agent_name: str = Field(default="voice-assistant", min_length=1)
    max_tokens_per_reply: int = Field(default=250, gt=0, le=2000)
    max_session_duration_sec: int = Field(default=300, gt=30, le=3600)

    log_path: Path = Field(default=Path("logs/voice.log"))
    leads_path: Path = Field(default=Path("leads.jsonl"))
