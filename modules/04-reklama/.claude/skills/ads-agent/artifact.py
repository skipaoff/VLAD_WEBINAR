# -*- coding: utf-8 -*-
"""Собирает экран прогона агента из состояния.

Состояние в build/state.json, страница в build/Экран.html. Скилл после каждого
шага дописывает состояние, зовёт этот скрипт и публикует файл через инструмент
Artifact по тому же пути: адрес не меняется, страница дорастает.

Запуск:  python .claude/skills/site-agent/artifact.py

Changes when: меняется вид экрана прогона.

Anti-goal:
1. Ничего не выдумывает: что положили в состояние, то и покажет.
2. Не решает, какой шаг пройден: статусы ставит скилл.
3. Светлой темы нет намеренно: экран одинаковый у всех зрителей эфира.
"""
import base64
import io
import json
import os
import sys
from string import Template

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
STATE = os.path.join(ROOT, "build", "state.json")
OUT = os.path.join(ROOT, "build", "Экран.html")

MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
LABEL = {"done": "готово", "run": "в работе", "warn": "нужно решить", "wait": "ждёт"}


def esc(v):
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def data_uri(path):
    """Картинка уезжает в артефакт целиком: внешние адреса он не пустит."""
    full = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(full):
        return None
    mime = MIME.get(os.path.splitext(full)[1].lower())
    if not mime:
        return None
    return "data:" + mime + ";base64," + base64.b64encode(io.open(full, "rb").read()).decode("ascii")


def initials(name):
    parts = [p for p in str(name).split() if p]
    return (parts[0][:2] if parts else "??").upper()


def team_html(team):
    """Команда агента. Каждый специалист это персонаж, а не буквы в квадрате."""
    if not team:
        return ""
    cells = []
    for m in team:
        st = m.get("status", "wait")
        uri = data_uri(m.get("img", "")) if m.get("img") else None
        face = ('<img class="face" src="' + uri + '" alt="' + esc(m.get("name", "")) + '">'
                if uri else '<span class="ava">' + esc(initials(m.get("name", ""))) + '</span>')
        cells.append(
            '<li class="mate" data-s="' + esc(st) + '">'
            '<span class="pod">' + face + '<i class="halo"></i><i class="tick"></i></span>'
            '<span class="mname">' + esc(m.get("name", "")) + '</span>'
            '<span class="mskill">' + esc(m.get("skill", "")) + '</span>'
            '<span class="mstate">' + esc(m.get("doing") or LABEL.get(st, st)) + '</span>'
            '</li>')
    return ('<section class="team"><div class="teamhead">'
            '<span class="lab">субагенты</span>'
            '<span class="lab dim">' + str(len(team)) + ' в работе над запуском</span></div>'
            '<ul class="mates">' + "".join(cells) + '</ul></section>')


def chips(items):
    if not items:
        return ""
    return '<ul class="chips">' + "".join('<li>' + esc(c) + '</li>' for c in items) + '</ul>'


def facts(items):
    if not items:
        return ""
    rows = ['<li data-s="' + esc(f.get("s", "done")) + '"><span class="bul"></span>'
            + esc(f.get("t", "")) + '</li>' for f in items]
    return '<ul class="facts">' + "".join(rows) + '</ul>'


def nums(items):
    if not items:
        return ""
    cells = ['<div><b>' + esc(n.get("v", "")) + '</b><span>' + esc(n.get("t", "")) + '</span></div>'
             for n in items]
    return '<div class="nums">' + "".join(cells) + '</div>'


def doc_html(docs):
    """Документы, которые сделали скиллы. Виден объём, раскрываются целиком."""
    if not docs:
        return ""
    if isinstance(docs, dict):
        docs = [docs]
    out = []
    for doc in docs:
        body = ""
        path = doc.get("path")
        if path:
            full = path if os.path.isabs(path) else os.path.join(ROOT, path)
            if os.path.exists(full):
                body = io.open(full, encoding="utf-8").read()
        if not body:
            body = doc.get("text", "")
        if not body:
            continue
        words = len(body.split())
        meta = doc.get("meta") or (format(words, ",d").replace(",", " ") + " слов")
        out.append('<details class="doc"><summary><span class="dicon"></span>'
                   '<span class="dname">' + esc(doc.get("name", "документ")) + '</span>'
                   '<span class="dmeta">' + esc(meta) + '</span>'
                   '<span class="dopen">открыть</span></summary>'
                   '<pre>' + esc(body) + '</pre></details>')
    return "".join(out)


