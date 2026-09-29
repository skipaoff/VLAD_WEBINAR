# -*- coding: utf-8 -*-
"""Собирает страницу-артефакт из состояния прогона.

Состояние лежит в build/state.json, страница пишется в build/Сборка.html.
После каждого шага скилл обновляет состояние, зовёт этот скрипт и публикует
файл через инструмент Artifact по тому же пути: адрес остаётся прежним, а
страница дорастает.

Запуск:  python .claude/skills/stoma-demo/artifact.py

Changes when: меняется вид страницы прогона.

Anti-goal:
1. Ничего не выдумывает. Что положили в состояние, то и покажет.
2. Не решает, какой шаг пройден: статусы ставит скилл.
"""
import base64
import io
import json
import os
import sys
from string import Template

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
STATE = os.path.join(ROOT, "build", "state.json")
OUT = os.path.join(ROOT, "build", "Сборка.html")

STATE_LABEL = {"done": "готово", "run": "сейчас", "warn": "нужно решить", "wait": "впереди"}
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def esc(v):
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def data_uri(path):
    """Картинку в артефакт можно положить только целиком: внешние адреса он не пустит."""
    full = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(full):
        return None
    mime = MIME.get(os.path.splitext(full)[1].lower())
    if not mime:
        return None
    raw = io.open(full, "rb").read()
    return "data:" + mime + ";base64," + base64.b64encode(raw).decode("ascii")


def chips(items):
    if not items:
        return ""
    return ('<ul class="chips">'
            + "".join('<li>' + esc(c) + '</li>' for c in items)
            + '</ul>')


def facts(items):
    if not items:
        return ""
    rows = []
    for f in items:
        st = f.get("s", "done")
        rows.append('<li data-s="' + esc(st) + '"><span class="bul"></span>'
                    + esc(f.get("t", "")) + "</li>")
    return '<ul class="facts">' + "".join(rows) + "</ul>"


def nums(items):
    if not items:
        return ""
    cells = []
    for n in items:
        cells.append('<div><b>' + esc(n.get("v", "")) + "</b><span>"
                     + esc(n.get("t", "")) + "</span></div>")
    return '<div class="nums">' + "".join(cells) + "</div>"


def shots(items):
    out = []
    for sh in items or []:
        uri = data_uri(sh.get("path", ""))
        if not uri:
            continue
        out.append('<figure><img src="' + uri + '" alt="' + esc(sh.get("caption", "")) + '">'
                   + ('<figcaption>' + esc(sh["caption"]) + "</figcaption>"
                      if sh.get("caption") else "") + "</figure>")
    return '<div class="shots">' + "".join(out) + "</div>" if out else ""


