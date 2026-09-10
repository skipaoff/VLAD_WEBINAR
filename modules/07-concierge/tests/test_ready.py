"""Готов ли консьерж к работе и не разъехались ли предохранители."""

from __future__ import annotations

import json
import re
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((MODULE_ROOT / "config.json").read_text(encoding="utf-8"))
KNOWLEDGE = MODULE_ROOT / "knowledge"
CODE = (MODULE_ROOT / "concierge.py").read_text(encoding="utf-8")

PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")


def test_two_knowledge_folders() -> None:
    """Что предлагаем и как писать — две папки, как и в остальных модулях."""
    folders = {p.name for p in KNOWLEDGE.iterdir() if p.is_dir()}
    assert folders == {"what-we-offer", "how-to-write"}, folders


def test_how_to_write_is_prefilled() -> None:
    """Правила переписки написаны заранее — владельцу их заполнять не надо."""
    for path in (KNOWLEDGE / "how-to-write").glob("*.md"):
        assert not PLACEHOLDER.findall(path.read_text(encoding="utf-8")), path.name


def test_no_llm_key_anywhere() -> None:
    """Мозги снаружи: своего ключа модели у модуля нет и быть не должно."""
    env = (MODULE_ROOT / ".env.example").read_text(encoding="utf-8")
    for token in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "anthropic", "openai"):
        assert token not in env, f"в .env.example появился {token}"
        assert token not in CODE, f"в concierge.py появился {token}"


def test_limits_are_sane() -> None:
    lim = CONFIG["limits"]
    assert lim["max_per_run"] <= lim["hard_ceiling"] <= 20, "потолок больше двадцати — это уже рассылка"
    assert lim["max_per_day"] <= lim["hard_ceiling"]
    pace = CONFIG["pace"]
    assert pace["min_gap_sec"] >= 60, "пауза меньше минуты выглядит как автомат"
    assert pace["max_gap_sec"] > pace["min_gap_sec"], "пауза должна быть случайной, а не фиксированной"


def test_stop_words_present() -> None:
    words = " ".join(CONFIG["stop_words"]).lower()
    for must in ("не пиши", "спам", "отпишись"):
        assert must in words, f"нет стоп-слова: {must}"


def test_code_enforces_guards() -> None:
    """Предохранители живут в коде, а не в просьбе к модели."""
    for guard in (
        "hard_ceiling",          # потолок списка
        "max_per_run",           # потолок за прогон
        "max_per_day",           # суточный потолок
        "PeerFloodError",        # остановка при ограничении
        "FloodWaitError",
        "уже писали",            # без повторов
        "каждое сообщение должно быть своим",  # без одинаковых текстов
        "--confirm",             # отправка только с подтверждением
    ):
        assert guard in CODE, f"из concierge.py пропал предохранитель: {guard}"


def test_leads_ceiling_matches_config() -> None:
    example = (MODULE_ROOT / "leads.example.csv").read_text(encoding="utf-8")
    rows = [l for l in example.splitlines() if l and not l.startswith("#") and "," in l]
    assert len(rows) - 1 <= CONFIG["limits"]["hard_ceiling"]
