# -*- coding: utf-8 -*-
"""Собирает экран работы агента из состояния — один HTML-файл под артефакт.

Состояние лежит в shagi/<шаг>.json, готовая страница — в build/Экран.html.
Скилл после каждого куска работы двигает состояние, зовёт этот скрипт и
публикует файл через инструмент Artifact по тому же пути: адрес не меняется,
страница дорастает прямо на глазах.

Запуск:  python3 ekran.py 01-sajt

Чего он не делает:
1. Ничего не придумывает: что в состоянии, то и на экране.
2. Не решает, какой шаг пройден: статусы ставит скилл через shag.py.
3. Не тянет ничего из сети: картинки уезжают в страницу целиком.
"""
import base64
import io
import json
import os
import sys
from string import Template

HERE = os.path.dirname(os.path.abspath(__file__))
LICA = os.path.join(HERE, "lica")
BUILD = os.path.join(HERE, "build")

IMYA = {"01-sajt": "Сайт.html", "02-prodavec": "Продавец.html",
        "03-video": "Ролик.html", "04-reklama": "Реклама.html"}

ST = {"done": "готово", "run": "в работе", "wait": "ждёт"}


def esc(v):
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def lico(name):
    """Портрет уезжает в страницу целиком: внешних адресов артефакт не пустит."""
    path = os.path.join(LICA, str(name))
    if not name or not os.path.exists(path):
        return ""
    return "data:image/png;base64," + base64.b64encode(io.open(path, "rb").read()).decode("ascii")


def kartinka(src):
    """Картинка уезжает в страницу целиком: внешних адресов артефакт не пустит."""
    if not src:
        return ""
    if src.startswith("data:") or src.startswith("http"):
        return src
    path = src if os.path.isabs(src) else os.path.join(HERE, src)
    if not os.path.exists(path):
        return ""
    ext = os.path.splitext(path)[1].lower()
    mime = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
    return ("data:%s;base64," % mime) + base64.b64encode(io.open(path, "rb").read()).decode("ascii")


def grid(arr):
    """Плитка с картинками: чего ещё нет — место под неё, с подписью."""
    if not arr:
        return ""
    out = []
    for n, g in enumerate(arr, 1):
        src = kartinka(g.get("file"))
        inner = ('<img src="%s" alt="">' % src) if src else (
            '<span class="hole">место под картинку %d</span>' % n)
        out.append('<figure class="tile%s">%s<figcaption>%s</figcaption></figure>'
                   % ("" if src else " empty", inner, esc(g.get("text", ""))))
    return '<div class="grid">' + "".join(out) + "</div>"


def chips(arr):
    if not arr:
        return ""
    return ('<div class="chips">' +
            "".join('<span class="chip">' + esc(c) + "</span>" for c in arr) +
            "</div>")


def items(arr):
    if not arr:
        return ""
    return ('<ul class="items">' +
            "".join("<li>" + esc(i) + "</li>" for i in arr) +
            "</ul>")


def log(arr, live):
    """Строчки работы. На идущем шаге они проявляются по одной, на готовом стоят все."""
    if not arr:
        return ""
    out = []
    for n, line in enumerate(arr):
        at = (n + 1) / float(len(arr) + 1)
        out.append('<li%s data-at="%.3f">%s</li>' % (' class="hid"' if live else "", at, esc(line)))
    return '<ul class="log%s">%s</ul>' % (" live" if live else "", "".join(out))


def card_now(s, n, total):
    """Развёрнутый блок: шаг, который идёт сейчас, либо последний сделанный."""
    st = s.get("status", "wait")
    live = st == "run"
    head = ('<div class="nowtop"><span class="no">шаг %02d из %02d</span>'
            '<span class="pill" data-s="%s">%s</span></div>' % (n, total, esc(st), ST.get(st, st)))
    body = ["<h2>" + esc(s.get("title", "")) + "</h2>"]
    if s.get("sub"):
        body.append('<p class="sub">' + esc(s["sub"]) + "</p>")
    if st == "done":
        if s.get("say"):
            body.append('<p class="say">' + esc(s["say"]) + "</p>")
        body.append(chips(s.get("chips")))
        body.append(items(s.get("items")))
    body.append(log(s.get("log"), live))
    if live:
        body.append('<div class="work"><i></i><span>работает</span></div>')
    return ('<section class="now" id="now" data-dur="%d">%s<div class="nowbody">%s</div></section>'
            % (int(s.get("dur", 20)), head, "".join(body)))


def mate_cards(team, steps):
    out = []
    for k, m in enumerate(team):
        face = lico(m.get("img"))
        pic = ('<img class="face" src="%s" alt="">' % face) if face else '<span class="face"></span>'
        out.append('<button class="mate" type="button" data-k="%d" data-s="%s" title="%s">'
                   '%s<b>%s</b><span class="role">%s</span>'
                   '<span class="st">%s</span></button>'
                   % (k, esc(m.get("status", "wait")), esc(m.get("name", "")), pic,
                      esc(m.get("name", "")), esc(m.get("role", "")),
                      ST.get(m.get("status", "wait"), "")))
    return "".join(out)


