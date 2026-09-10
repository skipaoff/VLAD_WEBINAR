"""Движок продаж на поддельном канале: без Telegram и без обращения к модели.

Проверяем то, ради чего движок отделён от транспорта: дебаунс, разбиение ответа,
эскалацию, перехват диалога владельцем, молчание на mute и выбор голоса.
"""

from __future__ import annotations

import asyncio
from conftest import CLIENT_UID as CLIENT
from seller.memory import SELLER


async def settle(engine) -> None:
    """Дождаться, пока отложенный ответ отработает."""
    await asyncio.sleep(0.15)
    for task in list(engine.timers.values()):
        if not task.done():
            await task


async def test_дебаунс_склеивает_подряд_идущие_сообщения(seller):
    engine, channel, brain = seller
    brain.reply = "Здравствуйте! Что за помещение?"

    await engine.on_client_text(CLIENT, "привет")
    await engine.on_client_text(CLIENT, "нужен стол")
    await engine.on_client_text(CLIENT, "и стеллаж")
    await settle(engine)

    assert len(channel.sent) == 1, "три сообщения подряд получают один ответ"
    assert len(brain.asked) == 1, "и один запрос к модели, а не три"
    history = engine.memory.load(CLIENT)["messages"]
    assert [m["text"] for m in history if m["role"] == "client"] == [
        "привет", "нужен стол", "и стеллаж",
    ], "но в памяти остаются все три реплики"


async def test_ответ_режется_по_пустой_строке(seller):
    engine, channel, brain = seller
    brain.reply = "Стол из ясеня от 68 000.\n\nВам в квартиру или в дом?"

    await engine.on_client_text(CLIENT, "сколько стоит")
    await settle(engine)

    assert [text for _, text in channel.sent] == [
        "Стол из ясеня от 68 000.",
        "Вам в квартиру или в дом?",
    ]


async def test_эскалация_уходит_владельцу_а_не_клиенту(seller):
    engine, channel, brain = seller
    brain.reply = "Уточню и вернусь.\n[[ESCALATE: точная смета на шкаф]]"

    await engine.on_client_text(CLIENT, "назовите точную цену")
    await settle(engine)

    assert channel.sent == [(CLIENT, "Уточню и вернусь.")]
    assert any("точная смета на шкаф" in note for note in channel.owner)
    assert not any("ESCALATE" in text for _, text in channel.sent)


async def test_модель_упала_клиент_не_остаётся_в_тишине(seller):
    engine, channel, brain = seller
    brain.error = RuntimeError("API упал")

    await engine.on_client_text(CLIENT, "привет")
    await settle(engine)

    assert channel.sent == [(CLIENT, engine.settings.holding_line)]
    assert any("Не смог ответить" in note for note in channel.owner)


async def test_пустой_ответ_модели_тоже_придерживает_клиента(seller):
    engine, channel, brain = seller
    brain.reply = "   "

    await engine.on_client_text(CLIENT, "привет")
    await settle(engine)

    assert channel.sent == [(CLIENT, engine.settings.holding_line)]
    assert any("пустой ответ" in note.lower() for note in channel.owner)


async def test_ошибка_отправки_не_роняет_диалог(seller):
    engine, channel, brain = seller
    brain.reply = "Первое.\n\nВторое."
    channel.fail_send = True

    await engine.on_client_text(CLIENT, "привет")
    await settle(engine)

    assert channel.sent == [], "ничего не ушло"
    assert any("Не смог отправить" in note for note in channel.owner), "владелец знает"


async def test_владелец_написал_сам_продавец_замолкает(seller):
    """Сценарий живого аккаунта: владелец вмешался в диалог со своего телефона."""
    engine, channel, brain = seller
    brain.reply = "Отвечаю"

    await engine.on_client_text(CLIENT, "привет")
    await settle(engine)
    assert len(channel.sent) == 1

    await engine.on_owner_wrote(CLIENT, "Здравствуйте, это Антон, дальше я сам")
    assert engine.memory.load(CLIENT)["muted"] is True
    assert any("замолчал" in note for note in channel.owner)

    await engine.on_client_text(CLIENT, "а когда замер?")
    await settle(engine)

    assert len(channel.sent) == 1, "на mute продавец не пишет"
    history = engine.memory.load(CLIENT)["messages"]
    assert history[-1]["text"] == "а когда замер?", "но реплику клиента запоминает"
    assert any(
        m["text"].startswith("Здравствуйте, это Антон") for m in history
    ), "и реплику владельца тоже"


async def test_повторный_перехват_не_спамит_владельца(seller):
    engine, channel, brain = seller
    await engine.on_owner_wrote(CLIENT, "первое")
    await engine.on_owner_wrote(CLIENT, "второе")
    assert sum("замолчал" in note for note in channel.owner) == 1


