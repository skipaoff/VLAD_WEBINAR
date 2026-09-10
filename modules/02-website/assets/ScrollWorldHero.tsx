import { useEffect, useRef } from "react";
import mountScrollWorld from "../vendor/scrubEngine";

const BASE = import.meta.env.BASE_URL;
const S = `${BASE}scroll/`;
const FONT = "'Open Sauce One', -apple-system, BlinkMacSystemFont, sans-serif";

export default function ScrollWorldHero({ onBook }: { onBook: () => void }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const mounted = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || mounted.current) return;
    mounted.current = true;

    mountScrollWorld(el, {
      brand: null,
      hint: "гортайте",
      diveScroll: 0.85,
      nav: false,
      // розовый градиент и летающие точки движка чужие белому сайту и
      // анимируются непрерывно, забирая кадры
      atmosphere: false,
      sections: [
        {
          id: "vhid",
          label: "Клініка",
          still: `${S}vhid.jpg`,
          clip: `${S}vid/vhid.mp4`,
          clipMobile: `${S}vid/vhid-m.mp4`,
          accent: "#C80000",
          eyebrow: "Сімейна стоматологія на Троєщині",
          title: "Comfort Dental",
          body: "Консультація безкоштовна. Щодня 9:00-20:00.",
          tags: ["пр. Червоної Калини, 67"],
        },
        {
          id: "kabinet",
          label: "Обладнання",
          still: `${S}kabinet.jpg`,
          clip: `${S}vid/kabinet.mp4`,
          clipMobile: `${S}vid/kabinet-m.mp4`,
          accent: "#C80000",
          eyebrow: "Сучасне обладнання",
          title: "КТ і мікроскоп",
          body: "Канали лікуємо під мікроскопом. Прицільний знімок постійним пацієнтам безкоштовно.",
          tags: ["Гарантія 6-12 місяців"],
        },
        {
          id: "vinir",
          label: "Вініри",
          still: `${S}vinir.jpg`,
          clip: `${S}vid/vinir.mp4`,
          clipMobile: `${S}vid/vinir-m.mp4`,
          accent: "#C80000",
          eyebrow: "Цифрова стоматологія",
          title: "Вініри фрезеруємо самі",
          body: "Власна фрезерувальна установка. Коронки і вініри без очікування тижнями.",
          tags: ["Кераміка", "Wax Up"],
          scroll: 0.75,
        },
        {
          id: "finale",
          label: "Акція",
          still: `${S}result.jpg`,
          clip: `${S}vid/result.mp4`,
          clipMobile: `${S}vid/result-m.mp4`,
          accent: "#C80000",
          eyebrow: "Акція",
          title: "Лінія посмішки",
          body: "10 вінірів, 80 000 грн. Знижка 18 350 грн.",
          tags: ["6 вінірів, знижка 8 950", "20 вінірів, знижка 34 350"],
          scroll: 1.15,
          cta: {
            primary: { label: "Подзвонити: (067) 604 17 13", href: "tel:+380676041713" },
            secondary: { label: "Дивитись прайс", href: "#/prajs" },
          },
        },
      ],
      connectors: [null, null, null],
    });
  }, []);

  // Слушатели отдельным эффектом, без защиты mounted: иначе перерисовка сайта
  // снимает их навсегда.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Геометрию меряем один раз: getBoundingClientRect на каждом тике скролла
    // заставляет пересчитывать layout и даёт рывки поверх перемотки видео.
    let top = 0;
    let height = 0;
    const measure = () => {
      const r = el.getBoundingClientRect();
      top = r.top + window.scrollY;
      height = el.offsetHeight;
    };
    measure();

    let last = -1;
    let ticking = false;
    const apply = () => {
      ticking = false;
      const left = top + height - window.scrollY - window.innerHeight;
      const tail = window.innerHeight * 0.4;
      const p = left > 0 ? 0 : Math.min(1, -left / tail);
      if (Math.abs(p - last) < 0.01) return;
      last = p;
      el.style.opacity = p ? String(1 - p) : "";
      el.style.visibility = p >= 1 ? "hidden" : "visible";
      el.style.pointerEvents = p > 0.5 ? "none" : "";
      document.body.classList.toggle("hero-flight", p < 1);
    };
    const onScroll = () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(apply);
    };
    const onResize = () => {
      measure();
      last = -1;
      onScroll();
    };
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement)?.closest?.('a[href="#book"]');
      if (a) {
        e.preventDefault();
        onBook();
      }
    };

    document.body.classList.add("hero-flight");
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    el.addEventListener("click", onClick);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      el.removeEventListener("click", onClick);
      document.body.classList.remove("hero-flight");
    };
  }, [onBook]);

  return (
    <>
      {/* Движок держит стили в @layer sw, а обычный CSS сайта этот слой
          перебивает. Здесь возвращаем типографику сайта. */}
      <style>{`
        .sw-root .sw-btn--primary { background:#111111; color:#FFFFFF; font-weight:600; }
        .sw-root .sw-btn--ghost { color:#111111; font-weight:600; }
        /* у движка блок текста всего 460px, из-за этого заголовок ломался
           на три строки. Расширяем под крупный двухстрочный, как на сайте */
        .sw-root .sw-copy { width:min(62vw,780px); max-width:780px; }
        .sw-root .sw-copy__title {
          font-family:${FONT}; font-weight:700; color:#111111;
          letter-spacing:-0.025em; line-height:0.93; text-transform:none;
          font-size:clamp(2.8rem,6.2vw,5.6rem); max-width:none;
          margin:14px 0 14px;
        }
        .sw-root .sw-copy__eyebrow {
          font-family:${FONT}; font-weight:600; font-size:.8rem;
          letter-spacing:normal; text-transform:none; color:#111111;
          display:inline-block; background:rgba(255,255,255,.72);
          backdrop-filter:blur(6px); border-radius:9999px; padding:6px 14px;
        }
        .sw-root .sw-copy__body {
          font-family:${FONT}; font-weight:500; font-size:.95rem;
          color:rgba(17,17,17,.72); max-width:28rem;
        }
        .sw-root .sw-copy__tags li {
          font-family:${FONT}; font-weight:600; color:#111111;
          background:rgba(255,255,255,.72); border-radius:9999px;
        }
        /* Tailwind у сайта ставит video/img height:auto, и это перебивает
           правило движка object-fit:cover, потому что его стили в @layer sw.
           Из-за этого на узком экране видео занимало четверть высоты. */
        .sw-root .sw-scene video,
        .sw-root .sw-scene img {
          width:100%; height:100%; max-width:none; object-fit:cover; display:block;
        }
        .sw-root .sw-particles { display:none; }
        /* у сайта внизу свои плавающие кнопки, освобождаем под них место */
        .sw-root .sw-copy { padding-bottom:88px; }
        .sw-root .sw-copy__num,
        .sw-root .sw-route__label,
        .sw-root .sw-hint { font-family:${FONT}; }

        /* пока идёт полёт, шапка сайта не съедает кадр: она прозрачная,
           а читаемость даёт мягкая подложка сверху, а не обводка у букв */
        body.hero-flight header {
          background:transparent !important; backdrop-filter:none !important;
          transition:background .25s ease, backdrop-filter .25s ease;
        }
        body.hero-flight header::before {
          content:""; position:absolute; inset:0; z-index:-1; pointer-events:none;
          background:linear-gradient(to bottom, rgba(255,255,255,.92) 0%, rgba(255,255,255,.75) 55%, rgba(255,255,255,0) 100%);
        }
        body.hero-flight header:hover {
          background:rgba(255,255,255,.94) !important; backdrop-filter:blur(8px) !important;
        }
        body.hero-flight header:hover::before { opacity:0; }
        /* телефон в шапке не должен ломаться на две строки */
        header a, header nav a { white-space:nowrap; }
      `}</style>
      <div
        ref={ref}
        className="sw-root"
        style={
          {
            position: "relative",
            zIndex: 40,
            background: "#FFFFFF",
            // движок резервирует на экран больше, чем длится полёт: подтягиваем
            // следующую секцию сайта вплотную к финалу
            marginBottom: "-60vh",
            "--sw-bg": "#FFFFFF",
            "--sw-ink": "#111111",
            "--sw-ink-soft": "#5b5b5b",
            "--sw-accent": "#C80000",
            "--sw-font-display": FONT,
            "--sw-font-body": FONT,
          } as React.CSSProperties
        }
      />
    </>
  );
}
