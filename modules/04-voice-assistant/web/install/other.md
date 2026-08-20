# Другой стек: контракт из двух точек

Если фреймворк не совпал ни с одним рецептом, собери руками — контракт маленький.

## Точка 1. Эндпоинт токена

`POST /api/voice-token` (адрес любой, лишь бы совпадал с `data-token-url`) отвечает:

```json
{ "serverUrl": "wss://…livekit.cloud", "token": "eyJ…", "roomName": "web-abc123" }
```

Что делает эндпоинт:

1. читает `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `VOICE_AGENT_NAME`
   из окружения — на сервере, никогда в браузере;
2. создаёт `AccessToken` на 15 минут с правами `roomJoin`, `canPublish`, `canSubscribe`
   на одну случайную комнату;
3. кладёт в `roomConfig` явный вызов воркера: `agents: [{ agentName }]` — без этого воркер
   в комнату не придёт и кнопка будет висеть на «Соединяю»;
4. ограничивает частоту по IP.

Готовые реализации: `token/vercel-node.js` (Node-хендлер `(req, res)`),
`token/next-app-route.ts` (Web `Request`/`Response`), `token/netlify-function.js`.
Возьми ту, чья сигнатура ближе к твоему хостингу, и поменяй только обёртку.

## Точка 2. Виджет

`voice-widget.core.js` не имеет импортов и экспортирует одну функцию:

```js
import { mountVoiceWidget } from "./voice-widget.core.js";
import * as livekit from "livekit-client";

const unmount = mountVoiceWidget({
  livekit,
  tokenUrl: "/api/voice-token",
  title: "Название бизнеса",
  accent: "#2563eb",
});
```

Вызывать только в браузере: функция сразу дописывает разметку в `document.body`.
Возвращённый `unmount()` снимает виджет и рвёт соединение — нужен там, где компоненты
размонтируются.

Стили `voice-widget.css` подключаются один раз любым способом.
