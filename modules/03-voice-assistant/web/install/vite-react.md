# Vite

Признак: `vite.config.*` в корне.

## 1. Зависимости

```bash
npm i livekit-client
npm i livekit-server-sdk
```

## 2. Файлы

**Если в проекте React:**

```
web/react/VoiceWidget.jsx   → src/components/voice/VoiceWidget.jsx
web/voice-widget.core.js    → src/components/voice/voice-widget.core.js
web/voice-widget.css        → public/voice-widget.css
web/token/vercel-node.js    → api/voice-token.js
```

Подключение в `src/App.jsx`, последним элементом разметки:

```jsx
import VoiceWidget from "./components/voice/VoiceWidget";

<VoiceWidget title="Название бизнеса" accent="#2563eb" />
```

Стили — в `index.html`: `<link rel="stylesheet" href="/voice-widget.css">`.

**Если React в проекте нет** — иди по рецепту [static-html.md](static-html.md): файлы
`voice-widget.core.js`, `voice-widget.cdn.js` и `voice-widget.css` кладутся в `public/`,
а тег `<script type="module" data-voice-widget …>` — в `index.html`.

## 3. Эндпоинт токена

Папка `api/` в корне проекта (не в `src/`) — Vercel поднимет её как serverless-функцию
рядом со статикой, которую собрал Vite. Локально через `vite dev` эта функция работать
не будет: проверять эндпоинт нужно на задеплоенном сайте либо через `vercel dev`.

## 4. Переменные окружения

```
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
VOICE_AGENT_NAME
```

Без префикса `VITE_` — иначе Vite вшьёт секреты в бандл и они уедут в браузер.
