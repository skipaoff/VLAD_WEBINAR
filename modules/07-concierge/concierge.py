#!/usr/bin/env python3
"""Консьерж: пишет первым тем, кого ты сам выбрал.

Своего мозга у скрипта нет и не будет. Тексты пишет Claude Code, в котором ты
работаешь: он читает knowledge/, смотрит на лид и складывает готовое сообщение
в очередь. Скрипт только отправляет — по одному, с паузами, и следит, чтобы не
превысить лимиты.

Такое разделение сделано намеренно. Массовая рассылка одинакового текста —
это то, за что Telegram блокирует аккаунты. Здесь каждое сообщение пишется
отдельно и под конкретный бизнес, а темп задан так, чтобы поведение не
отличалось от живой переписки.

Команды:
    python concierge.py login                       разовая авторизация аккаунта
    python concierge.py check                       кто я, лимиты, что в очереди
    python concierge.py leads                       список лидов и статусы
    python concierge.py queue --to @user --text "…" положить сообщение в очередь
    python concierge.py drain --confirm             отправить очередь с паузами
    python concierge.py inbox                       новые ответы
    python concierge.py reply --to @user --text "…" ответить одному
    python concierge.py stop --to @user             вычеркнуть навсегда
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
LIMITS = CONFIG["limits"]
PACE = CONFIG["pace"]
STOP_WORDS = [w.lower() for w in CONFIG["stop_words"]]

STATE = ROOT / "state"
STATE.mkdir(exist_ok=True)
LEADS_FILE = ROOT / "leads.csv"
LEADS_STATE = STATE / "leads.json"
OUTBOX = STATE / "outbox.jsonl"
LOG = STATE / "log.txt"
SESSION = ROOT / "session" / CONFIG["session"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(line: str) -> None:
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(f"{now()}  {line}\n")
    print(line)


def die(msg: str) -> None:
    raise SystemExit(f"✗ {msg}")


# ─── лиды и состояние ──────────────────────────────────────────────────────

def norm(username: str) -> str:
    return "@" + username.strip().lstrip("@").lower()


def read_leads() -> dict[str, dict]:
    if not LEADS_FILE.exists():
        die(f"нет {LEADS_FILE.name} — скопируй leads.example.csv и заполни")
    rows: dict[str, dict] = {}
    with LEADS_FILE.open(encoding="utf-8") as fh:
        for row in csv.DictReader(l for l in fh if not l.startswith("#")):
            if not (row.get("username") or "").strip():
                continue
            key = norm(row["username"])
            rows[key] = {
                "username": key,
                "name": (row.get("name") or "").strip(),
                "business": (row.get("business") or "").strip(),
                "note": (row.get("note") or "").strip(),
            }
    if not rows:
        die("в leads.csv нет ни одного лида с username")
    if len(rows) > LIMITS["hard_ceiling"]:
        die(
            f"в leads.csv {len(rows)} лидов, потолок — {LIMITS['hard_ceiling']}. "
            "Это не рассылочный инструмент: больше за раз писать нельзя."
        )
    return rows


def load_state() -> dict:
    if LEADS_STATE.exists():
        return json.loads(LEADS_STATE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    LEADS_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def record(state: dict, key: str) -> dict:
    return state.setdefault(key, {"status": "new", "sent_at": 0, "replies": 0})


def sent_today(state: dict) -> int:
    today = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in state.values() if r.get("sent_day") == today)


# ─── очередь ───────────────────────────────────────────────────────────────

def queue_items() -> list[dict]:
    if not OUTBOX.exists():
        return []
    return [json.loads(l) for l in OUTBOX.read_text(encoding="utf-8").splitlines() if l.strip()]


def queue_write(items: list[dict]) -> None:
    OUTBOX.write_text(
        "".join(json.dumps(i, ensure_ascii=False) + "\n" for i in items), encoding="utf-8"
    )


# ─── Telegram ──────────────────────────────────────────────────────────────

def client():
    try:
        from telethon import TelegramClient
    except ImportError:
        die("нет Telethon: .venv/bin/pip install -r requirements.txt")
    api_id, api_hash = os.environ.get("TG_API_ID"), os.environ.get("TG_API_HASH")
    if not (api_id and api_hash):
        die("в .env нет TG_API_ID и TG_API_HASH — взять на my.telegram.org")
    SESSION.parent.mkdir(exist_ok=True)
    return TelegramClient(str(SESSION), int(api_id), api_hash)


async def with_client(fn):
    tg = client()
    await tg.connect()
    try:
        if not await tg.is_user_authorized():
            die("аккаунт не авторизован — сначала python concierge.py login")
        return await fn(tg)
    finally:
        await tg.disconnect()


# ─── команды ───────────────────────────────────────────────────────────────

async def cmd_login(_args) -> None:
    tg = client()
    print("Авторизация аккаунта. Номер и код вводятся здесь и никуда не пересылаются.")
    await tg.start()
    me = await tg.get_me()
    print(f"✓ вошли как {me.first_name} @{me.username or '—'} (id {me.id})")
    print(f"  файл сессии: {SESSION}.session — это ключ от аккаунта, не пересылай его")
    await tg.disconnect()


async def cmd_check(_args) -> None:
    leads, state = read_leads(), load_state()

    async def inner(tg):
        me = await tg.get_me()
        return f"{me.first_name} @{me.username or '—'}"

    who = await with_client(inner)
    statuses: dict[str, int] = {}
    for key in leads:
        statuses[record(state, key)["status"]] = statuses.get(record(state, key)["status"], 0) + 1

    print(f"аккаунт:      {who}")
    print(f"лидов:        {len(leads)}")
    print(f"по статусам:  {statuses}")
    print(f"в очереди:    {len(queue_items())}")
    print(f"отправлено сегодня: {sent_today(state)} из {LIMITS['max_per_day']}")
    print(f"темп:         пауза {PACE['min_gap_sec']}–{PACE['max_gap_sec']} с, "
          f"длинная пауза {PACE['long_break_sec']} с каждые {PACE['long_break_every']}")


async def cmd_leads(_args) -> None:
    leads, state = read_leads(), load_state()
    print(f"{'username':24} {'статус':10} {'бизнес'}")
    for key, lead in leads.items():
        r = record(state, key)
        print(f"{key:24} {r['status']:10} {lead['business'][:40]}")


async def cmd_queue(args) -> None:
    leads, state = read_leads(), load_state()
    key = norm(args.to)
    if key not in leads:
        die(f"{key} нет в leads.csv — писать можно только тем, кто в списке")

    r = record(state, key)
    if r["status"] in {"sent", "replied"}:
        die(f"{key} уже писали {r.get('sent_at_h', '')} — второй раз не пишем")
    if r["status"] == "stopped":
        die(f"{key} вычеркнут — писать нельзя")

    text = args.text.strip()
    if not text:
        die("пустой текст")
    if len(text) > 700:
        die("сообщение длиннее 700 знаков — первое сообщение должно читаться за три секунды")

    items = queue_items()
    if any(i["to"] == key for i in items):
        die(f"{key} уже в очереди")
    if len(items) >= LIMITS["max_per_run"]:
        die(f"в очереди уже {len(items)} — потолок за прогон {LIMITS['max_per_run']}")

    same = [i for i in items if i["text"].strip() == text]
    if same:
        die("такой же текст уже в очереди — каждое сообщение должно быть своим")

    items.append({"to": key, "text": text, "queued_at": now()})
    queue_write(items)
    r["status"] = "queued"
    save_state(state)
    print(f"✓ в очереди {len(items)}: {key}")


async def cmd_drain(args) -> None:
    items = queue_items()
    if not items:
        die("очередь пуста")
    state = load_state()

    left_today = LIMITS["max_per_day"] - sent_today(state)
    if left_today <= 0:
        die(f"дневной лимит {LIMITS['max_per_day']} исчерпан — продолжим завтра")
    if len(items) > left_today:
        print(f"! сегодня осталось {left_today} — отправлю столько, остальное останется в очереди")
        items = items[:left_today]

    if not args.confirm:
        print(f"План: {len(items)} сообщений, паузы {PACE['min_gap_sec']}–{PACE['max_gap_sec']} с.")
        for i in items:
            print(f"  → {i['to']}: {i['text'][:70]}…")
        print("\nЗапуск: python concierge.py drain --confirm")
        return

    async def inner(tg):
        from telethon.errors import FloodWaitError, PeerFloodError, UserPrivacyRestrictedError

        sent = 0
        for n, item in enumerate(items, 1):
            key = item["to"]
            r = record(state, key)
            try:
                await tg.send_message(key, item["text"])
            except PeerFloodError:
                log("✗ Telegram: слишком много сообщений незнакомым. ОСТАНОВКА.")
                log("  Аккаунт под ограничением. Сегодня больше не пишем ничего.")
                break
            except UserPrivacyRestrictedError:
                log(f"– {key}: закрыл личку, пропускаю")
                r["status"] = "unreachable"
                continue
            except FloodWaitError as e:
                log(f"✗ Telegram просит подождать {e.seconds} с. ОСТАНОВКА.")
                break
            except Exception as e:
                log(f"✗ {key}: {type(e).__name__} — пропускаю")
                continue

            r["status"] = "sent"
            r["sent_at"] = time.time()
            r["sent_at_h"] = now()
            r["sent_day"] = datetime.now(timezone.utc).date().isoformat()
            sent += 1
            save_state(state)
            log(f"✓ {n}/{len(items)} {key}")

            rest = [i for i in queue_items() if i["to"] != key]
            queue_write(rest)

            if n < len(items):
                gap = random.randint(PACE["min_gap_sec"], PACE["max_gap_sec"])
                if n % PACE["long_break_every"] == 0:
                    gap = PACE["long_break_sec"]
                    log(f"  длинная пауза {gap} с")
                else:
                    log(f"  пауза {gap} с")
                await asyncio.sleep(gap)
        return sent

    sent = await with_client(inner)
    log(f"готово: отправлено {sent}")


async def cmd_inbox(_args) -> None:
    leads, state = read_leads(), load_state()
    written = [k for k in leads if record(state, k)["status"] in {"sent", "replied", "stopped"}]
    if not written:
        print("никому ещё не писали")
        return

    async def inner(tg):
        found = []
        for key in written:
            r = record(state, key)
            msgs = await tg.get_messages(key, limit=12)
            fresh = [m for m in reversed(msgs) if not m.out and m.text
                     and m.id > r.get("last_seen_id", 0)]
            if not fresh:
                continue
            r["last_seen_id"] = max(m.id for m in fresh)
            r["replies"] = r.get("replies", 0) + len(fresh)
            if r["status"] == "sent":
                r["status"] = "replied"
            joined = " / ".join(m.text.strip() for m in fresh)
            if any(w in joined.lower() for w in STOP_WORDS):
                r["status"] = "stopped"
                found.append((key, joined, True))
            else:
                found.append((key, joined, False))
        save_state(state)
        return found

    found = await with_client(inner)
    if not found:
        print("новых ответов нет")
        return
    for key, text, stopped in found:
        lead = leads[key]
        mark = "  ⛔ ПРОСИТ НЕ ПИСАТЬ — вычеркнут" if stopped else ""
        print(f"\n{key} · {lead['business']}{mark}")
        print(f"  {text}")


async def cmd_reply(args) -> None:
    leads, state = read_leads(), load_state()
    key = norm(args.to)
    if key not in leads:
        die(f"{key} нет в leads.csv")
    r = record(state, key)
    if r["status"] == "stopped":
        die(f"{key} просил не писать — отвечать нельзя")
    if r["status"] not in {"sent", "replied"}:
        die(f"{key} ещё не писали — сначала queue и drain")

    async def inner(tg):
        await tg.send_message(key, args.text.strip())

    await with_client(inner)
    log(f"→ {key}: {args.text.strip()[:60]}")


async def cmd_stop(args) -> None:
    state = load_state()
    key = norm(args.to)
    record(state, key)["status"] = "stopped"
    save_state(state)
    queue_write([i for i in queue_items() if i["to"] != key])
    print(f"✓ {key} вычеркнут, писать ему больше не будем")


COMMANDS = {
    "login": cmd_login, "check": cmd_check, "leads": cmd_leads, "queue": cmd_queue,
    "drain": cmd_drain, "inbox": cmd_inbox, "reply": cmd_reply, "stop": cmd_stop,
}


def main() -> None:
    ap = argparse.ArgumentParser(description="Консьерж: пишет первым тем, кого ты выбрал")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in COMMANDS:
        p = sub.add_parser(name)
        if name in {"queue", "reply", "stop"}:
            p.add_argument("--to", required=True)
        if name in {"queue", "reply"}:
            p.add_argument("--text", required=True)
        if name == "drain":
            p.add_argument("--confirm", action="store_true")
    args = ap.parse_args()
    asyncio.run(COMMANDS[args.cmd](args))


if __name__ == "__main__":
    main()
