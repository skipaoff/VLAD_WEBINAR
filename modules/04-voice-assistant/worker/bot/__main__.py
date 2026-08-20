"""Запуск воркера.

    cd worker
    python -m bot start   # боевой режим
    python -m bot dev     # локальная отладка с автоперезапуском

Воркер заходит только в те комнаты, чей токен явно просит агента с этим именем
(explicit dispatch). Имя берётся из config.json и должно совпадать с тем, что
подставляет /api/voice-token на сайте.
"""

from __future__ import annotations

from livekit.agents import WorkerOptions, cli

from .agent import entrypoint, prewarm
from .composition_root import load_settings


def main() -> None:
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            agent_name=load_settings().agent_name,
        )
    )


if __name__ == "__main__":
    main()
