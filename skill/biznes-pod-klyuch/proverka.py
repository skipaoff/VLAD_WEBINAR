#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка перед эфиром: всё ли на месте.

    python3 proverka.py

Собирает все четыре экрана, считает портреты, дёргает ссылки результатов
и смотрит, положены ли картинки рекламы. Печатает короткий отчёт.
Ничего не меняет и никуда не ходит, кроме проверки ссылок.
"""
import io
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

EKRANY = ["01-sajt", "02-prodavec", "03-video", "04-reklama"]

ok = True


def stroka(good, text):
    global ok
    if not good:
        ok = False
    print("  %s %s" % ("✓" if good else "×", text))


def zhivaya(url):
    """Через curl, а не питоном: он берёт доверенные корни у самой системы."""
    try:
        out = subprocess.run(["curl", "-sSL", "-o", os.devnull, "-w", "%{http_code}",
                              "--max-time", "15", url],
                             capture_output=True, text=True, timeout=25)
        return int((out.stdout or "0").strip() or 0)
    except Exception:
        return 0


def main():
    import ekran

    print("\nЭкраны")
    ssylki = []
    for name in EKRANY:
        try:
            out = ekran.build(name)
            d = json.loads(io.open(os.path.join(HERE, "shagi", name + ".json"),
                                   encoding="utf-8").read())
            sek = sum(int(s.get("dur", 20)) for s in d["steps"])
            bez_vida = [s["title"] for s in d["steps"] if not s.get("vid")]
            stroka(not bez_vida and sek <= 180,
                   "%-12s %d шагов, идёт %d:%02d%s"
                   % (name, len(d["steps"]), sek // 60, sek % 60,
                      "" if not bez_vida else ", без картинки работы: " + ", ".join(bez_vida)))
            for l in (d.get("fin") or {}).get("links", []):
                if l.get("url", "").startswith("http"):
                    ssylki.append((name, l["text"], l["url"]))
        except Exception as e:
            stroka(False, "%-12s не собирается: %s" % (name, e))

    print("\nПортреты")
    lica = [f for f in os.listdir(os.path.join(HERE, "lica")) if f.endswith(".png")]
    stroka(len(lica) >= 6, "%d штук в lica/" % len(lica))

    print("\nКартинки рекламы")
    kdir = os.path.join(HERE, "kreativy")
    est = [f for f in os.listdir(kdir) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    kab = "kabinet.png" in est
    kart = [f for f in est if f != "kabinet.png"]
    stroka(len(kart) > 0, "картинок положено: %d из 5" % len(kart))
    stroka(kab, "скриншот кабинета: %s" % ("на месте" if kab else "ещё нет"))

    print("\nСсылки результатов")
    for name, text, url in ssylki:
        code = zhivaya(url)
        stroka(code == 200, "%-12s %s — %s" % (name, text, code or "не отвечает"))

    print("\n%s\n" % ("Всё на месте, можно в эфир." if ok else
                      "Есть незакрытые пункты — смотри строки с ×."))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
