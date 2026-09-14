# -*- coding: utf-8 -*-
"""Собирает пиксельный офис агента: девять специалистов живут и работают.

Спрайты взяты из пака MetroCity (JIK-A-4, лицензия CC0) в том виде, в каком
их раздаёт пакет pixel-agents (MIT). Персонаж это 16x32, семь кадров в трёх
направлениях: вниз, вбок, вверх. Всё вшивается в страницу целиком, потому что
артефакт не пускает внешние адреса.

Запуск:  python .claude/skills/site-agent/ofis.py

Changes when: меняется раскладка офиса, состав команды или поведение.

Anti-goal: не рисует прогресса, которого не было. Это сцена, а не отчёт.
"""
import base64
import io
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
PIX = os.path.join(ROOT, "assets", "pixel")
OUT = os.path.join(ROOT, "build", "Офис.html")

TILE = 16          # размер тайла в пикселях спрайта
COLS, ROWS = 32, 11

# имя агента, чем занят, цвет подсветки, номер спрайта, поворот оттенка,
# клетка стула и клетка, куда смотрит стол
CREW = [
    ("Техник",            "подключаю кабинет",        0, 0, (3, 3)),
    ("Оценщик видео", "смотрю, зацепит ли видео",             1, 0, (11, 3)),
    ("Искатель зрителей",        "ищу, кому показать",       2, 0, (19, 3)),
    ("Автор текста",          "пишу текст рекламы",          3, 0, (3, 8)),
    ("Планировщик",        "решаю, где и за сколько",         4, 0, (7, 8)),
    ("Контролёр",         "проверяю и запускаю",      5, 0, (11, 8)),
]


def uri(rel):
    full = os.path.join(PIX, rel)
    if not os.path.exists(full):
        return ""
    return "data:image/png;base64," + base64.b64encode(io.open(full, "rb").read()).decode("ascii")


def assets():
    """Что грузим в страницу. Ключ это имя, по которому зовём из раскладки."""
    need = {
        "floor": "floors/floor_2.png",
        "floor_alt": "floors/floor_5.png",
        "wall": "walls/wall_0.png",
        "carpet": "carpets/carpet_0.png",
        "desk_front": "furniture/DESK/DESK_FRONT.png",
        "desk_side": "furniture/DESK/DESK_SIDE.png",
        "pc_off": "furniture/PC/PC_FRONT_OFF.png",
        "pc_on1": "furniture/PC/PC_FRONT_ON_1.png",
        "pc_on2": "furniture/PC/PC_FRONT_ON_2.png",
        "pc_on3": "furniture/PC/PC_FRONT_ON_3.png",
        "chair_back": "furniture/WOODEN_CHAIR/WOODEN_CHAIR_BACK.png",
        "chair_front": "furniture/WOODEN_CHAIR/WOODEN_CHAIR_FRONT.png",
        "sofa": "furniture/SOFA/SOFA_FRONT.png",
        "small_table": "furniture/SMALL_TABLE/SMALL_TABLE_FRONT.png",
        "coffee_table": "furniture/COFFEE_TABLE/COFFEE_TABLE.png",
        "bookshelf": "furniture/BOOKSHELF/BOOKSHELF.png",
        "bookshelf2": "furniture/DOUBLE_BOOKSHELF/DOUBLE_BOOKSHELF.png",
        "plant": "furniture/PLANT/PLANT.png",
        "plant2": "furniture/PLANT_2/PLANT_2.png",
        "big_plant": "furniture/LARGE_PLANT/LARGE_PLANT.png",
        "cactus": "furniture/CACTUS/CACTUS.png",
        "board": "furniture/WHITEBOARD/WHITEBOARD.png",
        "painting": "furniture/LARGE_PAINTING/LARGE_PAINTING.png",
        "clock": "furniture/CLOCK/CLOCK.png",
        "coffee": "furniture/COFFEE/COFFEE.png",
        "bin": "furniture/BIN/BIN.png",
    }
    out = {}
    for key, rel in need.items():
        u = uri(rel)
        if u:
            out[key] = u
    for k in range(6):
        u = uri("characters/char_%d.png" % k)
        if u:
            out["char%d" % k] = u
    return out


