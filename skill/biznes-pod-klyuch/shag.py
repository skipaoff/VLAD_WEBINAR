#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Двигает работу на один шаг и пересобирает экран.

    python3 shag.py 01-sajt 1          — шаг 1 в работу
    python3 shag.py 01-sajt 2          — шаг 1 готов, шаг 2 в работу
    python3 shag.py 01-sajt finish     — все шаги готовы, показать результат
    python3 shag.py 01-sajt otvet "и там и там" "100 долларов"
                                       — вписать ответы человека в вопросы на экране
    python3 shag.py 01-sajt reset      — вернуть на старт

После каждой команды файл build/Экран.html готов к публикации: публикуй его
через инструмент Artifact по тому же пути — адрес не меняется, страница дорастает.
"""
import io
import json
import os
import sys

import ekran

HERE = os.path.dirname(os.path.abspath(__file__))


def path(name):
    return os.path.join(HERE, "shagi", name + ".json")


def load(name):
    return json.loads(io.open(path(name), encoding="utf-8").read())


def save(name, d):
    io.open(path(name), "w", encoding="utf-8").write(
        json.dumps(d, ensure_ascii=False, indent=2) + "\n")


def spent(d, upto):
    """Сколько времени уже заняло: складываем длительности сделанных шагов."""
    return sum(int(s.get("dur", 20)) for s in d["steps"][:upto])


def run(name, n):
    d = load(name)
    steps = d["steps"]
    if n < 1 or n > len(steps):
        sys.exit("шага %d нет, всего %d" % (n, len(steps)))
    for i, s in enumerate(steps, 1):
        s["status"] = "done" if i < n else ("run" if i == n else "wait")
    for k, m in enumerate(d["team"]):
        mine = [s for s in steps if s.get("who") == k]
        if any(s["status"] == "run" for s in mine):
            m["status"] = "run"
        elif mine and all(s["status"] == "done" for s in mine):
            m["status"] = "done"
        else:
            m["status"] = "wait"
    d["state"] = "в работе"
    d["elapsed"] = spent(d, n - 1)
    d.pop("_fin_on", None)
    save(name, d)


def finish(name):
    d = load(name)
    for s in d["steps"]:
        s["status"] = "done"
    for m in d["team"]:
        m["status"] = "done"
    d["state"] = "готово"
    d["elapsed"] = spent(d, len(d["steps"]))
    save(name, d)


def reset(name):
    d = load(name)
    for s in d["steps"]:
        s["status"] = "wait"
    for m in d["team"]:
        m["status"] = "wait"
    d["state"] = "готов к запуску"
    d["elapsed"] = 0
    if d.get("ask"):
        for q in d["ask"].get("rows", []):
            q.pop("answer", None)
    save(name, d)


def otvet(name, answers):
    d = load(name)
    rows = (d.get("ask") or {}).get("rows", [])
    if not rows:
        sys.exit("на этом экране вопросов нет")
    for q, a in zip(rows, answers):
        q["answer"] = a
    save(name, d)


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    name, cmd = args[0], args[1]
    if not os.path.exists(path(name)):
        sys.exit("нет такого экрана: %s" % name)
    if cmd == "finish":
        finish(name)
    elif cmd == "reset":
        reset(name)
    elif cmd == "otvet":
        otvet(name, args[2:])
    else:
        run(name, int(cmd))
    out = ekran.build(name)
    print("публикуй этот файл: %s" % out)


if __name__ == "__main__":
    main()