async def test_на_паузе_продавец_копит_но_молчит(seller):
    engine, channel, brain = seller
    brain.reply = "Отвечаю"
    engine.paused = True

    await engine.on_client_text(CLIENT, "привет")
    await settle(engine)

    assert channel.sent == []
    assert engine.memory.load(CLIENT)["messages"][-1]["text"] == "привет"


async def test_голосом_отвечаем_только_голосовому(seller, monkeypatch, tmp_path):
    engine, channel, brain = seller
    brain.reply = "Конечно"
    monkeypatch.setattr(engine.voice, "speaks", True)

    async def fake_synthesize(text):
        path = tmp_path / "fake.ogg"
        path.write_bytes(b"x")
        return path

    monkeypatch.setattr(engine.voice, "synthesize", fake_synthesize)

    await engine.on_client_text(CLIENT, "текстом")
    await settle(engine)
    assert not channel.voices, "написавшему текстом отвечаем текстом"

    mem = engine.memory.load(CLIENT)
    mem["voice"] = True
    engine.memory.save(CLIENT, mem)
    engine.pending[CLIENT].append("а голосом?")
    engine.schedule(CLIENT)
    await settle(engine)
    assert channel.voices == [CLIENT], "написавшему голосом отвечаем голосом"


async def test_без_ключа_openai_просим_написать_текстом(seller):
    engine, channel, brain = seller
    assert engine.voice.listens is False

    await engine.on_client_voice(CLIENT, raw_message=object(), size=1000)

    assert len(channel.sent) == 1
    assert "текстом" in channel.sent[0][1]
    assert channel.forwarded == 1, "голосовое всё равно уходит владельцу"


async def test_слишком_длинное_голосовое_отклоняется(seller, monkeypatch):
    engine, channel, brain = seller
    monkeypatch.setattr(engine.voice, "listens", True)

    await engine.on_client_voice(CLIENT, raw_message=object(), size=99 * 1024 * 1024)

    assert "Слишком длинное" in channel.sent[0][1]


async def test_новый_диалог_объявляется_один_раз(seller):
    engine, channel, brain = seller
    brain.reply = "Здравствуйте"

    await engine.on_client_text(CLIENT, "привет")
    await settle(engine)
    await engine.on_client_text(CLIENT, "ещё вопрос")
    await settle(engine)

    assert sum("Новый диалог" in note for note in channel.owner) == 1


async def test_метка_из_ссылки_попадает_в_карточку(seller):
    engine, channel, brain = seller
    brain.reply = "Здравствуйте"

    await engine.on_client_start(CLIENT, "instagram-sept", {"name": "Аня"})
    await settle(engine)

    assert engine.memory.load(CLIENT)["client"]["entry"] == "instagram-sept"
    assert any("instagram-sept" in note for note in channel.owner)


# ─── напоминания ───────────────────────────────────────────────────────────


def test_напоминание_нужно_только_когда_последнее_слово_за_продавцом(seller):
    engine, channel, brain = seller
    now = 1_000_000.0
    long_ago = now - engine.settings.followup.hours * 3600 - 1

    mem = engine.memory.load(CLIENT)
    mem["messages"] = [{"role": SELLER, "text": "жду ответа", "ts": long_ago}]
    mem["last_client_at"] = long_ago
    assert engine.needs_followup(CLIENT, mem, now) is True

    mem["messages"].append({"role": "client", "text": "думаю", "ts": long_ago})
    assert engine.needs_followup(CLIENT, mem, now) is False, "сначала ответ, потом напоминание"


def test_напоминаний_не_больше_лимита(seller):
    engine, channel, brain = seller
    now = 1_000_000.0
    long_ago = now - engine.settings.followup.hours * 3600 - 1
    mem = engine.memory.load(CLIENT)
    mem["messages"] = [{"role": SELLER, "text": "жду", "ts": long_ago}]
    mem["last_client_at"] = long_ago
    mem["followups"] = engine.settings.followup.max_touches
    assert engine.needs_followup(CLIENT, mem, now) is False


def test_на_mute_и_на_паузе_не_напоминаем(seller):
    engine, channel, brain = seller
    now = 1_000_000.0
    long_ago = now - engine.settings.followup.hours * 3600 - 1
    mem = engine.memory.load(CLIENT)
    mem["messages"] = [{"role": SELLER, "text": "жду", "ts": long_ago}]
    mem["last_client_at"] = long_ago

    mem["muted"] = True
    assert engine.needs_followup(CLIENT, mem, now) is False

    mem["muted"] = False
    engine.paused = True
    assert engine.needs_followup(CLIENT, mem, now) is False
