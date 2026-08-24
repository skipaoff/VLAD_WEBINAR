// React-обёртка для Next.js, Vite, Remix — везде, где есть сборка.
// livekit-client берётся из node_modules, а не с CDN.
//
// Установка:  npm i livekit-client
// Файл и voice-widget.core.js кладутся РЯДОМ, в одну папку (например components/voice/),
// стили — в public/voice-widget.css.
//
// Использование:
//   <VoiceWidget title="Название бизнеса" accent="#2563eb" />
//
// Если проект на TypeScript — файл можно оставить .jsx, Next и Vite его соберут.

"use client";

import { useEffect } from "react";

export default function VoiceWidget({
  tokenUrl = "/api/voice-token",
  label = "Позвонить",
  title = "Голосовой помощник",
  accent = "#2563eb",
  notice,
}) {
  useEffect(() => {
    let unmount;
    let cancelled = false;

    // Динамический импорт: виджет трогает document, поэтому грузится только в браузере.
    (async () => {
      const [livekit, core] = await Promise.all([
        import("livekit-client"),
        import("./voice-widget.core.js"),
      ]);
      if (cancelled) return;
      unmount = core.mountVoiceWidget({ livekit, tokenUrl, label, title, accent, notice });
    })();

    return () => {
      cancelled = true;
      unmount?.();
    };
  }, [tokenUrl, label, title, accent, notice]);

  return null;
}