CSS = """
:root{
  --ground:#f6f8f7; --surface:#ffffff; --sunk:#eef2f1;
  --ink:#13201d; --muted:#5d6c69; --line:#dde5e2;
  --accent:#0e7c6b; --accent-soft:#e2f1ee;
  --done:#2f7a52; --run:#b06a00; --warn:#a3401f;
  --shadow:0 1px 2px rgba(19,32,29,.05), 0 8px 24px -16px rgba(19,32,29,.22);
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#0d1413; --surface:#151d1b; --sunk:#1b2523;
    --ink:#e7efec; --muted:#93a4a0; --line:#26332f;
    --accent:#57d6bb; --accent-soft:#12302b;
    --done:#5cc78d; --run:#e2a955; --warn:#e8886a;
    --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 30px -18px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --ground:#0d1413; --surface:#151d1b; --sunk:#1b2523;
  --ink:#e7efec; --muted:#93a4a0; --line:#26332f;
  --accent:#57d6bb; --accent-soft:#12302b;
  --done:#5cc78d; --run:#e2a955; --warn:#e8886a;
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 10px 30px -18px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);
     font:16px/1.6 'Source Sans 3',system-ui,-apple-system,'Segoe UI',sans-serif;
     -webkit-font-smoothing:antialiased}
.wrap{max-width:860px;margin:0 auto;padding:40px 22px 80px}
h1,h2,h3{font-family:'Bricolage Grotesque','Source Sans 3',system-ui,sans-serif;
         text-wrap:balance;margin:0;letter-spacing:-.02em}
.lab{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.12em;
     text-transform:uppercase;color:var(--muted)}

/* сводка */
.head{display:flex;flex-wrap:wrap;gap:18px 26px;align-items:flex-end;
      padding-bottom:22px;border-bottom:1px solid var(--line);margin-bottom:30px}
.head .who{flex:1 1 260px;min-width:0}
.head h1{font-size:clamp(26px,4.4vw,38px);line-height:1.08;margin-top:8px}
.head p{color:var(--muted);margin:8px 0 0;font-size:15px}
.meter{flex:0 0 auto;text-align:right}
.meter b{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:30px;font-weight:600;
         display:block;line-height:1;font-variant-numeric:tabular-nums}
.meter span{font-size:13px;color:var(--muted)}
.rail{margin-top:10px;width:170px;height:5px;border-radius:3px;background:var(--sunk);overflow:hidden}
.rail i{display:block;height:100%;background:var(--accent);border-radius:3px}

/* шаги */
.steps{display:flex;flex-direction:column;gap:14px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;
      padding:20px 22px;box-shadow:var(--shadow)}
.ahead{border:1px dashed var(--line);border-radius:14px;padding:16px 22px}
.ahead .lab{display:block;margin-bottom:10px}
.ahead ol{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:8px 22px}
.ahead li{color:var(--muted);font-size:15px;display:flex;gap:8px;align-items:baseline}
.card[data-s="run"]{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft),var(--shadow)}
.top{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.no{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:13px;color:var(--muted);
    font-variant-numeric:tabular-nums}
.card h2{font-size:20px;flex:1 1 auto;min-width:0}
.pill{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.06em;
      text-transform:uppercase;padding:4px 10px;border-radius:999px;border:1px solid var(--line);
      color:var(--muted);white-space:nowrap}
.card[data-s="done"] .pill{color:var(--done);border-color:color-mix(in srgb,var(--done) 40%,transparent)}
.card[data-s="run"] .pill{color:var(--run);border-color:color-mix(in srgb,var(--run) 45%,transparent)}
.card[data-s="warn"] .pill{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,transparent)}
.note{margin:10px 0 0;color:var(--muted)}
.card p.note{max-width:62ch}

.chips{list-style:none;display:flex;flex-wrap:wrap;gap:7px;margin:16px 0 0;padding:0}
.chips li{background:var(--sunk);border-radius:999px;padding:6px 12px;font-size:14px}
.facts{list-style:none;margin:16px 0 0;padding:0;display:flex;flex-direction:column;gap:8px}
.facts li{display:flex;gap:10px;align-items:flex-start;font-size:15px}
.facts .bul{width:9px;height:9px;border-radius:50%;margin-top:7px;flex:0 0 9px;
            background:var(--done)}
.facts li[data-s="run"] .bul{background:var(--run)}
.facts li[data-s="warn"] .bul{background:var(--warn)}
.facts li[data-s="wait"] .bul{background:var(--line)}
.facts li[data-s="wait"]{color:var(--muted)}
.nums{display:flex;flex-wrap:wrap;gap:26px;margin-top:20px;padding-top:16px;border-top:1px solid var(--line)}
.nums b{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:24px;font-weight:600;
        display:block;line-height:1.1;font-variant-numeric:tabular-nums}
.nums span{font-size:13px;color:var(--muted)}

.shots{display:grid;gap:12px;margin-top:20px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.shots figure{margin:0}
.shots img{width:100%;display:block;border-radius:10px;border:1px solid var(--line)}
.shots figcaption{font-size:13px;color:var(--muted);margin-top:7px}

/* вопрос */
.ask{margin-top:26px;background:var(--accent-soft);border:1px solid color-mix(in srgb,var(--accent) 35%,transparent);
     border-radius:14px;padding:20px 22px}
.ask h2{font-size:18px;margin-bottom:6px}
.ask p{margin:0;color:var(--ink)}
.ask .lab{display:block;margin-bottom:10px}

.foot{margin-top:34px;padding-top:18px;border-top:1px solid var(--line);
      display:flex;flex-wrap:wrap;gap:8px 20px;color:var(--muted);font-size:14px}
.foot a{color:var(--accent)}
@media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
"""


