// Кнопка «Позвонить» на сайте. Работает на любой странице — статике, Next.js, чём угодно.
//
// Подключение (в конец <body>):
//   <link rel="stylesheet" href="/voice-widget.css">
//   <script type="module" src="/voice-widget.js"
//           data-token-url="/api/voice-token"
//           data-label="Позвонить"
//           data-title="Название бизнеса"
//           data-accent="#2563eb"></script>
//
// Секретов здесь нет: страница просит короткоживущий токен у своего же сервера.

import { Room, RoomEvent, Track } from "https://cdn.jsdelivr.net/npm/livekit-client@2/+esm";

const script = document.currentScript || document.querySelector('script[src*="voice-widget"]');
const cfg = {
  tokenUrl: script?.dataset.tokenUrl || "/api/voice-token",
  label: script?.dataset.label || "Позвонить",
  title: script?.dataset.title || "Голосовой помощник",
  accent: script?.dataset.accent || "#2563eb",
  notice:
    script?.dataset.notice ||
    "Сейчас включится микрофон, и вы поговорите с голосовым помощником. Разговор нужен только для ответа на ваши вопросы.",
};

const STATE_TEXT = {
  idle: "",
  connecting: "Соединяю…",
  live: "Говорите",
  ended: "Разговор завершён",
};

let room = null;
let state = "idle";

// ─── разметка ───────────────────────────────────────────────────────────
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
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
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
  statusText: root.querySelector(".vw-status-text"),
  status: root.querySelector(".vw-status"),
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

// ─── состояние ──────────────────────────────────────────────────────────
function setState(next, message) {
  state = next;
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

function clearError() {
  el.error.hidden = true;
}

// ─── звонок ─────────────────────────────────────────────────────────────
async function start() {
  clearError();
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
  } catch (err) {
    showError("Не получилось включить микрофон. Разрешите доступ и попробуйте снова.");
    setState("idle");
  }
}

function stop() {
  room?.disconnect();
  room = null;
  setState("ended");
}

// ─── события ────────────────────────────────────────────────────────────
el.launcher.addEventListener("click", () => {
  el.panel.hidden = false;
  el.launcher.hidden = true;
  clearError();
  setState("idle");
});
el.close.addEventListener("click", () => {
  stop();
  el.panel.hidden = true;
  el.launcher.hidden = false;
});
el.start.addEventListener("click", start);
el.stop.addEventListener("click", stop);
window.addEventListener("pagehide", () => room?.disconnect());

setState("idle");
