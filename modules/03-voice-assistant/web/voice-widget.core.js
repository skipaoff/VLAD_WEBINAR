// Ядро виджета: кнопка «Позвонить», панель разговора, соединение с LiveKit.
//
// Здесь НЕТ ни одного импорта — это сделано намеренно. Разные сайты берут
// livekit-client по-разному: статика тянет с CDN, сборка берёт из node_modules.
// Ядро получает его параметром и одинаково работает везде.
//
// Использование:
//   import * as livekit from "livekit-client";
//   mountVoiceWidget({ livekit, tokenUrl: "/api/voice-token", title: "…", accent: "#…" });
//
// Возвращает функцию, которая снимает виджет со страницы (нужна React-обёртке).

const DEFAULTS = {
  tokenUrl: "/api/voice-token",
  label: "Позвонить",
  title: "Голосовой помощник",
  accent: "#2563eb",
  notice:
    "Сейчас включится микрофон, и вы поговорите с голосовым помощником. Разговор нужен только для ответа на ваши вопросы.",
};

const STATE_TEXT = {
  idle: "",
  connecting: "Соединяю…",
  live: "Говорите",
  ended: "Разговор завершён",
};

export function mountVoiceWidget(options = {}) {
  const { livekit } = options;
  if (!livekit?.Room) {
    throw new Error("mountVoiceWidget: нужен livekit-client — передай его в options.livekit");
  }
  const cfg = { ...DEFAULTS, ...options };
  const { Room, RoomEvent, Track } = livekit;

  let room = null;

  const root = document.createElement("div");
  root.className = "vw-root";
  root.style.setProperty("--vw-accent", cfg.accent);
  root.innerHTML = `
    <div class="vw-panel" hidden>
      <div class="vw-panel-head">
        <span class="vw-title"></span>
        <button class="vw-close" type="button" aria-label="Закрыть">×</button>
      </div>
      <p class="vw-notice"></p>
      <div class="vw-status"><span class="vw-dot"></span><span class="vw-status-text"></span></div>
      <div class="vw-actions">
        <button class="vw-start" type="button"></button>
        <button class="vw-stop" type="button" hidden>Завершить</button>
      </div>
      <p class="vw-error" hidden></p>
    </div>
    <button class="vw-launcher" type="button">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" aria-hidden="true">
        <path d="M2 12h2M6 8v8M10 4v16M14 7v10M18 10v4M22 12h0"/>
      </svg>
      <span class="vw-launcher-label"></span>
    </button>
  `;
  document.body.appendChild(root);

  const el = {
    panel: root.querySelector(".vw-panel"),
    title: root.querySelector(".vw-title"),
    notice: root.querySelector(".vw-notice"),
    status: root.querySelector(".vw-status"),
    statusText: root.querySelector(".vw-status-text"),
    start: root.querySelector(".vw-start"),
    stop: root.querySelector(".vw-stop"),
    close: root.querySelector(".vw-close"),
    error: root.querySelector(".vw-error"),
    launcher: root.querySelector(".vw-launcher"),
    launcherLabel: root.querySelector(".vw-launcher-label"),
  };

  el.title.textContent = cfg.title;
  el.notice.textContent = cfg.notice;
  el.start.textContent = cfg.label;
  el.launcherLabel.textContent = cfg.label;

  function setState(next, message) {
    el.statusText.textContent = message || STATE_TEXT[next] || "";
    el.status.hidden = next === "idle";
    el.status.dataset.state = next;
    el.start.hidden = next === "connecting" || next === "live";
    el.stop.hidden = next !== "live";
  }

  function showError(text) {
    el.error.textContent = text;
    el.error.hidden = false;
  }

  async function start() {
    el.error.hidden = true;
    setState("connecting");
    try {
      const res = await fetch(cfg.tokenUrl, { method: "POST" });
      if (!res.ok) {
        showError(
          res.status === 429
            ? "Сейчас много звонков, попробуйте через минуту."
            : "Помощник временно недоступен.",
        );
        setState("idle");
        return;
      }
      const { serverUrl, token } = await res.json();

      room = new Room();
      // Голос помощника приходит отдельным треком — включаем его в скрытом <audio>.
      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) {
          const audio = track.attach();
          audio.style.display = "none";
          root.appendChild(audio);
        }
      });
      room.on(RoomEvent.Disconnected, () => setState("ended"));

      await room.connect(serverUrl, token);
      await room.localParticipant.setMicrophoneEnabled(true);
      setState("live");
    } catch {
      showError("Не получилось включить микрофон. Разрешите доступ и попробуйте снова.");
      setState("idle");
    }
  }

  function stop() {
    room?.disconnect();
    room = null;
    setState("ended");
  }

  const onPageHide = () => room?.disconnect();

  el.launcher.addEventListener("click", () => {
    el.panel.hidden = false;
    el.launcher.hidden = true;
    el.error.hidden = true;
    setState("idle");
  });
  el.close.addEventListener("click", () => {
    stop();
    el.panel.hidden = true;
    el.launcher.hidden = false;
  });
  el.start.addEventListener("click", start);
  el.stop.addEventListener("click", stop);
  window.addEventListener("pagehide", onPageHide);

  setState("idle");

  return function unmount() {
    window.removeEventListener("pagehide", onPageHide);
    room?.disconnect();
    room = null;
    root.remove();
  };
}

/** Читает настройки из data-атрибутов тега <script data-voice-widget …>. */
export function configFromScriptTag() {
  const tag = document.querySelector("script[data-voice-widget]");
  if (!tag) return {};
  const d = tag.dataset;
  return {
    tokenUrl: d.tokenUrl,
    label: d.label,
    title: d.title,
    accent: d.accent,
    notice: d.notice,
  };
}
