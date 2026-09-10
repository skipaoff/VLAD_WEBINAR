"""Пульт владельца: разбор команд и их действие на диалог."""

from __future__ import annotations

import pytest

from conftest import CLIENT_UID as CLIENT
from seller import admin
from seller.config import TEST_UID


async def test_неизвестное_слово_командой_не_считается(seller):
    engine, _, _ = seller
    assert await admin.handle(engine, "привет как дела") is None
    assert admin.looks_like_command("привет") is False
    assert admin.looks_like_command("/status") is True


async def test_pause_и_resume_переключают_продавца(seller):
    engine, _, _ = seller
    await admin.handle(engine, "/pause")
    assert engine.paused is True
    await admin.handle(engine, "/resume")
    assert engine.paused is False


async def test_mute_и_unmute_меняют_диалог(seller):
    engine, _, _ = seller
    await admin.handle(engine, f"/mute {CLIENT}")
    assert engine.memory.load(CLIENT)["muted"] is True
    await admin.handle(engine, f"/unmute {CLIENT}")
    assert engine.memory.load(CLIENT)["muted"] is False


async def test_say_отправляет_и_запоминает(seller):
    engine, channel, _ = seller
    answer = await admin.handle(engine, f"/say {CLIENT} добрый день")
    assert channel.sent == [(CLIENT, "добрый день")]
    assert engine.memory.load(CLIENT)["messages"][-1]["text"] == "добрый день"
    assert "Отправлено" in answer


async def test_say_без_текста_объясняет_как_надо(seller):
    engine, channel, _ = seller
    answer = await admin.handle(engine, f"/say {CLIENT}")
    assert "Как:" in answer
    assert channel.sent == []


async def test_кривой_id_не_роняет_пульт(seller):
    engine, _, _ = seller
    answer = await admin.handle(engine, "/hist абракадабра")
    assert "не похоже на id" in answer


async def test_hist_показывает_последние_реплики(seller):
    engine, _, _ = seller
    await admin.handle(engine, f"/say {CLIENT} первое")
    await admin.handle(engine, f"/say {CLIENT} второе")
    answer = await admin.handle(engine, f"/hist {CLIENT}")
    assert "первое" in answer and "второе" in answer


async def test_asclient_не_трогает_клиентов(seller):
    engine, channel, brain = seller
    brain.reply = "Стол от 68 000. В квартиру или в дом?"

    answer = await admin.handle(engine, "/asclient сколько стоит стол")

    assert channel.sent == [], "клиентам ничего не ушло"
    assert "68 000" in answer
    assert engine.memory.exists(TEST_UID)

    await admin.handle(engine, "/asclient reset")
    assert not engine.memory.exists(TEST_UID)


async def test_asclient_показывает_эскалацию(seller):
    engine, _, brain = seller
    brain.reply = "Уточню.\n[[ESCALATE: точная смета]]"
    answer = await admin.handle(engine, "/asclient точную цену назови")
    assert "эскалация" in answer and "точная смета" in answer


async def test_упавшая_команда_не_роняет_продавца(seller):
    engine, channel, brain = seller
    brain.error = RuntimeError("модель недоступна")
    answer = await admin.handle(engine, "/asclient привет")
    assert "Не сгенерировалось" in answer


async def test_status_собирается(seller):
    engine, _, _ = seller
    answer = await admin.handle(engine, "/status")
    assert "Канал" in answer and "Модель" in answer


async def test_у_каждой_команды_есть_обработчик():
    for name in admin.COMMANDS:
        assert name in admin._HANDLERS, f"/{name} объявлена, но не реализована"
