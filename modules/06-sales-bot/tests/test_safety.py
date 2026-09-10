"""Секреты не должны утекать в лог и в личку владельцу."""

from __future__ import annotations

from seller.safety import MASK, scrub


def test_токен_вычищается_из_текста_ошибки():
    token = "111111:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    error = f"Cannot connect to https://api.telegram.org/bot{token}/sendMessage"
    cleaned = scrub(error, [token])
    assert token not in cleaned
    assert MASK in cleaned


def test_вычищаются_все_переданные_секреты():
    text = "key=sk-ant-secret and openai=sk-proj-secret"
    cleaned = scrub(text, ["sk-ant-secret", "sk-proj-secret"])
    assert "secret" not in cleaned


def test_без_секретов_текст_не_меняется():
    assert scrub("обычная ошибка", []) == "обычная ошибка"


def test_принимает_не_строку():
    assert scrub(ValueError("что-то"), []) == "что-то"


def test_короткие_значения_в_список_не_попадают(tmp_path):
    """Пустой или очень короткий ключ вычистил бы половину текста."""
    from conftest import make_settings

    settings = make_settings(tmp_path)
    secrets = settings.secrets_to_scrub()
    assert settings.bot_token in secrets
    assert settings.anthropic_key in secrets
    assert "" not in secrets, "пустые ключи не попадают в список"


def test_ошибка_владельцу_уходит_без_токена(seller):
    engine, channel, brain = seller
    token = engine.settings.bot_token
    assert token in scrub(f"fail {token}", []), "проверка самого теста"
    assert token not in engine.safe(f"Cannot POST /bot{token}/sendMessage")
