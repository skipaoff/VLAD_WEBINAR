"""Слушает голосовые клиента и озвучивает ответы продавца.

Расшифровка — ElevenLabs или OpenAI, озвучка — ElevenLabs. По умолчанию слушает
и говорит один и тот же ключ ElevenLabs: на эфире это на один ключ меньше.
Нет ключа — обе операции честно возвращают пустоту, и продавец работает текстом.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from .config import VoiceSettings

log = logging.getLogger("seller")

STT_TIMEOUT_SEC = 180
TTS_TIMEOUT_SEC = 180
ELEVEN_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
ELEVEN_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
ELEVEN_STT_MODEL = "scribe_v1"
OPENAI_STT_MODEL = "gpt-4o-transcribe"
OPUS_BITRATE = "48k"      # голосовое Telegram: ogg/opus, этого битрейта хватает


class Voice:
    """Расшифровывает входящее и синтезирует исходящее. Оба метода не бросают:
    не вышло — пустая строка и None соответственно, причина в логе."""

    def __init__(
        self,
        backend: str,
        openai_key: str,
        eleven_key: str,
        settings: VoiceSettings,
        speaks: bool,
    ) -> None:
        self.backend = backend            # "elevenlabs", "openai" или пусто
        self.eleven_key = eleven_key
        self.settings = settings
        self.listens = bool(backend)
        self.speaks = speaks
        self._openai = self._build_openai(openai_key) if backend == "openai" else None

    @staticmethod
    def _build_openai(api_key: str):
        """Клиент создаётся один раз на запуск, а не на каждое голосовое."""
        if not api_key:
            return None
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=api_key)

    async def transcribe(self, audio: Path) -> str:
        """Текст голосового. Пусто — расшифровать не вышло."""
        try:
            if self.backend == "elevenlabs":
                return await self._transcribe_eleven(audio)
            if self.backend == "openai":
                return await self._transcribe_openai(audio)
        except Exception as exc:  # noqa: BLE001 — попросим клиента написать текстом
            log.error("расшифровка не вышла (%s): %s", self.backend, exc)
        return ""

    async def _transcribe_eleven(self, audio: Path) -> str:
        async with httpx.AsyncClient(timeout=STT_TIMEOUT_SEC) as http:
            with open(audio, "rb") as handle:
                response = await http.post(
                    ELEVEN_STT_URL,
                    headers={"xi-api-key": self.eleven_key},
                    data={"model_id": ELEVEN_STT_MODEL},
                    files={"file": handle},
                )
        response.raise_for_status()
        return (response.json().get("text") or "").strip()

    async def _transcribe_openai(self, audio: Path) -> str:
        if self._openai is None:
            return ""
        result = await self._openai.audio.transcriptions.create(
            model=OPENAI_STT_MODEL, file=audio, timeout=STT_TIMEOUT_SEC
        )
        return (result.text or "").strip()

    async def synthesize(self, text: str) -> Path | None:
        """Путь к ogg/opus для голосового Telegram. None — озвучить не вышло."""
        if not self.speaks:
            return None
        try:
            mp3 = await self._request_speech(text)
            return await self._to_opus(mp3)
        except Exception as exc:  # noqa: BLE001 — молча падаем в текст
            log.error("озвучка не вышла: %s", exc)
            return None

    async def _request_speech(self, text: str) -> Path:
        async with httpx.AsyncClient(timeout=TTS_TIMEOUT_SEC) as http:
            response = await http.post(
                f"{ELEVEN_TTS_URL}/{self.settings.voice_id}",
                headers={"xi-api-key": self.eleven_key, "accept": "audio/mpeg"},
                json={
                    "text": text,
                    "model_id": self.settings.model,
                    "voice_settings": self.settings.settings,
                },
            )
        response.raise_for_status()
        mp3 = Path(tempfile.mkstemp(suffix=".mp3")[1])
        mp3.write_bytes(response.content)
        return mp3

    @staticmethod
    async def _to_opus(mp3: Path) -> Path:
        """Без этого Telegram покажет ответ файлом, а не голосовым."""
        ogg = mp3.with_suffix(".ogg")
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
                 "-c:a", "libopus", "-b:a", OPUS_BITRATE, str(ogg)],
                check=True,
            )
        finally:
            mp3.unlink(missing_ok=True)
        return ogg


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))