LAYOUT = [
    # на стене
    ("board", 2, 0), ("painting", 9, 0), ("painting", 17, 0), ("clock", 25, 0),
    ("bookshelf2", 5, 0), ("bookshelf", 13, 0), ("bookshelf", 21, 0), ("bookshelf2", 28, 0),

    # верхний ряд рабочих мест
    ("desk_front", 3, 2), ("desk_front", 7, 2), ("desk_front", 11, 2),
    ("desk_front", 15, 2), ("desk_front", 19, 2), ("desk_front", 23, 2),

    # нижний ряд рабочих мест
    ("desk_front", 3, 7), ("desk_front", 7, 7), ("desk_front", 11, 7),

    # зона отдыха справа
    ("sofa", 21, 8), ("coffee_table", 23, 9), ("sofa", 25, 8),
    ("big_plant", 19, 8), ("plant2", 27, 8), ("coffee", 20, 7),
    ("small_table", 28, 9),

    # зелень и мелочь
    ("plant", 1, 2), ("cactus", 1, 7), ("plant2", 30, 2),
    ("plant", 16, 7), ("bin", 14, 8), ("cactus", 30, 10),
    ("plant2", 1, 10), ("big_plant", 17, 10),

    # левый и правый край комнаты
    ("bookshelf", 0, 0), ("bookshelf2", 30, 0),
    ("big_plant", 0, 4), ("cactus", 31, 4),
    ("plant", 0, 8), ("plant2", 31, 7),
    ("bin", 0, 11), ("small_table", 31, 11),
]

# ковровая зона отдыха: с какого по какой тайл
CARPET = (20, 8, 29, 10)


def probe(found):
    """Часть спрайтов лежит под другими именами: подставляем, что нашлось."""
    import glob
    fixes = {
        "sofa": "furniture/SOFA/*.png",
        "coffee_table": "furniture/COFFEE_TABLE/*.png",
        "bookshelf": "furniture/BOOKSHELF/*.png",
        "bookshelf2": "furniture/DOUBLE_BOOKSHELF/*.png",
        "plant": "furniture/PLANT/*.png",
        "plant2": "furniture/PLANT_2/*.png",
        "big_plant": "furniture/LARGE_PLANT/*.png",
        "cactus": "furniture/CACTUS/*.png",
        "board": "furniture/WHITEBOARD/*.png",
        "painting": "furniture/LARGE_PAINTING/*.png",
        "clock": "furniture/CLOCK/*.png",
        "coffee": "furniture/COFFEE/*.png",
        "bin": "furniture/BIN/*.png",
        "carpet": "carpets/*.png",
    }
    for key, pat in fixes.items():
        if key in found:
            continue
        hits = sorted(glob.glob(os.path.join(PIX, pat.replace("/", os.sep))))
        hits = [h for h in hits if not h.endswith("manifest.json")]
        if hits:
            found[key] = "data:image/png;base64," + base64.b64encode(
                io.open(hits[0], "rb").read()).decode("ascii")
    return found


CSS = """
:root{
  --void:#05070b; --panel:#0c121b; --line:#1b2634;
  --ink:#eef2fb; --mid:#9aa6c4; --dim:#5f6b8a; --neon:#2f86ff;
}
*{box-sizing:border-box}
body{margin:0;background:var(--void);color:var(--ink);
     font:16px/1.6 Manrope,system-ui,-apple-system,'Segoe UI',sans-serif;-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:24px 16px 60px}
h1{font-family:Unbounded,Manrope,system-ui,sans-serif;font-size:clamp(19px,3vw,26px);
   margin:0 0 6px;font-weight:600;letter-spacing:-.02em}
.sub{color:var(--mid);margin:0 0 18px;font-size:14.5px;max-width:66ch}
.lab{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;letter-spacing:.16em;
     text-transform:uppercase;color:var(--dim)}
.stage{position:relative;border:1px solid var(--line);border-radius:16px;overflow:hidden;
       background:#1a1a24;line-height:0}
canvas{width:100%;height:auto;display:block;image-rendering:pixelated}
.bar{margin-top:14px;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;
     border:1px solid var(--line);border-radius:14px;background:var(--panel);padding:13px 16px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--neon);flex:0 0 8px;animation:blink 1.6s infinite}
@keyframes blink{50%{opacity:.25}}
.bar b{font-weight:600;font-size:15px}
.bar span{color:var(--mid);font-size:14px}
.crew{margin-top:14px;display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}
.card{border:1px solid var(--line);border-radius:11px;background:var(--panel);padding:9px 12px;
      display:flex;align-items:center;gap:9px;transition:.25s}
.card i{width:7px;height:7px;border-radius:50%;background:#243447;flex:0 0 7px}
.card b{font-size:13.5px;font-weight:600}
.card em{font-style:normal;font-size:12px;color:var(--dim);margin-left:auto}
.card[data-on="1"]{border-color:rgba(47,134,255,.45);background:#0b1430}
.card[data-on="1"] i{background:var(--neon);box-shadow:0 0 8px var(--neon)}
.card[data-on="1"] em{color:var(--neon)}
.hint{margin-top:12px;color:var(--dim);font-size:13px;max-width:74ch}
@media (prefers-reduced-motion:reduce){.dot{animation:none}}
"""

