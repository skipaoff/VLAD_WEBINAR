"""Хранит переписку по каждому клиенту: JSON-файл на диалог, никакой базы.

Файл переживает перезапуск и читается глазами — этого достаточно.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger("seller")

CLIENT = "client"
SELLER = "seller"


def blank(uid: int) -> dict:
    return {
        "id": uid,
        "client": {},
        "muted": False,
        "voice": False,
        "created": time.time(),
        "last_client_at": 0.0,
        "followups": 0,
        "messages": [],
    }


def remember(mem: dict, role: str, text: str) -> None:
    """role: client или seller. Реплики владельца пишутся как seller — для модели
    это её собственные слова, и она продолжает разговор с их учётом."""
    mem.setdefault("messages", []).append({"role": role, "text": text, "ts": time.time()})


class Memory:
    """Читает и пишет диалоги, и переводит их в формат сообщений Claude."""

    def __init__(self, state_dir: Path, history_limit: int) -> None:
        self.state_dir = state_dir
        self.history_limit = history_limit

    def path_for(self, uid: int) -> Path:
        return self.state_dir / f"{uid}.json"

    def load(self, uid: int) -> dict:
        path = self.path_for(uid)
        if not path.exists():
            return blank(uid)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("битая память %s, начинаю заново", path.name)
            return blank(uid)

    def save(self, uid: int, mem: dict) -> None:
        """Пишем через временный файл: падение посреди записи не бьёт историю."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        mem["messages"] = mem.get("messages", [])[-self.history_limit * 2 :]
        tmp = self.path_for(uid).with_suffix(".tmp")
        tmp.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path_for(uid))

    def exists(self, uid: int) -> bool:
        return self.path_for(uid).exists()

    def forget(self, uid: int) -> None:
        self.path_for(uid).unlink(missing_ok=True)

    def dialogs(self) -> list[Path]:
        """Все диалоги, свежие первыми."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        return sorted(self.state_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    def as_messages(self, mem: dict, fresh: list[str], note: str | None = None) -> list[dict]:
        """История в формате Claude.

        Всё изменчивое — время, карточка клиента — живёт здесь, а не в системном
        промпте: иначе кэш промпта промахивался бы на каждом запросе.
        """
        messages = self._history_as_messages(mem)
        block = self._current_block(mem, fresh, note)
        if messages and messages[-1]["role"] == "user":
            messages[-1]["content"] += "\n\n" + block
        else:
            messages.append({"role": "user", "content": block})
        return messages

    def _history_as_messages(self, mem: dict) -> list[dict]:
        history = list(mem.get("messages", [])[-self.history_limit :])
        while history and history[0]["role"] != CLIENT:
            history.pop(0)  # диалог для API начинается с реплики клиента, иначе 400

        messages: list[dict] = []
        for item in history:
            role = "user" if item["role"] == CLIENT else "assistant"
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"] += "\n" + item["text"]
            else:
                messages.append({"role": role, "content": item["text"]})
        return messages

    @staticmethod
    def _current_block(mem: dict, fresh: list[str], note: str | None) -> str:
        client = mem.get("client", {})
        who = ", ".join(
            bit
            for bit in (
                client.get("name") or "",
                f"@{client['username']}" if client.get("username") else "",
                f"метка {client['entry']}" if client.get("entry") else "",
            )
            if bit
        )
        lines = [f"Сейчас {datetime.now().strftime('%d.%m.%Y %H:%M')}."]
        if who:
            lines.append(f"Собеседник: {who}.")
        block = "\n".join(lines)
        if fresh:
            block += "\n\n" + "\n".join(fresh)
        if note:
            block += f"\n\n{note}"
        return block
