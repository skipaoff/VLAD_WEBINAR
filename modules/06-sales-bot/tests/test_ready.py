"""Готов ли продавец к запуску.

На чистом шаблоне зелёный: шаблон и должен быть с метками. Как только в config.json
поставлен настоящий бизнес — тесты требуют, чтобы он был заполнен до конца.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from seller import config
from seller.knowledge import SECTION_TITLES, STUB, files_in

MODULE_ROOT = Path(__file__).resolve().parents[1]
RAW_CONFIG = json.loads((MODULE_ROOT / "config.json").read_text(encoding="utf-8"))
TEMPLATE = MODULE_ROOT / "business" / "_template"
PLAYBOOK = MODULE_ROOT / "playbook"

TEMPLATE_FILES = (
    "00-role.md", "01-offer.md", "02-product.md", "03-prices.md", "04-audience.md",
    "05-terms.md", "06-voice.md", "07-targets.md", "08-price-play.md",
    "09-phrases.md", "10-limits.md",
)


def stubs_in(folder: Path) -> list[str]:
    found = []
    for path in files_in(folder):
        found += [f"{path.name}: {stub}" for stub in STUB.findall(path.read_text(encoding="utf-8"))]
    return found


# ─── знания ────────────────────────────────────────────────────────────────


def test_методология_полная_и_без_меток():
    assert len(files_in(PLAYBOOK)) >= 10, "методология неполная"
    assert not stubs_in(PLAYBOOK), "в playbook остались метки — там их быть не должно"


def test_шаблон_бизнеса_на_месте_целиком():
    """Одиннадцать файлов: если один потерялся, продавец не узнает целый пласт бизнеса."""
    missing = [name for name in TEMPLATE_FILES if not (TEMPLATE / name).exists()]
    assert not missing, f"в шаблоне нет файлов: {missing}"


def test_шаблон_остаётся_шаблоном():
    """В шаблоне метки быть должны — иначе его нечего заполнять."""
    assert stubs_in(TEMPLATE), "в шаблоне не осталось меток"


def test_шаблон_объясняет_каждый_файл():
    """README шаблона — инструкция владельцу: там должен быть назван каждый файл."""
    readme = (TEMPLATE / "README.md").read_text(encoding="utf-8")
    missing = [name for name in TEMPLATE_FILES if name not in readme]
    assert not missing, f"в README шаблона не описаны: {missing}"


def test_активный_бизнес_готов():
    name = RAW_CONFIG["business"]
    if name == "_template":
        pytest.skip("в config.json стоит _template — скопируй его под клиента и заполни")
    folder = MODULE_ROOT / "business" / name
    assert folder.is_dir(), f"нет папки business/{name}"
    assert files_in(folder), f"в business/{name} нет ни одного файла знаний"
    assert not stubs_in(folder), "остались незаполненные метки"


def test_у_активного_бизнеса_есть_прайс():
    name = RAW_CONFIG["business"]
    if name == "_template":
        pytest.skip("шаблон")
    text = "\n".join(p.read_text(encoding="utf-8") for p in files_in(MODULE_ROOT / "business" / name))
    assert re.search(r"\d", text), "в знаниях нет ни одной цифры — где прайс?"


# ─── настройки ─────────────────────────────────────────────────────────────


def test_канал_и_расшифровка_из_config_известны():
    assert RAW_CONFIG.get("channel", "bot") in config.CHANNELS
    assert RAW_CONFIG.get("stt", "auto") in config.STT_MODES


def test_порядок_знаний_описан_и_полон():
    """Оба раздела должны попасть в промпт: без методологии продавец — справочник."""
    order = config._knowledge_order_from(RAW_CONFIG.get("knowledge_order"))
    assert set(order) == set(config.KNOWLEDGE_SECTIONS), f"раздел потерялся: {order}"
    assert set(order) <= set(SECTION_TITLES), "у раздела нет заголовка в промпте"


def test_настройки_собираются_и_проверяются():
    settings = config.load()
    assert settings.business_dir.is_dir()
    assert settings.pace.debounce_sec > 0
    assert settings.pace.max_parts >= 1


def test_расшифровка_выбирается_по_ключам():
    """Один ключ ElevenLabs закрывает и слух, и голос — на эфире это важно."""
    settings = config.load()
    eleven = settings.__class__(**{**settings.__dict__, "eleven_key": "x" * 20})
    assert eleven.stt_backend == "elevenlabs"

    openai_only = settings.__class__(**{**settings.__dict__, "openai_key": "x" * 20})
    assert openai_only.stt_backend == "openai"

    deaf = settings.__class__(**{**settings.__dict__, "eleven_key": "", "openai_key": ""})
    assert deaf.stt_backend == "" and deaf.listens_to_voice is False


# ─── каналы ────────────────────────────────────────────────────────────────


def test_оба_канала_реализуют_контракт():
    """Смысл модуля — выбор транспорта. Каналов два, и оба умеют всё, что просит движок."""
    contract = (MODULE_ROOT / "seller" / "channels" / "base.py").read_text(encoding="utf-8")
    methods = re.findall(r"async def (\w+)|^    def (\w+)", contract, re.MULTILINE)
    required = {a or b for a, b in methods} - {"__init__"}

    for name in ("botapi", "userbot"):
        code = (MODULE_ROOT / "seller" / "channels" / f"{name}.py").read_text(encoding="utf-8")
        missing = [m for m in required if f"def {m}(" not in code]
        assert not missing, f"канал {name} не реализует: {missing}"


@pytest.mark.parametrize(
    "module,klass,dependency",
    [("botapi", "BotChannel", "telegram"), ("userbot", "UserbotChannel", "telethon")],
)
def test_канал_закрывает_все_абстрактные_методы(module, klass, dependency):
    """Проверка настоящим импортом — но только там, где зависимость канала поставлена."""
    pytest.importorskip(dependency, reason=f"канал {module} не установлен")
    import importlib

    channel = getattr(importlib.import_module(f"seller.channels.{module}"), klass)
    assert not channel.__abstractmethods__, f"{klass} не реализует: {channel.__abstractmethods__}"


# ─── секреты ───────────────────────────────────────────────────────────────


def test_код_ничего_не_знает_о_бизнесе():
    """В коде не должно быть продуктовых фактов — только загрузка файлов."""
    for path in (MODULE_ROOT / "seller").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in ("грн", "руб", "скидк", "консультаци"):
            assert word not in text, (
                f"в {path.name} просочился бизнес-факт ({word}) — его место в business/"
            )


def test_секреты_не_уезжают_в_репозиторий():
    gitignore = (MODULE_ROOT / ".gitignore").read_text(encoding="utf-8")
    for must in (".env", "state/", "session/", "*.session"):
        assert must in gitignore, f"{must} не в .gitignore"

    example = (MODULE_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in example.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            assert line.strip().endswith("="), f"в .env.example лежит значение: {line}"


def test_env_example_покрывает_все_ключи():
    """Каждый ключ, который читает config.load, должен быть в образце."""
    source = (MODULE_ROOT / "seller" / "config.py").read_text(encoding="utf-8")
    used = set(re.findall(r'env(?:_int)?\("([A-Z_]+)"', source))
    example = (MODULE_ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^([A-Z_]+)=", example, re.MULTILINE))
    assert used <= documented, f"нет в .env.example: {sorted(used - documented)}"


SECRET_HINTS = (
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}"),
    re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
)
SKIP_PARTS = {"__pycache__", ".git", ".venv", "state", "session", "logs", ".pytest_cache"}


def test_ничего_похожего_на_ключ_не_закоммичено():
    for path in MODULE_ROOT.rglob("*"):
        if not path.is_file() or path.name == ".env":
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix not in {".py", ".json", ".md", ".txt", ".example", ".sh"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_HINTS:
            assert not pattern.search(text), f"похоже на секрет в {path.relative_to(MODULE_ROOT)}"