def mate_sheets(team, steps):
    """Что показывается на той же полке, когда нажали на человека."""
    out = []
    for k, m in enumerate(team):
        mine = [(i + 1, s) for i, s in enumerate(steps) if s.get("who") == k]
        body = ['<header class="shhead">']
        face = lico(m.get("img"))
        if face:
            body.append('<img class="face big" src="%s" alt="">' % face)
        body.append('<div><b>%s</b><span>%s</span></div>'
                    '<button class="back" type="button">← к работе</button></header>'
                    % (esc(m.get("name", "")), esc(m.get("role", ""))))
        if not mine:
            body.append('<p class="empty">Ещё не брался за работу.</p>')
        for i, s in mine:
            st = s.get("status", "wait")
            body.append('<section class="shstep" data-s="%s">'
                        '<div class="nowtop"><span class="no">шаг %02d</span>'
                        '<span class="pill" data-s="%s">%s</span></div>'
                        '<h3>%s</h3>' % (esc(st), i, esc(st), ST.get(st, st), esc(s.get("title", ""))))
            if st == "done":
                if s.get("say"):
                    body.append('<p class="say">' + esc(s["say"]) + "</p>")
                body.append(chips(s.get("chips")))
                body.append(grid(s.get("grid")))
                body.append(items(s.get("items")))
            elif st == "run":
                body.append('<p class="empty">Работает прямо сейчас.</p>')
            else:
                body.append('<p class="empty">Ждёт своей очереди.</p>')
            body.append("</section>")
        out.append('<section class="mv" id="mv-%d" hidden>%s</section>' % (k, "".join(body)))
    return "".join(out)


def polka(steps):
    """Картинки, которые уже сделаны, остаются на экране: их и показываем."""
    out = []
    for s in steps:
        if s.get("status") == "done" and s.get("grid"):
            out.append('<section class="polka"><span class="lab">%s</span>%s</section>'
                       % (esc(s.get("gridlab", "что нарисовали")), grid(s["grid"])))
    return "".join(out)


def itogi(d, steps):
    """Общий счёт снизу: цифра появляется, когда её шаг сделан."""
    rows = d.get("itogi") or []
    if not rows:
        return ""
    done = sum(1 for s in steps if s.get("status") == "done")
    cells = []
    for r in rows:
        got = done >= int(r.get("after", 1))
        cells.append('<div class="it%s"><b>%s</b><span>%s</span></div>'
                     % ("" if got else " wait", esc(r.get("n", "")) if got else "—",
                        esc(r.get("t", ""))))
    return ('<section class="itogi"><div class="itoptop"><span class="lab">что уже сделано</span>'
            '<span class="lab">%d из %d шагов</span></div><div class="itrow">%s</div></section>'
            % (done, len(steps), "".join(cells)))


def plan(steps):
    out = []
    for i, s in enumerate(steps, 1):
        st = s.get("status", "wait")
        out.append('<li data-s="%s"><span class="no">%02d</span><span>%s</span>'
                   '<em>%s</em></li>' % (esc(st), i, esc(s.get("title", "")), ST.get(st, st)))
    return '<ol class="plan">' + "".join(out) + "</ol>"


def ask_block(a):
    """Вопрос человеку прямо на экране: что спросили и что ответили."""
    if not a:
        return ""
    rows = []
    for q in a.get("rows", []):
        got = q.get("answer")
        rows.append('<div class="qrow%s"><span class="q">%s</span>'
                    '<span class="a">%s</span></div>'
                    % ("" if got else " wait", esc(q.get("q", "")),
                       esc(got) if got else "ждём ответ"))
    return ('<section class="ask"><span class="lab">%s</span>%s</section>'
            % (esc(a.get("title", "уточняю у тебя")), "".join(rows)))


def fin_block(f):
    if not f:
        return ""
    links = "".join('<a class="go%s" href="%s" target="_blank" rel="noopener">%s</a>'
                    % (" main" if n == 0 else "", esc(l.get("url", "#")), esc(l.get("text", "")))
                    for n, l in enumerate(f.get("links", [])))
    shot = ""
    if f.get("shot"):
        src = kartinka(f["shot"])
        if src:
            shot = '<img class="shot" src="%s" alt="%s">' % (esc(src), esc(f.get("shotalt", "")))
        else:
            shot = '<div class="shot hole">%s</div>' % esc(f.get("shotalt", "место под скриншот"))
    return ('<section class="fin"><span class="lab">готово</span><h2>%s</h2>'
            '<p>%s</p>%s<div class="gos">%s</div></section>'
            % (esc(f.get("title", "Готово")), esc(f.get("text", "")), shot, links))


def build(name):
    path = os.path.join(HERE, "shagi", name + ".json")
    d = json.loads(io.open(path, encoding="utf-8").read())
    steps = d.get("steps", [])
    team = d.get("team", [])
    done = sum(1 for s in steps if s.get("status") == "done")
    run = next((i for i, s in enumerate(steps) if s.get("status") == "run"), None)
    live = run is not None
    shown = run if live else (done - 1 if done else 0)
    now = card_now(steps[shown], shown + 1, len(steps)) if steps else ""

    page = Template(shablon()).substitute(
        title=esc(d.get("title", "Работа агента")),
        who=esc(d.get("who", "")),
        source=esc(d.get("source", "")),
        state=esc(d.get("state", "в работе" if live else "готово")),
        live="1" if live else "0",
        elapsed=int(d.get("elapsed", 0)),
        done=done,
        total=len(steps),
        pct=int(round(100.0 * done / max(1, len(steps)))),
        mates=mate_cards(team, steps),
        sheets=mate_sheets(team, steps),
        ask=ask_block(d.get("ask")),
        now=now,
        polka=polka(steps),
        itogi=itogi(d, steps),
        plan=plan(steps),
        fin=fin_block(d.get("fin")) if (steps and not live and done == len(steps)) else "",
    )
    out = os.path.join(BUILD, IMYA.get(name, name + ".html"))
    if not os.path.isdir(BUILD):
        os.makedirs(BUILD)
    io.open(out, "w", encoding="utf-8").write(page)
    print("%s → %s (%d из %d, %s)" % (name, out, done, len(steps),
                                      "идёт" if live else "стоп"))
    return out


def shablon():
    return io.open(os.path.join(HERE, "shablon.html"), encoding="utf-8").read()


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "01-sajt")
