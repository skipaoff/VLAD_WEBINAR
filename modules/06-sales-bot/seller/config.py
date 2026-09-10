"""Собирает настройки продавца в один объект Settings и проверяет секреты.

Три источника, и они не пересекаются: в .env только то, что нельзя показывать,
в config.json только то, что можно, в business/ только то, что про бизнес.
Читаются они здесь и больше нигде: остальные модули получают готовое.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"
SESSION_DIR = ROOT / "session"
PLAYBOOK_DIR = ROOT / "playbook"
BUSINESS_ROOT = ROOT / "business"
CONFIG_FILE = ROOT / "config.json"
ENV_FILE = ROOT / ".env"

CHANNELS = ("bot", "userbot")

# Разделы знаний. Порядок берётся из config.json, набор — отсюда: пускать
# в промпт произвольную папку с диска незачем.
KNOWLEDGE_SECTIONS = ("business", "playbook")
DEFAULT_KNOWLEDGE_ORDER = ("business", "playbook")

# Кто расшифровывает голосовые. auto — тем ключом, который есть, ElevenLabs первым:
# он же озвучивает ответы, значит на эфире хватает одного голосового ключа.
STT_MODES = ("auto", "elevenlabs", "openai", "off")

# Пределы Telegram и здравого смысла — не настройки, а факты платформы.
TELEGRAM_MESSAGE_LIMIT = 4000
TELEGRAM_ACTION_TTL_SEC = 4.0  # индикатор «печатает» гаснет через пять секунд
MAX_VOICE_BYTES = 20 * 1024 * 1024
MAX_INCOMING_CHARS = 4000

TEST_UID = 999_000_001  # диалог команды /asclient, клиентам не принадлежит


def load_env(path: Path) -> None:
    """Минимальный .env-парсер: KEY=value, кавычки и # в начале строки."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_int(name: str, default: int = 0) -> int:
    try:
        return int(env(name) or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class Pace:
    """Насколько по-человечески продавец печатает."""

    debounce_sec: float = 6.0       # ждём, вдруг человек дописывает
    typing_cps: float = 18.0        # знаков в секунду
    min_delay: float = 2.0
    max_delay: float = 25.0
    jitter: tuple[float, float] = (0.8, 1.2)   # разброс задержки
    reading_pause: tuple[float, float] = (0.5, 2.5)  # «прочитал сообщение»
    max_parts: int = 3              # сообщений подряд
    history_limit: int = 40         # реплик в контексте


@dataclass(frozen=True)
class Followup:
    """Напоминания молчащим."""

    hours: float = 20.0
    max_touches: int = 2
    check_every_sec: float = 600.0


@dataclass(frozen=True)
class VoiceSettings:
    """Озвучка ответов. enabled False — продавец работает текстом."""

    enabled: bool = False
    voice_id: str = ""
    whose_voice: str = ""
    character: str = ""
    model: str = "eleven_multilingual_v2"
    settings: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Settings:
    """Всё, чем настраивается поведение продавца. Собирается один раз в bot.py."""

    channel: str
    business: str
    business_dir: Path
    knowledge_order: tuple[str, ...]
    model: str
    effort: str
    stt: str
    holding_line: str
    session_path: Path
    pace: Pace
    followup: Followup
    voice: VoiceSettings

    # Секреты. В логи и в сообщения владельцу не попадают — см. secrets_to_scrub.
    bot_token: str
    admin_chat_id: int
    anthropic_key: str
    openai_key: str
    eleven_key: str
    tg_api_id: int
    tg_api_hash: str

    @property
    def stt_backend(self) -> str:
        """Чем расшифровываем голосовые. Пусто — нечем, попросим написать текстом."""
        if self.stt == "off":
            return ""
        if self.stt in ("auto", "elevenlabs") and self.eleven_key:
            return "elevenlabs"
        if self.stt in ("auto", "openai") and self.openai_key:
            return "openai"
        return ""

    @property
    def listens_to_voice(self) -> bool:
        return bool(self.stt_backend)

    @property
    def speaks_voice(self) -> bool:
        """Озвучка требует всего сразу: ключа, голоса и ffmpeg."""
        return bool(
            self.eleven_key
            and self.voice.enabled
            and self.voice.voice_id
            and "{{" not in self.voice.voice_id
            and shutil.which("ffmpeg")
        )

    def secrets_to_scrub(self) -> list[str]:
        """Строки, которых не должно быть ни в логе, ни в сообщении владельцу."""
        return [s for s in (
            self.bot_token, self.anthropic_key, self.openai_key,
            self.eleven_key, self.tg_api_hash,
        ) if len(s) >= 8]


def _pace_from(raw: dict) -> Pace:
    return Pace(
        debounce_sec=float(raw.get("debounce_sec", Pace.debounce_sec)),
        typing_cps=float(raw.get("typing_cps", Pace.typing_cps)),
        min_delay=float(raw.get("min_delay", Pace.min_delay)),
        max_delay=float(raw.get("max_delay", Pace.max_delay)),
        max_parts=int(raw.get("max_parts", Pace.max_parts)),
        history_limit=int(raw.get("history_limit", Pace.history_limit)),
    )


def _followup_from(raw: dict) -> Followup:
    return Followup(
        hours=float(raw.get("hours", Followup.hours)),
        max_touches=int(raw.get("max", Followup.max_touches)),
    )


def _voice_from(raw: dict) -> VoiceSettings:
    return VoiceSettings(
        enabled=bool(raw.get("enabled", False)),
        voice_id=str(raw.get("voice_id", "")),
        whose_voice=str(raw.get("whose_voice", "")),
        character=str(raw.get("character", "")),
        model=str(raw.get("model", VoiceSettings.model)),
        settings=dict(raw.get("settings", {})),
    )


def _knowledge_order_from(raw: list | None) -> tuple[str, ...]:
    """Порядок разделов знаний. Правила канала всё равно идут последними — см. knowledge.py."""
    if not raw:
        return DEFAULT_KNOWLEDGE_ORDER
    order = tuple(str(name).strip() for name in raw)
    unknown = [name for name in order if name not in KNOWLEDGE_SECTIONS]
    if unknown:
        raise SystemExit(
            f"Неизвестные разделы знаний в config.json: {', '.join(unknown)}. "
            f"Бывают: {', '.join(KNOWLEDGE_SECTIONS)}"
        )
    return order


def load(config_file: Path = CONFIG_FILE, env_file: Path = ENV_FILE) -> Settings:
    """Читает config.json и .env и отдаёт готовые настройки."""
    load_env(env_file)
    raw = json.loads(config_file.read_text(encoding="utf-8"))

    channel = raw.get("channel", "bot")
    if channel not in CHANNELS:
        raise SystemExit(
            f'Неизвестный канал "{channel}" в config.json: бывает ' + " или ".join(CHANNELS)
        )
    stt = raw.get("stt", "auto")
    if stt not in STT_MODES:
        raise SystemExit(
            f'Неизвестное значение stt "{stt}" в config.json: бывает ' + ", ".join(STT_MODES)
        )
    session = raw.get("userbot", {}).get("session", "seller")

    return Settings(
        channel=channel,
        business=raw["business"],
        business_dir=BUSINESS_ROOT / raw["business"],
        knowledge_order=_knowledge_order_from(raw.get("knowledge_order")),
        model=raw.get("model", "claude-opus-5"),
        effort=raw.get("effort", "low"),
        stt=stt,
        holding_line=raw.get("holding_line", "Секунду, уточню и вернусь"),
        session_path=SESSION_DIR / session,
        pace=_pace_from(raw.get("pace", {})),
        followup=_followup_from(raw.get("followup", {})),
        voice=_voice_from(raw.get("voice", {})),
        bot_token=env("BOT_TOKEN"),
        admin_chat_id=env_int("ADMIN_CHAT_ID"),
        anthropic_key=env("ANTHROPIC_API_KEY"),
        openai_key=env("OPENAI_API_KEY"),
        eleven_key=env("ELEVENLABS_API_KEY"),
        tg_api_id=env_int("TG_API_ID"),
        tg_api_hash=env("TG_API_HASH"),
    )


def check(settings: Settings) -> None:
    """Падаем на старте с понятной ошибкой, а не через час на первом клиенте."""
    if not settings.anthropic_key:
        raise SystemExit("Нет ANTHROPIC_API_KEY в .env — продавцу нечем думать.")

    if settings.channel == "bot":
        if not settings.bot_token:
            raise SystemExit("Канал bot, но в .env нет BOT_TOKEN. Взять у @BotFather.")
        return

    if not (settings.tg_api_id and settings.tg_api_hash):
        raise SystemExit(
            "Канал userbot, но в .env нет TG_API_ID и TG_API_HASH.\n"
            "Взять на my.telegram.org → API development tools."
        )
    if not settings.session_path.with_suffix(".session").exists():
        raise SystemExit(
            f"Нет сессии {settings.session_path.name}.session — аккаунт не авторизован.\n"
            "Запусти один раз: python tools/login-userbot.py"
        )