def media_html(step):
    out = []
    for sh in step.get("shots") or []:
        uri = data_uri(sh.get("path", ""))
        if not uri:
            continue
        cls = ' class="phone"' if sh.get("phone") else ""
        out.append('<figure' + cls + '><img src="' + uri + '" alt="' + esc(sh.get("caption", "")) + '">'
                   + ('<figcaption>' + esc(sh["caption"]) + '</figcaption>' if sh.get("caption") else "")
                   + '</figure>')
    v = step.get("video")
    if v and v.get("url"):
        poster = data_uri(v.get("poster", "")) or ""
        out.append('<figure class="vid"><video src="' + esc(v["url"]) + '"'
                   + (' poster="' + poster + '"' if poster else "")
                   + ' controls playsinline preload="metadata"></video>'
                   + ('<figcaption>' + esc(v["caption"]) + '</figcaption>' if v.get("caption") else "")
                   + '</figure>')
    return '<div class="shots">' + "".join(out) + '</div>' if out else ""


def log_html(step):
    lines = step.get("log") or []
    if not lines:
        return ""
    rows = ['<li>' + esc(l) + '</li>' for l in lines]
    return '<ul class="log">' + "".join(rows) + '</ul>'


def say_html(step):
    t = step.get("say")
    if not t:
        return ""
    return '<div class="say"><span class="bot">AI</span><p>' + esc(t) + '</p></div>'


