"""Общая обвязка тестов: продавец, собранный на поддельном канале.

Ни Telegram, ни Claude, ни файлов клиента — знания подменяются крошечным
заполненным бизнесом во временной папке, всё остальное поддельное.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
# Именно append, а не insert: рядом с seller/ лежит bot.py, и в начале пути он
# перекрыл бы пакет bot/ соседнего модуля, когда тесты гоняют из корня репозитория.
sys.path.append(str(MODULE_ROOT))
# Из корня репозитория pytest импортирует тесты через importlib, и папка tests
# на пути не оказывается. Без этой строки `from conftest import ...` не найдётся.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seller.brain import Brain  # noqa: E402
from seller.channels.base import Channel  # noqa: E402
from seller.config import Followup, Pace, Settings, VoiceSettings  # noqa: E402
from seller.engine import Engine  # noqa: E402
from seller.knowledge import Knowledge  # noqa: E402
from seller.memory import Memory  # noqa: E402
from seller.voice import Voice  # noqa: E402

CLIENT_UID = 4242
FAST_DEBOUNCE_SEC = 0.05

# Бизнес для тестов: заполненный, крошечный и ни на кого не похожий.
FAKE_BUSINESS = """# Кто ты

Ты — Ася из «Мастерской». Пишешь на русском.

# Прайс

Стол из ясеня — 68 000, доставка включена.
"""


class FakeChannel(Channel):
    """Канал, который никуда не ходит и всё записывает."""

    name = "поддельный"

    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []
        self.voices: list[int] = []
        self.owner: list[str] = []
        self.forwarded = 0
        self.engine = None
        self.fail_send = False

    @property
    def has_owner(self) -> bool:
        return True

    async def send_text(self, uid: int, text: str) -> None:
        if self.fail_send:
            raise RuntimeError("Telegram недоступен")
        self.sent.append((uid, text))

    async def send_voice(self, uid: int, ogg: Path) -> bool:
        self.voices.append(uid)
        return True

    async def show_typing(self, uid: int, seconds: float) -> None:
        pass  # в тестах не ждём

    async def show_recording(self, uid: int, seconds: float) -> None:
        pass

    async def notify_owner(self, html_text: str) -> None:
        self.owner.append(html_text)

    async def forward_to_owner(self, raw_message) -> None:
        self.forwarded += 1

    async def fetch_voice(self, raw_message, dest: Path) -> bool:
        return False

    def run(self) -> None:
        raise NotImplementedError("поддельный канал не запускается")


class FakeBrain:
    """Отвечает заранее заданной строкой или бросает заданную ошибку."""

    def __init__(self, knowledge: Knowledge) -> None:
        self.knowledge = knowledge
        self.reply = ""
        self.error: Exception | None = None
        self.asked: list[list[dict]] = []

    async def ask(self, messages: list[dict]) -> str:
        self.asked.append(messages)
        if self.error is not None:
            raise self.error
        return self.reply


def make_business(tmp_path: Path) -> Path:
    folder = tmp_path / "business"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "00-vse.md").write_text(FAKE_BUSINESS, encoding="utf-8")
    return folder


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        channel="bot",
        business="тестовый",
        business_dir=make_business(tmp_path),
        knowledge_order=("business", "playbook"),
        model="claude-opus-5",
        effort="low",
        stt="auto",
        holding_line="Секунду, уточню и вернусь",
        session_path=tmp_path / "seller",
        pace=Pace(debounce_sec=FAST_DEBOUNCE_SEC),
        followup=Followup(),
        voice=VoiceSettings(),
        bot_token="111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        admin_chat_id=1,
        anthropic_key="sk-ant-test-key-value",
        openai_key="",
        eleven_key="",
        tg_api_id=0,
        tg_api_hash="",
    )


@pytest.fixture
def seller(tmp_path):
    """Готовый продавец: (engine, channel, brain). Память — во временной папке."""
    settings = make_settings(tmp_path)
    channel = FakeChannel()
    knowledge = Knowledge(
        sections=[
            ("business", settings.business_dir),
            ("playbook", MODULE_ROOT / "playbook"),
        ],
        voice=settings.voice,
        speaks_voice=False,
    )
    brain = FakeBrain(knowledge)
    voice = Voice(
        backend="", openai_key="", eleven_key="",
        settings=settings.voice, speaks=False,
    )
    memory = Memory(state_dir=tmp_path / "state", history_limit=settings.pace.history_limit)
    engine = Engine(channel, settings, brain, voice, memory)
    channel.engine = engine
    return engine, channel, brain


@pytest.fixture
def real_brain_class():
    """Настоящий Brain — нужен тестам, которые проверяют его контракт."""
    return Brain
