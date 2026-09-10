"""Превращает историю диалога в ответ продавца через Claude.

Знания уезжают системным промптом под кэш, вся изменчивая часть — в сообщениях.
"""

from __future__ import annotations

import logging
import re

import anthropic

from .knowledge import Knowledge

log = logging.getLogger("seller")

ESCALATE_RE = re.compile(r"\[\[ESCALATE:(.*?)\]\]", re.DOTALL)
MAX_TOKENS = 2000
CACHE_TTL = "1h"          # знания большие и не меняются — держим их в кэше час
PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def split_reply(reply: str, max_parts: int) -> tuple[list[str], list[str]]:
    """Режет ответ на сообщения и отделяет пометки эскалации.

    Возвращает (что отправить клиенту, что показать владельцу). Пустой первый
    список означает, что отправлять нечего.
    """
    escalations = [m.strip() for m in ESCALATE_RE.findall(reply)]
    clean = ESCALATE_RE.sub("", reply).strip()
    parts = [p.strip() for p in PARAGRAPH_BREAK.split(clean) if p.strip()]
    if len(parts) > max_parts:
        parts = parts[: max_parts - 1] + ["\n\n".join(parts[max_parts - 1 :])]
    return parts, escalations


class Brain:
    """Один вопрос — один ответ продавца. Пустая строка означает «ответа нет»."""

    def __init__(self, api_key: str, model: str, effort: str, knowledge: Knowledge) -> None:
        self.model = model
        self.effort = effort
        self.knowledge = knowledge
        self.client = anthropic.AsyncAnthropic(api_key=api_key)

    async def ask(self, messages: list[dict]) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": self.knowledge.prompt(),
                    "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
                }
            ],
            output_config={"effort": self.effort},
            messages=messages,
        )
        if response.stop_reason == "refusal":
            log.warning("модель отказалась отвечать: %s", response.stop_details)
            return ""
        return "".join(b.text for b in response.content if b.type == "text").strip()
