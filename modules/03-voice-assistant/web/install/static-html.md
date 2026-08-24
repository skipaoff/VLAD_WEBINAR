# Статика: обычный HTML или Astro

Сборки нет, файлы кладутся как есть.

## 1. Файлы

Скопируй в публичную папку сайта (`/` для чистого HTML, `public/` для Astro):

```
voice-widget.core.js
voice-widget.cdn.js
voice-widget.css
```

Оба `.js` должны лежать рядом: `voice-widget.cdn.js` импортирует ядро по относительному пути.

## 2. Эндпоинт токена

`token/vercel-node.js` → `api/voice-token.js` в корне проекта. Vercel поднимет его сам,
даже если весь остальной сайт — статика.

Если сайта ещё нет в проекте с `package.json`, создай его:

```json
{
  "private": true,
  "dependencies": { "livekit-server-sdk": "^2.9.0" }
}
```

## 3. Подключение

В конец `<body>` каждой страницы, где нужна кнопка:

```html
<link rel="stylesheet" href="/voice-widget.css">
<script type="module" src="/voice-widget.cdn.js" data-voice-widget
        data-token-url="/api/voice-token"
        data-label="Позвонить"
        data-title="Название бизнеса"
        data-accent="#2563eb"></script>
```

Атрибут `data-voice-widget` обязателен — по нему скрипт находит собственные настройки.
Название и цвет подставь из `brand.json`.

## 4. Переменные окружения проекта

```
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
VOICE_AGENT_NAME
```

`VOICE_AGENT_NAME` = `agent_name` из `worker/config.json`.