JS = """
(function(){
  var A = window.__ART__, CREW = window.__CREW__, LAY = window.__LAY__;
  var TILE = 16, COLS = __COLS__, ROWS = __ROWS__, CARPET = window.__CARPET__;
  var cv = document.getElementById('office');
  if(!cv) return;
  var cx = cv.getContext('2d');
  cv.width = COLS * TILE; cv.height = ROWS * TILE;
  cx.imageSmoothingEnabled = false;

  var img = {}, left = 0;
  Object.keys(A).forEach(function(k){
    left++;
    var im = new Image();
    im.onload = im.onerror = function(){ left--; if(left === 0) start(); };
    im.src = A[k]; img[k] = im;
  });

  /* шесть исходных персонажей на девять агентов: лишних перекрашиваем */
  function tinted(im, deg){
    if(!deg) return im;
    var c = document.createElement('canvas');
    c.width = im.width; c.height = im.height;
    var g = c.getContext('2d');
    g.filter = 'hue-rotate(' + deg + 'deg) saturate(1.2)';
    g.drawImage(im, 0, 0);
    return c;
  }

  var ROW = {down: 0, side: 1, up: 2};

  function Agent(spec){
    this.name = spec.name; this.doing = spec.doing;
    this.sprite = spec.sprite; this.tint = spec.tint;
    this.home = {x: spec.home[0], y: spec.home[1]};
    this.x = spec.home[0] + 0.5; this.y = spec.home[1] + 0.5;
    this.dir = 'up'; this.flip = false; this.frame = 0; this.t = 0;
    this.state = 'sit'; this.path = []; this.wait = 1 + Math.random() * 5;
    this.atHome = true; this.busy = false;
  }

  Agent.prototype.draw = function(){
    var f = this.state === 'walk' ? (1 + (this.frame % 6)) : 0;
    var px = Math.round(this.x * TILE - 8);
    var py = Math.round(this.y * TILE - 26);
    if(this.flip){
      cx.save();
      cx.translate(px + 16, py);
      cx.scale(-1, 1);
      cx.drawImage(this.sheet, f * 16, ROW[this.dir] * 32, 16, 32, 0, 0, 16, 32);
      cx.restore();
    } else {
      cx.drawImage(this.sheet, f * 16, ROW[this.dir] * 32, 16, 32, px, py, 16, 32);
    }
  };

  /* ходим по двум коридорам, чтобы не лезть сквозь столы */
  var LANES = [5, 10];
  function routeTo(a, tx, ty){
    var lane = LANES.reduce(function(best, l){
      return Math.abs(l - a.y) < Math.abs(best - a.y) ? l : best;
    }, LANES[0]);
    a.path = [{x: a.x, y: lane + 0.5},
              {x: tx + 0.5, y: lane + 0.5},
              {x: tx + 0.5, y: ty + 0.5}];
  }

  function step(a, dt){
    if(a.state === 'walk' && a.path.length){
      var p = a.path[0], dx = p.x - a.x, dy = p.y - a.y;
      var d = Math.sqrt(dx * dx + dy * dy), v = 3.2 * dt;
      if(d <= v){
        a.x = p.x; a.y = p.y; a.path.shift();
        if(!a.path.length){
          a.state = a.atHome ? 'sit' : 'stand';
          a.dir = a.atHome ? 'up' : 'down';
          a.flip = false;
          a.wait = a.atHome ? 4 + Math.random() * 6 : 2 + Math.random() * 4;
        }
      } else {
        a.x += dx / d * v; a.y += dy / d * v;
        if(Math.abs(dx) > Math.abs(dy)){ a.dir = 'side'; a.flip = dx < 0; }
        else { a.dir = dy > 0 ? 'down' : 'up'; a.flip = false; }
        a.t += dt;
        if(a.t > 0.1){ a.t = 0; a.frame++; }
      }
      return;
    }
    a.wait -= dt;
    if(a.wait > 0) return;

    if(a.busy && !(a.atHome && a.state === 'sit')){
      a.atHome = true; a.state = 'walk';
      routeTo(a, a.home.x, a.home.y);
      return;
    }
    if(a.busy) { a.wait = 2; return; }

    a.atHome = Math.random() < 0.45;
    var tx, ty;
    if(a.atHome){ tx = a.home.x; ty = a.home.y; }
    else {
      tx = 2 + Math.floor(Math.random() * (COLS - 5));
      ty = LANES[Math.floor(Math.random() * LANES.length)];
    }
    a.state = 'walk';
    routeTo(a, tx, ty);
  }

  var agents = [], active = 0, blink = 0;

  /* фон статичен: рисуем один раз, тонируем под интерфейс и кэшируем */
  var bg = null;
  function buildBackground(){
    bg = document.createElement('canvas');
    bg.width = COLS * TILE; bg.height = ROWS * TILE;
    var b = bg.getContext('2d');
    b.imageSmoothingEnabled = false;

    for(var y = 0; y < ROWS; y++){
      for(var x = 0; x < COLS; x++){
        if(y < 1){
          if(img.wall) b.drawImage(img.wall, 16, 16, 16, 16, x * TILE, y * TILE, TILE, TILE);
        } else {
          var t = ((x * 3 + y * 5) % 11 === 0 && img.floor_alt) ? img.floor_alt : img.floor;
          if(t) b.drawImage(t, 0, 0, 16, 16, x * TILE, y * TILE, TILE, TILE);
        }
      }
    }
    if(img.carpet && CARPET){
      for(var cy = CARPET[1]; cy <= CARPET[3]; cy++)
        for(var k = CARPET[0]; k <= CARPET[2]; k++)
          b.drawImage(img.carpet, 0, 0, 16, 16, k * TILE, cy * TILE, TILE, TILE);
    }

    /* перекрашиваем пол и стены в палитру интерфейса */
    b.globalCompositeOperation = 'color';
    b.fillStyle = '#14293b';
    b.fillRect(0, 0, bg.width, bg.height);

    b.globalCompositeOperation = 'multiply';
    b.fillStyle = '#7d94b4';
    b.fillRect(0, 0, bg.width, bg.height);

    b.globalCompositeOperation = 'source-over';
    b.fillStyle = 'rgba(6,10,17,.55)';
    b.fillRect(0, 0, bg.width, 1 * TILE);
    var g = b.createLinearGradient(0, 1 * TILE, 0, bg.height);
    g.addColorStop(0, 'rgba(47,134,255,.05)');
    g.addColorStop(1, 'rgba(6,10,17,.35)');
    b.fillStyle = g;
    b.fillRect(0, 1 * TILE, bg.width, bg.height - 1 * TILE);
  }

  function drawFloor(){
    if(!bg) buildBackground();
    cx.drawImage(bg, 0, 0);
  }

  function pcOn(){
    var n = [img.pc_on1, img.pc_on2, img.pc_on3].filter(Boolean);
    return n.length ? n[Math.floor(blink) % n.length] : img.pc_off;
  }

  function frame(){
    drawFloor();
    var items = [];

    LAY.forEach(function(o){
      var im = img[o[0]];
      if(!im) return;
      items.push({y: o[2] * TILE + TILE, draw: function(){
        cx.save();
        cx.filter = 'saturate(.72) brightness(.86) hue-rotate(-8deg)';
        cx.drawImage(im, o[1] * TILE, o[2] * TILE + TILE - im.height);
        cx.restore();
      }});
    });

    agents.forEach(function(a){
      var working = a.busy && a.state === 'sit';
      var pc = working ? pcOn() : img.pc_off;
      if(pc){
        items.push({y: (a.home.y - 1) * TILE + TILE, draw: function(){
          cx.drawImage(pc, a.home.x * TILE, (a.home.y - 1) * TILE + TILE - pc.height);
        }});
      }
      if(working){
        items.push({y: a.y * TILE - 1, draw: function(){
          var g = cx.createRadialGradient(a.x * TILE, a.y * TILE - 6, 1, a.x * TILE, a.y * TILE - 6, 22);
          g.addColorStop(0, 'rgba(47,134,255,.28)');
          g.addColorStop(1, 'rgba(47,134,255,0)');
          cx.fillStyle = g;
          cx.fillRect(a.x * TILE - 22, a.y * TILE - 28, 44, 44);
        }});
      }
      items.push({y: a.y * TILE, draw: function(){ a.draw(); }});
      if(working){
        items.push({y: a.y * TILE + 1, draw: function(){
          var bob = Math.sin(blink * 2) > 0 ? 0 : 1;
          cx.fillStyle = 'rgba(47,134,255,.9)';
          cx.fillRect(Math.round(a.x * TILE) - 1, Math.round(a.y * TILE) - 34 - bob, 3, 3);
          cx.fillRect(Math.round(a.x * TILE) - 4, Math.round(a.y * TILE) - 31 - bob, 9, 2);
        }});
      }
    });

    items.sort(function(p, q){ return p.y - q.y; });
    items.forEach(function(it){ it.draw(); });
  }

  function start(){
    agents = CREW.map(function(c){
      var a = new Agent(c);
      a.sheet = tinted(img['char' + c.sprite], c.tint);
      return a;
    });

    /* строка состояния и карточки есть не на всякой странице: без них тоже работаем */
    var cards = [].slice.call(document.querySelectorAll('.card'));
    var who = document.getElementById('who'), what = document.getElementById('what');
    function setActive(k){
      agents.forEach(function(a, n){
        a.busy = (n === k);
        if(n === k) a.wait = Math.min(a.wait, 0.2);
      });
      cards.forEach(function(el, n){ el.setAttribute('data-on', n === k ? '1' : '0'); });
      if(who) who.textContent = CREW[k].name;
      if(what) what.textContent = CREW[k].doing;
    }
    window.__setActive = setActive;
    setActive(typeof window.__ACTIVE__ === 'number' ? window.__ACTIVE__ : 0);
    if(window.__LOOP_ACTIVE__){
      setInterval(function(){
        active = (active + 1) % CREW.length;
        setActive(active);
      }, 9000);
    }

    var last = performance.now();
    requestAnimationFrame(function loop(now){
      var dt = Math.min(0.05, (now - last) / 1000);
      last = now; blink += dt * 5;
      agents.forEach(function(a){ step(a, dt); });
      frame();
      requestAnimationFrame(loop);
    });
  }
})();
"""


