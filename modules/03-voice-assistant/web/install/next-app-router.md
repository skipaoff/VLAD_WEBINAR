# Next.js App Router

Признак: папка `app/` рядом с `next.config.*`.

## 1. Зависимости

```bash
npm i livekit-client livekit-server-sdk
```

## 2. Файлы

```
web/react/VoiceWidget.jsx      → components/voice/VoiceWidget.jsx
web/voice-widget.core.js       → components/voice/voice-widget.core.js
web/voice-widget.css           → public/voice-widget.css
web/token/next-app-route.ts    → app/api/voice-token/route.ts
```

Оба файла виджета кладутся в одну папку — обёртка импортирует ядро относительным путём.
Если проект без TypeScript, переименуй `route.ts` в `route.js` и убери из него две строки
с `type VideoGrant` и аннотацией типа у `grant`.

## 3. Подключение

В `app/layout.tsx`, внутри `<body>`:

```tsx
import VoiceWidget from "@/components/voice/VoiceWidget";

// …внутри <body>, последним элементом:
<VoiceWidget title="Название бизнеса" accent="#2563eb" />
```

И туда же, в `<head>` или через `import`, стили:

```tsx
<link rel="stylesheet" href="/voice-widget.css" />
```

Компонент помечен `"use client"` и сам ничего не рисует на сервере: виджет монтируется
в браузере, поэтому гидрация не ломается.

## 4. Переменные окружения

`.env.local` для локальной проверки и переменные проекта на Vercel:

```
LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
VOICE_AGENT_NAME=
```

Без префикса `NEXT_PUBLIC_` — эти значения не должны попасть в браузер.