CSS = """
:root{
  --void:#04060e; --deep:#070a17; --panel:#0b1022; --raise:#10172d;
  --line:#1a2342; --line-hot:#28355f;
  --ink:#eef2fb; --mid:#9aa6c4; --dim:#5f6b8a;
  --neon:#2f86ff; --neon-dim:#123066; --blue:#8b6cff; --amber:#ffa630; --rose:#ff4f8b;
  --glow:0 0 0 1px rgba(47,134,255,.24), 0 0 34px -8px rgba(47,134,255,.4);
--story:linear-gradient(90deg,#ffa630,#ff4f8b 38%,#8b6cff 70%,#2f86ff);}
*{box-sizing:border-box}
body{
  margin:0; color:var(--ink); background:var(--void);
  font:16px/1.6 Manrope,system-ui,-apple-system,'Segoe UI',sans-serif;
  -webkit-font-smoothing:antialiased;
  background-image:
    radial-gradient(900px 520px at 78% -12%, rgba(47,134,255,.13), transparent 62%),
    radial-gradient(760px 460px at 8% 4%, rgba(111,156,255,.10), transparent 60%),
    linear-gradient(transparent 95%, rgba(255,255,255,.022) 95%),
    linear-gradient(90deg, transparent 95%, rgba(255,255,255,.022) 95%);
  background-size:auto,auto,34px 34px,34px 34px;
  background-attachment:fixed;
}
button{color:inherit;appearance:none}
:focus-visible{outline:2px solid var(--neon);outline-offset:3px;border-radius:6px}
.wrap{max-width:1080px;margin:0 auto;padding:34px 18px 90px}
h1,h2,h3{font-family:Unbounded,Manrope,system-ui,sans-serif;margin:0;letter-spacing:-.02em;text-wrap:balance}
.lab{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;letter-spacing:.16em;
     text-transform:uppercase;color:var(--dim)}
.lab.dim{color:#46527a}

.head{position:relative;border:1px solid var(--line);border-radius:18px;overflow:hidden;
      background:linear-gradient(160deg,var(--panel),var(--deep));padding:22px 24px}
.head::before{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(115deg,transparent 44%,rgba(47,134,255,.07) 50%,transparent 56%)}
.hrow{position:relative;display:flex;flex-wrap:wrap;gap:20px 26px;align-items:flex-end}
.hwho{flex:1 1 300px;min-width:0}
.head h1{font-size:clamp(23px,3.6vw,34px);line-height:1.12;margin-top:9px;font-weight:600}
.src{margin:9px 0 0;color:var(--mid);font-size:14.5px;word-break:break-word}
.src b{color:var(--neon);font-weight:500}
.hmeter{flex:0 0 auto;display:flex;gap:26px;align-items:flex-end}
.big{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:31px;font-weight:600;
     line-height:1;display:block;font-variant-numeric:tabular-nums}
.cap{font-size:12px;color:var(--dim);display:block;margin-top:7px}
.rail{margin-top:15px;height:4px;border-radius:3px;background:#10172d;overflow:hidden;position:relative}
.rail i{display:block;height:100%;border-radius:3px;
        background:var(--story);
        box-shadow:0 0 16px rgba(255,79,139,.45);transition:width .6s ease}
.live{display:inline-flex;align-items:center;gap:8px;padding:5px 11px;border-radius:999px;
      border:1px solid var(--neon-dim);background:rgba(47,134,255,.07);color:var(--neon);
      font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;letter-spacing:.1em;
      text-transform:uppercase}
.live i{width:6px;height:6px;border-radius:50%;background:var(--neon);
        box-shadow:0 0 0 0 rgba(47,134,255,.6);animation:pulse 1.7s infinite}
.live[data-done="1"]{border-color:#5a1f3a;background:rgba(255,79,139,.08);color:var(--rose)}
.live[data-done="1"] i{background:var(--blue);animation:none}
@keyframes pulse{70%{box-shadow:0 0 0 9px rgba(47,134,255,0)}100%{box-shadow:0 0 0 0 rgba(47,134,255,0)}}

.stick{position:relative;z-index:1;margin-top:16px;padding:10px 0 16px;
       background:var(--void)}
.stick::after{display:none}
.office{margin-top:0;width:fit-content;max-width:100%;border:1px solid var(--line);
        border-radius:18px;background:var(--panel);padding:11px 13px 12px;
        box-shadow:0 18px 40px -22px rgba(0,0,0,.95)}
.ohead{display:flex;justify-content:space-between;gap:12px;margin-bottom:9px;align-items:center}
.office .stage{border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#171a2c;line-height:0;text-align:center}
.office canvas{width:auto;max-width:100%;height:170px;display:block;image-rendering:pixelated}
.team{margin-top:8px;background:var(--void);position:relative;z-index:2}
.teamhead{display:none}
.mates{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.mate{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:999px;
      background:var(--panel);padding:4px 11px 4px 5px;display:flex;flex-direction:row;
      align-items:center;gap:7px;transition:.25s}
/* полоска работы: у готового залита, у активного бежит, у ждущего пустая */
.mate::before{content:"";position:absolute;left:0;bottom:0;height:2px;width:0;
              background:var(--neon);transition:width .5s ease}
.mate[data-s="done"]::before{width:100%;opacity:.55}
.mate[data-s="warn"]::before{width:100%;background:var(--amber);opacity:.7}
.mate[data-s="run"]::before{width:100%;background:linear-gradient(90deg,
  transparent,var(--neon),transparent);background-size:55% 100%;background-repeat:no-repeat;
  animation:runbar 1.5s linear infinite}
@keyframes runbar{0%{background-position:-60% 0}100%{background-position:160% 0}}

/* площадка, на которой стоит персонаж */
.pod{position:relative;display:block;margin:0;width:22px;height:22px;flex:0 0 22px;overflow:hidden;
     border-radius:50%;background:#111a33}
.face{position:relative;z-index:2;width:190%;height:190%;object-fit:contain;display:block;
      margin:-30% 0 0 -45%;image-rendering:pixelated;transition:filter .35s}
.ava{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;
     font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12px;font-weight:600;
     background:#111a33;border:1px solid var(--line-hot);color:var(--dim)}
.halo{display:none}
.tick{position:absolute;z-index:3;right:-1px;bottom:-1px;width:9px;height:9px;border-radius:50%;
      background:var(--neon);opacity:0;transform:scale(.4);transition:.3s}
.tick::after{content:""}

.mname{font-size:12.5px;font-weight:600;line-height:1.2;white-space:nowrap}
.mate[data-s="run"] .mname::after{content:"";display:inline-block;width:3px;height:3px;
  margin-left:6px;border-radius:50%;background:var(--neon);
  box-shadow:7px 0 0 var(--neon),14px 0 0 var(--neon);animation:dots 1.2s infinite}
@keyframes dots{0%,100%{opacity:.25}50%{opacity:1}}
.mate[data-s="run"]{padding-right:32px;border-color:rgba(47,134,255,.5)}
.mskill{display:none}
.mstate{display:none}

/* уже отработал: стоит спокойно, с галочкой */
.mate[data-s="done"] .halo{opacity:.28}
.mate[data-s="done"] .tick{opacity:1;transform:scale(1)}
.mate[data-s="done"] .mstate{color:var(--mid)}

/* работает прямо сейчас: подсвечен, покачивается, под ним пульсирует свет */
.mate[data-s="run"]{border-color:rgba(47,134,255,.45);box-shadow:var(--glow);background:#0b1430}
.mate[data-s="run"] .face{filter:drop-shadow(0 0 8px rgba(47,134,255,.75))}
.mate[data-s="run"] .halo{opacity:.75;animation:breathe 2.4s ease-in-out infinite}
.mate[data-s="run"] .mstate{color:var(--neon)}

@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
@keyframes breathe{0%,100%{opacity:.5;width:70%}50%{opacity:.95;width:84%}}
@keyframes sweep{0%{transform:translateX(-100%)}100%{transform:translateX(100%)}}

/* ещё не выходил: приглушён */
.mate[data-s="wait"] .face{filter:grayscale(1) brightness(.6)}
.mate[data-s="wait"]{opacity:.5}

/* момент, когда специалист только что закончил: подскок и вспышка */
.mate.justdone{animation:hop .75s cubic-bezier(.3,1.4,.5,1)}
.mate.justdone .pod::after{content:"";position:absolute;inset:-8%;border-radius:50%;
  background:radial-gradient(circle,rgba(47,134,255,.6),transparent 62%);
  animation:burst .75s ease-out forwards;pointer-events:none;z-index:1}
@keyframes hop{0%{transform:translateY(0)}35%{transform:translateY(-16px)}100%{transform:translateY(0)}}
@keyframes burst{0%{opacity:.95;transform:scale(.55)}100%{opacity:0;transform:scale(1.5)}}

/* кнопка звука */
.snd{position:absolute;top:16px;right:18px;z-index:5;display:inline-flex;align-items:center;gap:7px;
     border:1px solid var(--line-hot);background:rgba(8,12,19,.85);color:var(--mid);cursor:pointer;
     border-radius:999px;padding:7px 13px;font-family:'JetBrains Mono',ui-monospace,monospace;
     font-size:11px;letter-spacing:.08em;text-transform:uppercase;transition:.25s}
.snd:hover{border-color:var(--neon);color:var(--neon)}
.snd[data-on="1"]{border-color:var(--neon-dim);color:var(--neon);background:rgba(47,134,255,.08)}
.snd b{display:flex;gap:2px;align-items:flex-end;height:11px}
.snd b i{width:2px;background:currentColor;border-radius:1px;height:4px}
.snd[data-on="1"] b i{animation:eq .9s ease-in-out infinite}
.snd b i:nth-child(2){animation-delay:.15s}
.snd b i:nth-child(3){animation-delay:.3s}
@keyframes eq{0%,100%{height:4px}50%{height:11px}}

.steps{display:flex;flex-direction:column;gap:13px;margin-top:16px}
.card{position:relative;border:1px solid var(--line);border-radius:18px;background:var(--panel);
      padding:20px 22px}
.card[data-s="run"]{border-color:rgba(47,134,255,.4);box-shadow:var(--glow)}
.card[data-s="warn"]{border-color:rgba(255,180,84,.38)}
.top{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.no{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12px;color:#46527a;
    font-variant-numeric:tabular-nums}
.card h2{font-size:19px;flex:1 1 auto;min-width:0;font-weight:600}
.by{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;color:var(--dim);
    border:1px solid var(--line);border-radius:999px;padding:4px 9px;white-space:nowrap}
.pill{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;letter-spacing:.09em;
      text-transform:uppercase;padding:4px 10px;border-radius:999px;border:1px solid var(--line);
      color:var(--dim);white-space:nowrap}
.card[data-s="done"] .pill{color:var(--neon);border-color:var(--neon-dim)}
.card[data-s="run"] .pill{color:var(--void);background:var(--neon);border-color:var(--neon)}
.card[data-s="warn"] .pill{color:var(--amber);border-color:rgba(255,180,84,.4)}
.note{margin:12px 0 0;color:var(--mid);max-width:70ch}
.fold{padding:0}
.fold summary{list-style:none;cursor:pointer;padding:14px 20px}
.fold summary::-webkit-details-marker{display:none}
.fold summary .top{margin:0}
.fold summary h2{font-size:16px;font-weight:600;color:var(--mid)}
.fold[open] summary h2{color:var(--ink)}
.fold > *:not(summary){padding:0 20px}
.fold > *:last-child{padding-bottom:18px}
.fold summary::after{content:"развернуть";font-family:'JetBrains Mono',ui-monospace,monospace;
  font-size:10px;color:var(--dim);border:1px solid var(--line);border-radius:999px;padding:3px 9px}
.fold[open] summary::after{content:"свернуть"}

.say{display:flex;gap:12px;margin-top:14px;align-items:flex-start}
.say .bot{flex:0 0 30px;width:30px;height:30px;border-radius:9px;display:grid;place-items:center;
          background:linear-gradient(150deg,var(--neon),var(--blue));color:var(--void);
          font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;font-weight:700}
.say p{margin:0;background:var(--raise);border:1px solid var(--line);border-radius:4px 14px 14px 14px;
       padding:11px 15px;font-size:15.5px;line-height:1.55;max-width:64ch}

.chips{list-style:none;display:flex;flex-wrap:wrap;gap:7px;margin:15px 0 0;padding:0}
.chips li{background:var(--raise);border:1px solid var(--line);border-radius:999px;
          padding:5px 12px;font-size:13.5px;color:var(--mid)}
.facts{list-style:none;margin:15px 0 0;padding:0;display:flex;flex-direction:column;gap:9px}
.facts li{display:flex;gap:11px;align-items:flex-start;font-size:15px}
.facts .bul{width:8px;height:8px;border-radius:50%;margin-top:8px;flex:0 0 8px;background:var(--neon)}
.facts li[data-s="run"] .bul{background:var(--amber)}
.facts li[data-s="warn"] .bul{background:var(--rose)}
.facts li[data-s="wait"] .bul{background:var(--line-hot)}
.facts li[data-s="wait"]{color:var(--dim)}
.nums{display:flex;flex-wrap:wrap;gap:14px;margin-top:18px}
.nums div{flex:1 1 120px;border:1px solid var(--line);border-radius:12px;background:var(--deep);padding:12px 14px}
.nums b{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:23px;font-weight:600;
        display:block;line-height:1.1;color:var(--neon);font-variant-numeric:tabular-nums}
.nums span{font-size:12.5px;color:var(--dim)}

.log{list-style:none;margin:15px 0 0;padding:13px 15px;border:1px solid var(--line);border-radius:12px;
     background:#060914;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12.5px;
     color:var(--mid);display:flex;flex-direction:column;gap:6px;max-height:190px;overflow:auto}
.log li{display:flex;gap:9px}
.log li::before{content:"\\203A";color:var(--neon);flex:0 0 auto}

.doc{margin-top:15px;border:1px solid var(--line);border-radius:13px;background:var(--deep);overflow:hidden}
.doc + .doc{margin-top:9px}
.doc summary{display:flex;align-items:center;gap:11px;padding:13px 15px;cursor:pointer;list-style:none}
.doc summary::-webkit-details-marker{display:none}
.dicon{flex:0 0 16px;width:16px;height:20px;border-radius:2px;border:1px solid var(--line-hot);
       background:linear-gradient(180deg,#162040,#0c1225);position:relative}
.dicon::after{content:"";position:absolute;left:3px;right:3px;top:5px;height:1px;background:var(--dim);
              box-shadow:0 4px 0 var(--dim),0 8px 0 var(--dim)}
.dname{font-size:14.5px;flex:1 1 auto;min-width:0}
.dmeta{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;color:var(--neon);white-space:nowrap}
.dopen{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;color:var(--dim);
       border:1px solid var(--line);border-radius:999px;padding:3px 9px;white-space:nowrap}
.doc pre{margin:0;padding:14px 15px 15px;white-space:pre-wrap;word-break:break-word;
         font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12.5px;line-height:1.7;
         color:var(--mid);max-height:460px;overflow:auto;border-top:1px solid var(--line)}

.shots{display:grid;gap:13px;margin-top:18px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.shots figure{margin:0;min-width:0}
.shots figure.phone{max-width:270px}
.shots img,.shots video{width:100%;display:block;border-radius:12px;border:1px solid var(--line);background:#000}
.shots figcaption{font-size:12.5px;color:var(--dim);margin-top:8px}

.ahead{border:1px dashed var(--line);border-radius:18px;padding:15px 20px}
.ahead .lab{display:block;margin-bottom:11px}
.ahead ol{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:9px 22px}
.ahead li{color:var(--dim);font-size:14.5px;display:flex;gap:9px;align-items:baseline}

.foot{margin-top:26px;padding-top:17px;border-top:1px solid var(--line);
      display:flex;flex-wrap:wrap;gap:8px 20px;color:var(--dim);font-size:13.5px}
.foot a{color:var(--neon)}
@media (max-width:560px){
  .wrap{padding:22px 16px 70px}
  .head{padding:18px 16px;border-radius:15px}
  .hmeter{gap:20px}
  .card{padding:17px 16px;border-radius:15px}
  .mates{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

JS = """
(function(){
  var wrap = document.querySelector('.wrap');
  if(!wrap) return;
  var live = wrap.getAttribute('data-live') === '1';

  /* часы прогона */
  var el = document.getElementById('clock');
  if(el){
    var s = parseInt(el.getAttribute('data-from') || '0', 10);
    var p = function(n){ return (n < 10 ? '0' : '') + n; };
    var tick = function(){
      var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
      el.textContent = (h > 0 ? h + ':' + p(m) : p(m)) + ':' + p(x);
      s += 1;
    };
    tick();
    if(live) setInterval(tick, 1000);
  }

  /* звук синтезируем на месте: файлов нет, значит нечему не загрузиться */
  var actx = null, on = false;
  var store = function(k, v){ try{ if(v === undefined) return sessionStorage.getItem(k);
                                   sessionStorage.setItem(k, v); }catch(e){ return null; } };
  function ctx(){
    if(!actx){
      var C = window.AudioContext || window.webkitAudioContext;
      if(!C) return null;
      actx = new C();
    }
    if(actx.state === 'suspended') actx.resume();
    return actx;
  }
  function note(freq, at, len, vol){
    var a = ctx(); if(!a) return;
    var o = a.createOscillator(), g = a.createGain();
    o.type = 'triangle';
    o.frequency.setValueAtTime(freq, a.currentTime + at);
    g.gain.setValueAtTime(0, a.currentTime + at);
    g.gain.linearRampToValueAtTime(vol, a.currentTime + at + 0.015);
    g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + at + len);
    o.connect(g); g.connect(a.destination);
    o.start(a.currentTime + at); o.stop(a.currentTime + at + len + 0.05);
  }
  function play(kind){
    if(!on) return;
    if(kind === 'done'){ note(659.25, 0, .18, .16); note(830.61, .09, .18, .14); note(987.77, .18, .34, .12); }
    else if(kind === 'final'){ note(523.25, 0, .5, .15); note(659.25, .1, .5, .13);
                               note(783.99, .2, .5, .12); note(1046.5, .3, .7, .11); }
    else { note(880, 0, .09, .08); }
  }

  var btn = document.getElementById('snd');
  if(btn){
    on = store('sb_snd') === '1';
    btn.setAttribute('data-on', on ? '1' : '0');
    btn.querySelector('span').textContent = on ? 'звук включён' : 'включить звук';
    btn.addEventListener('click', function(){
      on = !on;
      store('sb_snd', on ? '1' : '0');
      btn.setAttribute('data-on', on ? '1' : '0');
      btn.querySelector('span').textContent = on ? 'звук включён' : 'включить звук';
      if(on) play('step');
    });
  }

  /* сразу показываем этап, который идёт сейчас */
  var now = document.getElementById('nowstep');
  if(now){
    var stick = document.querySelector('.stick');
    var pad = 18;
    var y = now.getBoundingClientRect().top + window.pageYOffset - pad;
    if(y > 40) window.scrollTo({top: y, behavior: 'smooth'});
  }

  /* что изменилось с прошлой публикации: празднуем ровно новые готовые этапы */
  var mates = [].slice.call(document.querySelectorAll('.mate'));
  var doneNow = parseInt(wrap.getAttribute('data-done') || '0', 10);
  var donePrev = parseInt(store('sb_done') || '-1', 10);
  store('sb_done', String(doneNow));
  if(donePrev >= 0 && doneNow > donePrev){
    var justDone = mates.filter(function(m){ return m.getAttribute('data-s') === 'done'; }).pop();
    if(justDone){
      justDone.classList.add('justdone');
      setTimeout(function(){ justDone.classList.remove('justdone'); }, 900);
    }
    play(wrap.getAttribute('data-live') === '1' ? 'done' : 'final');
  }
})();
"""

PAGE = Template("""<title>$title</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;600&family=Manrope:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap">
<style>$css</style>
<div class="wrap" data-live="$live" data-done="$donecount">
  <header class="head">
    <button class="snd" id="snd" data-on="0" type="button">
      <b><i></i><i></i><i></i></b><span>включить звук</span>
    </button>
    <div class="hrow">
      <div class="hwho">
        <span class="live" data-done="$alldone"><i></i>$livetext</span>
        <h1>$clinic</h1>
        <p class="src">$source</p>
      </div>
      <div class="hmeter">
        <div><b class="big" id="clock" data-from="$elapsed">00:00</b><span class="cap">в работе</span></div>
        <div><b class="big">$donecount/$total</b><span class="cap">этапов</span></div>
      </div>
    </div>
    <div class="rail"><i style="width:$pct%"></i></div>
  </header>
  <div class="stick">