PAGE = Template("""<title>$title</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Sans+3:wght@400;600&display=swap">
<style>$css</style>
<div class="wrap">
  <header class="head">
    <div class="who">
      <span class="lab">$kicker</span>
      <h1>$clinic</h1>
      <p>$subtitle</p>
    </div>
    <div class="meter">
      <b>$donecount/$total</b>
      <span>шагов пройдено</span>
      <div class="rail"><i style="width:$pct%"></i></div>
    </div>
  </header>

  <div class="steps">
$steps
  </div>
$ask
  <footer class="foot">$foot</footer>
</div>
""")


def build(state):
    steps_html = []
    ahead = []
    for i, s in enumerate(state.get("steps", []), 1):
        st = s.get("status", "wait")
        if st == "wait":
            ahead.append('<li><span class="no">' + ("%02d" % i) + "</span>"
                         + esc(s.get("title", "")) + "</li>")
            continue
        body = ""
        if True:
            if s.get("note"):
                body += '<p class="note">' + esc(s["note"]) + "</p>"
            body += chips(s.get("chips"))
            body += facts(s.get("items"))
            body += nums(s.get("nums"))
            body += shots(s.get("shots"))
        steps_html.append(
            '<section class="card" data-s="' + esc(st) + '">'
            '<div class="top"><span class="no">' + ("%02d" % i) + "</span>"
            "<h2>" + esc(s.get("title", "")) + "</h2>"
            '<span class="pill">' + STATE_LABEL.get(st, st) + "</span></div>"
            + body + "</section>")

    if ahead:
        steps_html.append('<section class="ahead"><span class="lab">впереди</span>'
                          "<ol>" + "".join(ahead) + "</ol></section>")

    ask = ""
    q = state.get("question")
    if q:
        ask = ('<section class="ask"><span class="lab">нужен ваш ответ</span>'
               '<h2>' + esc(q.get("title", "Идём дальше?")) + "</h2>"
               '<p>' + esc(q.get("text", "")) + "</p></section>")

    foot = []
    if state.get("site"):
        foot.append('<span>Сайт: <a href="' + esc(state["site"]) + '">'
                    + esc(state["site"]) + "</a></span>")
    if state.get("folder"):
        foot.append("<span>Папка: " + esc(state["folder"]) + "</span>")
    if state.get("updated"):
        foot.append("<span>Обновлено: " + esc(state["updated"]) + "</span>")

    total = len(state.get("steps", []))
    done = sum(1 for s in state.get("steps", []) if s.get("status") == "done")
    return PAGE.substitute(
        title=esc(state.get("title") or ("Сборка сайта: " + state.get("clinic", ""))),
        css=CSS,
        kicker=esc(state.get("kicker", "сборка сайта клиники")),
        clinic=esc(state.get("clinic", "")),
        subtitle=esc(state.get("subtitle", "")),
        donecount=done, total=total,
        pct=int(round(done * 100.0 / total)) if total else 0,
        steps="\n".join(steps_html),
        ask=ask,
        foot="".join(foot) or "<span>Прогон идёт</span>")


def main():
    if not os.path.exists(STATE):
        sys.exit("нет файла состояния: " + STATE)
    state = json.load(io.open(STATE, encoding="utf-8"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(build(state))
    size = os.path.getsize(OUT) / 1048576.0
    print("страница собрана: %s (%.2f МБ)" % (OUT, size))
    if size > 15:
        print("ВНИМАНИЕ: артефакт не принимает файлы больше 16 МБ, убери часть скриншотов")


if __name__ == "__main__":
    main()