def build():
    art = probe(assets())
    crew_js = ",".join(
        '{name:"%s",doing:"%s",sprite:%d,tint:%d,home:[%d,%d]}' % (n, d, sp, tn, h[0], h[1])
        for n, d, sp, tn, h in CREW)
    lay_js = ",".join('["%s",%d,%d]' % o for o in LAYOUT)
    art_js = ",".join('"%s":"%s"' % (k, v) for k, v in sorted(art.items()))
    cards = "".join(
        '<div class="card" data-on="0"><i></i><b>%s</b><em>%s</em></div>' % (n, d)
        for n, d, sp, tn, h in CREW)

    js = JS.replace("__COLS__", str(COLS)).replace("__ROWS__", str(ROWS))

    return """<title>Офис агента</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Unbounded:wght@500;600&family=Manrope:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>%s</style>
<div class="wrap">
  <span class="lab">команда агента за работой</span>
  <h1>Офис агента</h1>
  <p class="sub">Девять специалистов делают сайт. Чья очередь, тот идёт на своё место, садится за компьютер, и экран у него оживает. Остальные не стоят столбом: ходят по офису, отходят к дивану, возвращаются.</p>

  <div class="stage"><canvas id="office"></canvas></div>

  <div class="bar">
    <span class="dot"></span><b id="who"></b><span id="what"></span>
  </div>
  <div class="crew">%s</div>
  <p class="hint">Персонажи и мебель из набора MetroCity, автор JIK-A-4, лицензия CC0.</p>
</div>
<script>
window.__ART__ = {%s};
window.__CREW__ = [%s];
window.__LAY__ = [%s];
window.__CARPET__ = [%d,%d,%d,%d];
</script>
<script>%s</script>
""" % (CSS, cards, art_js, crew_js, lay_js,
       CARPET[0], CARPET[1], CARPET[2], CARPET[3], js)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(build())
    print("офис собран: %s (%.2f МБ)" % (OUT, os.path.getsize(OUT) / 1048576.0))


if __name__ == "__main__":
    main()
