// Точка входа для сайта без сборки: обычный HTML, Astro, любая статика.
// livekit-client берётся с CDN, настройки — из data-атрибутов тега <script>.
//
// Подключение в конец <body>:
//   <link rel="stylesheet" href="/voice-widget.css">
//   <script type="module" src="/voice-widget.cdn.js" data-voice-widget
//           data-token-url="/api/voice-token"
//           data-label="Позвонить"
//           data-title="Название бизнеса"
//           data-accent="#2563eb"></script>
//
// Атрибут data-voice-widget обязателен: в ES-модулях document.currentScript
// всегда null, и тег ищется именно по нему.

import * as livekit from "https://cdn.jsdelivr.net/npm/livekit-client@2/+esm";
import { configFromScriptTag, mountVoiceWidget } from "./voice-widget.core.js";

function clean(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined));
}

mountVoiceWidget({ livekit, ...clean(configFromScriptTag()) });