$office
$team
  </div>
  <div class="steps">
$steps
  </div>
  <footer class="foot">$foot</footer>
</div>
<script>$js</script>
$officejs
""")


def office_html(state):
    """Живой офис наверху экрана: за компьютер садится тот, чей этап идёт."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import ofis
    except ImportError:
        return "", ""

    team = state.get("team") or []
    if not team:
        return "", ""

    seats = [c[4] for c in ofis.CREW]
    sprites = [(c[2], c[3]) for c in ofis.CREW]
    crew, active = [], 0
    for k, m in enumerate(team[:len(seats)]):
        sp, tn = sprites[k]
        crew.append(chr(123) + 'name:"%s",doing:"%s",sprite:%d,tint:%d,home:[%d,%d]' % (
            esc(m.get("name", "")), esc(m.get("doing") or ""), sp, tn,
            seats[k][0], seats[k][1]) + chr(125))
        if m.get("status") == "run":
            active = k

    art = ofis.probe(ofis.assets())
    art_js = ",".join('"%s":"%s"' % (k, v) for k, v in sorted(art.items()))
    lay_js = ",".join('["%s",%d,%d]' % o for o in ofis.LAYOUT)
    js = ofis.JS.replace("__COLS__", str(ofis.COLS)).replace("__ROWS__", str(ofis.ROWS))

    block = ('<section class="office">'
             '<div class="ohead"><span class="lab">офис агента</span>'
             '<span class="lab dim">работает ' + esc(team[active].get("name", "")) + '</span></div>'
             '<div class="stage"><canvas id="office"></canvas></div></section>')

    tail = ('<script>window.__ART__={' + art_js + '};'
            'window.__CREW__=[' + ",".join(crew) + '];'
            'window.__LAY__=[' + lay_js + '];'
            'window.__CARPET__=[%d,%d,%d,%d];'
            'window.__ACTIVE__=%d;</script><script>' % (
                ofis.CARPET[0], ofis.CARPET[1], ofis.CARPET[2], ofis.CARPET[3], active)
            + js + '</script>')
    return block, tail


