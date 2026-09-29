#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Подхватывает картинки рекламы из папки kreativy и вписывает их в экран.

    python3 kreativy.py

Картинки: kreativy/1.jpg … 5.jpg (или .png). Скриншот кабинета: kreativy/kabinet.png.
Ссылки на картинки: по одной в строке в kreativy/ssylki.txt, в том же порядке.
Чего нет — останется рамкой с подписью, экран не ломается.
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "shagi", "04-reklama.json")
DIR = os.path.join(HERE, "kreativy")


def found(n):
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        rel = "kreativy/%d%s" % (n, ext)
        if os.path.exists(os.path.join(HERE, rel)):
            return rel
    return None


def main():
    d = json.loads(io.open(STATE, encoding="utf-8").read())
    step = next(s for s in d["steps"] if s.get("grid"))
    urls = []
    path = os.path.join(DIR, "ssylki.txt")
    if os.path.exists(path):
        urls = [l.strip() for l in io.open(path, encoding="utf-8") if l.strip()]

    live = []
    for i, g in enumerate(step["grid"], 1):
        rel = found(i)
        g["file"] = rel or ("kreativy/%d.jpg" % i)
        if rel:
            live.append((i, g.get("text", "картинка %d" % i),
                         urls[i - 1] if len(urls) >= i else None))
    print("картинок на месте: %d из %d" % (len(live), len(step["grid"])))

    base = [l for l in d["fin"]["links"] if not l.get("_krea")]
    for i, text, url in live:
        if url:
            base.append({"text": "Картинка %d — %s" % (i, text), "url": url, "_krea": True})
    d["fin"]["links"] = base

    shot = os.path.join(DIR, "kabinet.png")
    d["fin"]["shot"] = "kreativy/kabinet.png"
    print("скриншот кабинета:", "на месте" if os.path.exists(shot) else "ещё нет")

    io.open(STATE, "w", encoding="utf-8").write(
        json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    print("вписал в", STATE)


if __name__ == "__main__":
    main()
