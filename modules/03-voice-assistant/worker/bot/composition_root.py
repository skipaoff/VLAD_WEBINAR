"""Сборка рантайма: конфиг + логгер + ключи + system prompt.

Падает сразу и внятно, если чего-то не хватает: лучше не подняться на старте,
чем взять трубку и молчать.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .kb_loader import KBLoadError, load_kb
from .settings import VoiceSettings


class ConfigError(Exception):
    pass


class MissingSecretError(Exception):
    pass


@dataclass(slots=True)
class VoiceRuntime:
    settings: VoiceSettings
    log: logging.Logger
    gemini_api_key: str
    system_prompt: str
    module_root: Path


def _module_root() -> Path:
    # worker/bot/composition_root.py → parents[2] = корень модуля (там kb/ и worker/)
    return Path(__file__).resolve().parents[2]


def _worker_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _setup_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger("voice")
    if not log.handlers:
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    return log


def load_settings() -> VoiceSettings:
    config_path = _worker_root() / "config.json"
    if not config_path.exists():
        raise ConfigError(f"config.json не найден: {config_path}")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    settings: VoiceSettings = VoiceSettings.model_validate(raw)
    if "{{" in settings.greeting or "{{" in settings.agent_name:
        raise ConfigError(
            "config.json ещё не заполнен: остались метки {{...}}. "
            "Заполни greeting и agent_name перед запуском."
        )
    return settings


def build_runtime() -> VoiceRuntime:
    module_root = _module_root()
    settings = load_settings()
    log = _setup_logger(_worker_root() / settings.log_path)

    # Ключи: worker/.env, затем обычные переменные окружения.
    load_dotenv(_worker_root() / ".env")

    secrets = {
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
        "LIVEKIT_API_KEY": os.environ.get("LIVEKIT_API_KEY"),
        "LIVEKIT_API_SECRET": os.environ.get("LIVEKIT_API_SECRET"),
        "LIVEKIT_URL": os.environ.get("LIVEKIT_URL"),
    }
    for name, value in secrets.items():
        if not value:
            raise MissingSecretError(f"{name} не задан в worker/.env или в окружении")

    gemini_key = secrets["GEMINI_API_KEY"]
    assert gemini_key is not None

    try:
        system_prompt = load_kb(module_root / settings.kb_root, settings.kb_files)
    except KBLoadError as e:
        raise ConfigError(f"база знаний не собралась: {e}") from e

    if "{{" in system_prompt:
        raise ConfigError(
            "в базе знаний остались незаполненные метки {{...}} — "
            "ассистент будет читать их вслух. Заполни kb/ полностью."
        )

    log.info(
        "рантайм собран: agent=%s model=%s язык=%s файлов=%d промпт=%d символов",
        settings.agent_name,
        settings.llm_model,
        settings.language,
        len(settings.kb_files),
        len(system_prompt),
    )

    return VoiceRuntime(
        settings=settings,
        log=log,
        gemini_api_key=gemini_key,
        system_prompt=system_prompt,
        module_root=module_root,
    )
