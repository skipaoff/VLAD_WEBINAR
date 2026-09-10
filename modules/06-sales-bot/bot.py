"""Простой продавец в Telegram.

Один файл, никаких фреймворков. Бот забирает сообщения long polling'ом, отвечает через
Claude по методологии продаж и базе знаний о продукте, умеет слушать и отправлять голосовые.

Осознанно примитивный: нет админки, нет этапов воронки, нет мини-аппа, нет базы данных.
Состояние диалога — обычный JSON-файл на чат. Так его можно поставить за пять минут
и починить, не разбираясь в чужой архитектуре.

Запуск:  python bot.py
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"
TG_FILES = f"https://api.telegram.org/file/bot{BOT_TOKEN}"

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "low")

FOLLOWUP_HOURS = float(os.environ.get("FOLLOWUP_HOURS", "20"))
FOLLOWUP_MAX = int(os.environ.get("FOLLOWUP_MAX", "2"))

TENANT = json.loads((ROOT / "tenant.json").read_text(encoding="utf-8"))
VOICE = TENANT["voice"]

# Голос включается, только если есть и ключ, и заполненный id голоса.
# Нет чего-то одного — бот работает текстом и ничего не ломается.
ELEVEN_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
VOICE_ON = bool(ELEVEN_KEY and VOICE.get("enabled") and "{{" not in VOICE.get("voice_id", ""))

STATE_DIR = ROOT / "state"
STATE_DIR.mkdir(exist_ok=True)

HISTORY_LIMIT = 40  # сообщений на чат; дальше режем самые старые
SPLIT = "<<<split>>>"

claude = anthropic.Anthropic()


# ─── системный промпт ──────────────────────────────────────────────────────

def knowledge_files() -> list[Path]:
    """Файлы знаний в порядке из tenant.json.

    Порядок задан папками, а не списком файлов: сначала что продаём, потом как продаём.
    Внутри папки файлы читаются по алфавиту, поэтому имена начинаются с номера.
    """
    files: list[Path] = []
    for folder in TENANT["knowledge_order"]:
        root = ROOT / folder
        if not root.is_dir():
            raise SystemExit(f"Папки знаний нет: {folder}")
        found = sorted(root.rglob("*.md"))
        if not found:
            raise SystemExit(f"Папка знаний пуста: {folder}")
        files.extend(found)
    return files


def build_system() -> str:
    """Системный промпт: кто говорит плюс всё, что он знает.

    Код ничего не знает о бизнесе. Всё знание живёт в knowledge/, всё, кем бот
    работает, — в tenant.json. Поменять бизнес значит поменять эти файлы, не код.
    """
    head = (
        f"Ты продавец в переписке. Бизнес: {TENANT['brand_name']}. "
        f"Тебя зовут {TENANT['seller_name']}. Язык переписки: {TENANT['language']}. "
        f"Сайт: {TENANT['site_url']}.\n"
        "Ниже — всё, что ты знаешь. Чего здесь нет — того ты не обещаешь и не выдумываешь."
    )

    parts = [head]
    for path in knowledge_files():
        parts.append(path.read_text(encoding="utf-8"))

    if VOICE_ON:
        parts.append(
            "Часть ответов уходит голосовым сообщением, озвученным голосом "
            f"({TENANT['voice']['whose_voice']}, {TENANT['voice']['character']}). "
            "Поэтому пиши так, чтобы это было не стыдно произнести вслух: "
            "короткие фразы, без списков, ссылок и скобок."
        )

    text = "\n\n".join(parts)
    if "{{" in text:
        raise SystemExit(
            "Остались метки {{...}} в knowledge/ или tenant.json — заполни их, "
            "иначе бот прочитает их клиенту вслух."
        )
    return text


SYSTEM = build_system()


# ─── состояние диалога ─────────────────────────────────────────────────────

def state_path(chat_id: int) -> Path:
    return STATE_DIR / f"{chat_id}.json"


def load_state(chat_id: int) -> dict:
    path = state_path(chat_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"history": [], "last_client_at": 0, "followups": 0, "voice": False}


def save_state(chat_id: int, state: dict) -> None:
    state["history"] = state["history"][-HISTORY_LIMIT:]
    state_path(chat_id).write_text(
        json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8"
    )


# ─── Telegram ──────────────────────────────────────────────────────────────

def tg(method: str, **params):
    r = requests.post(f"{TG}/{method}", data=params, timeout=60)
    return r.json()


def send_text(chat_id: int, text: str) -> None:
    for part in [p.strip() for p in text.split(SPLIT) if p.strip()]:
        tg("sendChatAction", chat_id=chat_id, action="typing")
        time.sleep(min(2.0, 0.4 + len(part) / 200))
        tg("sendMessage", chat_id=chat_id, text=part)


def send_voice(chat_id: int, text: str) -> bool:
    ogg = tts(text.replace(SPLIT, " "))
    if not ogg:
        return False
    tg("sendChatAction", chat_id=chat_id, action="record_voice")
    with open(ogg, "rb") as fh:
        requests.post(
            f"{TG}/sendVoice", data={"chat_id": chat_id}, files={"voice": fh}, timeout=120
        )
    os.unlink(ogg)
    return True


def download_voice(file_id: str) -> Path | None:
    info = tg("getFile", file_id=file_id)
    if not info.get("ok"):
        return None
    path = info["result"]["file_path"]
    data = requests.get(f"{TG_FILES}/{path}", timeout=120).content
    tmp = Path(tempfile.mkstemp(suffix=".oga")[1])
    tmp.write_bytes(data)
    return tmp


# ─── голос ─────────────────────────────────────────────────────────────────

def stt(audio: Path) -> str:
    """Расшифровка голосового клиента. Пусто — значит не получилось."""
    if not ELEVEN_KEY:
        return ""
    try:
        with open(audio, "rb") as fh:
            r = requests.post(
                "https://api.elevenlabs.io/v1/speech-to-text",
                headers={"xi-api-key": ELEVEN_KEY},
                data={"model_id": "scribe_v1"},
                files={"file": fh},
                timeout=180,
            )
        r.raise_for_status()
        return (r.json().get("text") or "").strip()
    except Exception as e:
        print("stt не сработал:", e)
        return ""


def tts(text: str) -> str | None:
    """Озвучка ответа. Возвращает путь к ogg или None."""
    if not VOICE_ON:
        return None
    try:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE['voice_id']}",
            headers={"xi-api-key": ELEVEN_KEY, "accept": "audio/mpeg"},
            json={
                "text": text,
                "model_id": VOICE.get("model", "eleven_multilingual_v2"),
                "voice_settings": VOICE.get("settings", {}),
            },
            timeout=180,
        )
        r.raise_for_status()
        mp3 = Path(tempfile.mkstemp(suffix=".mp3")[1])
        mp3.write_bytes(r.content)
        ogg = str(mp3).replace(".mp3", ".ogg")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
             "-c:a", "libopus", "-b:a", "48k", ogg],
            check=True,
        )
        os.unlink(mp3)
        return ogg
    except Exception as e:
        print("tts не сработал:", e)
        return None


# ─── Claude ────────────────────────────────────────────────────────────────

def ask_claude(history: list[dict], nudge: str | None = None) -> str:
    messages = list(history)
    if nudge:
        messages.append({"role": "user", "content": nudge})
    try:
        response = claude.messages.create(
            model=MODEL,
            max_tokens=1000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": EFFORT},
            messages=messages,
        )
    except Exception as e:
        print("claude не ответил:", e)
        return ""
    return "".join(b.text for b in response.content if b.type == "text").strip()


# ─── обработка сообщений ───────────────────────────────────────────────────

def handle(update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return

    state = load_state(chat_id)
    text = message.get("text", "")
    incoming_voice = False

    if message.get("voice"):
        audio = download_voice(message["voice"]["file_id"])
        text = stt(audio) if audio else ""
        if audio:
            os.unlink(audio)
        incoming_voice = True
        if not text:
            send_text(chat_id, "Не расслышал голосовое, напишите, пожалуйста, текстом 🙏")
            return

    if not text:
        return

    if text.strip() == "/start":
        state = {"history": [], "last_client_at": 0, "followups": 0, "voice": False}
        text = "Здравствуйте!"

    state["history"].append({"role": "user", "content": text})
    state["last_client_at"] = time.time()
    state["followups"] = 0
    # Голосом отвечаем только тому, кто сам пишет голосом — правило методологии.
    state["voice"] = incoming_voice

    reply = ask_claude(state["history"])
    if not reply:
        send_text(chat_id, "Секунду, уточню и вернусь 🙌")
        return

    state["history"].append({"role": "assistant", "content": reply})
    save_state(chat_id, state)

    if state["voice"] and VOICE_ON and send_voice(chat_id, reply):
        return
    send_text(chat_id, reply)


# ─── напоминания ───────────────────────────────────────────────────────────

NUDGE_TASK = (
    "Клиент молчит уже больше суток. Напиши ему одно короткое сообщение: "
    "напомни о себе по-человечески, дай пользу или уточни, насколько ещё актуально, "
    "и закончи вопросом. Без «ну что вы решили» и без давления."
)


def check_followups() -> None:
    """Одно-два касания и всё. Глубоких цепочек здесь нет намеренно."""
    now = time.time()
    for path in STATE_DIR.glob("*.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not state.get("history") or state.get("followups", 0) >= FOLLOWUP_MAX:
            continue
        if now - state.get("last_client_at", 0) < FOLLOWUP_HOURS * 3600:
            continue

        chat_id = int(path.stem)
        reply = ask_claude(state["history"], nudge=NUDGE_TASK)
        if not reply:
            continue
        state["history"].append({"role": "assistant", "content": reply})
        state["followups"] = state.get("followups", 0) + 1
        state["last_client_at"] = now  # следующее касание отсчитываем отсюда
        save_state(chat_id, state)
        send_text(chat_id, reply)


# ─── главный цикл ──────────────────────────────────────────────────────────

def main() -> None:
    print(f"Продавец запущен. Модель {MODEL}, голос {'включён' if VOICE_ON else 'выключен'}.")
    offset = None
    last_followup_check = 0.0

    while True:
        try:
            r = requests.get(
                f"{TG}/getUpdates",
                params={"timeout": 25, "offset": offset},
                timeout=40,
            ).json()
            for update in r.get("result", []):
                offset = update["update_id"] + 1
                try:
                    handle(update)
                except Exception as e:
                    print("сообщение не обработано:", e)

            if time.time() - last_followup_check > 600:
                last_followup_check = time.time()
                check_followups()

        except KeyboardInterrupt:
            print("Остановлен.")
            return
        except Exception as e:
            print(datetime.now(timezone.utc).isoformat(timespec="seconds"), "цикл:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
