# Next.js Pages Router

Признак: папка `pages/` рядом с `next.config.*`.

## 1. Зависимости

```bash
npm i livekit-client livekit-server-sdk
```

## 2. Файлы

```
web/react/VoiceWidget.jsx    → components/voice/VoiceWidget.jsx
web/voice-widget.core.js     → components/voice/voice-widget.core.js
web/voice-widget.css         → public/voice-widget.css
web/token/vercel-node.js     → pages/api/voice-token.js
```

Вариант `vercel-node.js` подходит здесь без правок: у Pages Router то же `(req, res)`.

## 3. Подключение

В `pages/_app.jsx`:

```jsx
import dynamic from "next/dynamic";

const VoiceWidget = dynamic(() => import("../components/voice/VoiceWidget"), { ssr: false });

export default function App({ Component, pageProps }) {
  return (
    <>
      <Component {...pageProps} />
      <VoiceWidget title="Название бизнеса" accent="#2563eb" />
    </>
  );
}
```

Стили — в `pages/_document.jsx` в `<Head>`:

```jsx
<link rel="stylesheet" href="/voice-widget.css" />
```

`ssr: false` здесь обязателен: виджет трогает `document` при монтировании.

## 4. Переменные окружения

```
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
VOICE_AGENT_NAME
```
