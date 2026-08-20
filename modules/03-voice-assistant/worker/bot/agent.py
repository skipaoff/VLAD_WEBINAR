"""Точка входа сессии: человек нажал кнопку на сайте — здесь начинается разговор."""

from __future__ import annotations

import asyncio
import logging

from livekit.agents import (
    Agent,
    AgentSession,
    ConversationItemAddedEvent,
    JobContext,
    JobProcess,
    llm as lk_llm,
)
from livekit.plugins import google

from .composition_root import VoiceRuntime, build_runtime
from .lead import make_lead_tool
from .leak_detector import detect_leak, incident_line


def prewarm(proc: JobProcess) -> None:
    """Собрать рантайм один раз на процесс: база знаний и ключи не меняются.

    Падение здесь роняет воркер на старте — это и нужно: лучше не подняться,
    чем поднять ассистента без базы знаний.
    """
    proc.userdata["runtime"] = build_runtime()


def _build_session(runtime: VoiceRuntime) -> AgentSession[None]:
    """Разговор — речь-в-речь. Отдельный TTS обслуживает только приветствие."""
    return AgentSession(
        llm=google.realtime.RealtimeModel(
            model=runtime.settings.llm_model,
            api_key=runtime.gemini_api_key,
            voice=runtime.settings.voice,
            language=runtime.settings.language,
        ),
        tts=google.beta.GeminiTTS(
            model="gemini-3.1-flash-tts-preview",
            voice_name=runtime.settings.voice,
            api_key=runtime.gemini_api_key,
        ),
    )


async def _play_greeting(
    session: AgentSession[None], greeting: str, log: logging.Logger
) -> None:
    """Первая фраза звучит дословно. Если TTS упал — разговор всё равно идёт."""
    try:
        handle = session.say(greeting)
        await handle
        if (error := handle.exception()) is not None:
            raise error
    except Exception:
        log.warning("приветствие не проиграло, разговор продолжается")


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    runtime: VoiceRuntime = ctx.proc.userdata["runtime"]
    settings = runtime.settings
    runtime.log.info("звонок: room=%s", ctx.room.name)

    session = _build_session(runtime)

    # Детектор утечки: гасит сессию, если в реплике оказалась внутрянка.
    leak_stop = asyncio.Event()

    @session.on("conversation_item_added")
    def _on_item(ev: ConversationItemAddedEvent) -> None:
        item = ev.item
        if not isinstance(item, lk_llm.ChatMessage):
            return
        text = item.text_content
        if item.role != "assistant" or not text or leak_stop.is_set():
            return
        verdict = detect_leak(text)
        if verdict.leaked:
            runtime.log.error(incident_line(ctx.room.name, verdict.markers))
            leak_stop.set()

    agent = Agent(
        instructions=runtime.system_prompt,
        tools=[
            make_lead_tool(
                runtime.module_root / "worker" / settings.leads_path,
                ctx.room.name,
                runtime.log,
            )
        ],
    )

    await session.start(agent, room=ctx.room)
    await _play_greeting(session, settings.greeting, runtime.log)

    # Человек закрыл вкладку — job отменяется сервером. Иначе жёсткий потолок,
    # чтобы забытая открытая вкладка не жгла минуты.
    try:
        await asyncio.wait_for(leak_stop.wait(), timeout=settings.max_session_duration_sec)
        runtime.log.error("сессия закрыта детектором утечки: room=%s", ctx.room.name)
    except asyncio.TimeoutError:
        runtime.log.info("лимит %d с исчерпан: room=%s", settings.max_session_duration_sec, ctx.room.name)
    finally:
        await session.aclose()
        ctx.shutdown(reason="voice session end")