def build(state):
    steps = state.get("steps", [])
    steps_html = []
    ahead = []
    for i, s in enumerate(steps, 1):
        st = s.get("status", "wait")
        if st == "wait":
            ahead.append('<li><span class="no">' + ("%02d" % i) + '</span>' + esc(s.get("title", "")) + '</li>')
            continue
        by = ('<span class="by">' + esc(s["by"]) + '</span>') if s.get("by") else ""
        body = ""
        if s.get("note"):
            body += '<p class="note">' + esc(s["note"]) + '</p>'
        body += say_html(s)
        body += chips(s.get("chips"))
        body += facts(s.get("items"))
        body += log_html(s)
        body += doc_html(s.get("docs") or s.get("doc"))
        body += nums(s.get("nums"))
        body += media_html(s)
        head = ('<div class="top"><span class="no">' + ("%02d" % i) + '</span>'
                '<h2>' + esc(s.get("title", "")) + '</h2>' + by
                + '<span class="pill">' + LABEL.get(st, st) + '</span></div>')
        if st == "done":
            steps_html.append(
                '<details class="card fold" data-s="done"><summary>' + head + '</summary>'
                + body + '</details>')
        else:
            steps_html.append(
                '<section class="card" data-s="' + esc(st) + '" id="nowstep">'
                + head + body + '</section>')

    if ahead:
        steps_html.append('<section class="ahead"><span class="lab">дальше по плану</span>'
                          '<ol>' + "".join(ahead) + '</ol></section>')

    foot = []
    if state.get("site"):
        foot.append('<span>Сайт: <a href="' + esc(state["site"]) + '">' + esc(state["site"]) + '</a></span>')
    if state.get("folder"):
        foot.append('<span>Папка: ' + esc(state["folder"]) + '</span>')
    if state.get("updated"):
        foot.append('<span>Обновлено: ' + esc(state["updated"]) + '</span>')

    office_block, office_tail = office_html(state)

    total = len(steps)
    done = sum(1 for s in steps if s.get("status") == "done")
    running = any(s.get("status") == "run" for s in steps)
    alldone = "0" if running or done < total else "1"
    src = state.get("source")
    source = ('Взял в работу <b>' + esc(src) + '</b>') if src else esc(state.get("subtitle", ""))

    return PAGE.substitute(
        title=esc(state.get("title") or state.get("clinic", "Запуск рекламы")),
        css=CSS, js=JS,
        live="1" if running else "0",
        alldone=alldone,
        livetext=esc(state.get("livetext") or ("агент работает" if running else "работа закончена")),
        clinic=esc(state.get("clinic", "")),
        source=source,
        elapsed=int(state.get("elapsed", 0)),
        donecount=done, total=total,
        pct=int(round(done * 100.0 / total)) if total else 0,
        office=office_block,
        officejs=office_tail,
        team=team_html(state.get("team")),
        steps="\n".join(steps_html),
        foot="".join(foot) or "<span>Прогон идёт</span>")


def main():
    if not os.path.exists(STATE):
        sys.exit("нет файла состояния: " + STATE)
    state = json.load(io.open(STATE, encoding="utf-8"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(build(state))
    size = os.path.getsize(OUT) / 1048576.0
    print("экран собран: %s (%.2f МБ)" % (OUT, size))
    if size > 15:
        print("ВНИМАНИЕ: артефакт не берёт больше 16 МБ, убери часть скриншотов")


if __name__ == "__main__":
    main()
