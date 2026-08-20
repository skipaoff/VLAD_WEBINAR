# Подготовка контура — до эфира

Делается один раз технической стороной. Ведущему это знать не нужно.

## 1. LiveKit

Завести проект в LiveKit Cloud, забрать `LIVEKIT_URL`, `LIVEKIT_API_KEY`,
`LIVEKIT_API_SECRET`. Под демо лучше отдельный проект: минуты видно отдельно и не жалко.

## 2. Gemini

Получить API-ключ с доступом к Live API. Ключ платный и тратится по минутам разговора,
а не по запросам, — поэтому в конфиге стоит потолок сессии 300 секунд.

## 3. Воркер

```bash
cd modules/04-voice-assistant/worker
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # вписать ключи
.venv/bin/python -m bot start
```

Воркер должен быть уже запущен к моменту, когда ведущий нажимает кнопку на сайте.
Он заходит только в те комнаты, где токен явно просит агента с именем из `config.json`.

Живёт долго — держать под pm2, systemd или чем удобно:

```bash
pm2 start --name voice-worker --interpreter ./.venv/bin/python -- -m bot start
```

## 4. Сайт

- `web/voice-widget.js` и `web/voice-widget.css` — в статику сайта;
- `web/api/voice-token.js` — в папку `api/` проекта сайта;
- `livekit-server-sdk` — в зависимости сайта;
- переменные окружения проекта сайта: `LIVEKIT_URL`, `LIVEKIT_API_KEY`,
  `LIVEKIT_API_SECRET`, `VOICE_AGENT_NAME`.

`VOICE_AGENT_NAME` обязан совпадать с `agent_name` из `worker/config.json` — иначе кнопка
будет бесконечно соединяться: комната создастся, а воркер в неё не придёт.

## 5. Заявки

Всё, что ассистент забрал в разговоре, ложится строкой в `worker/leads.jsonl`:

```bash
tail -f modules/04-voice-assistant/worker/leads.jsonl
```

В эфире это удобный кадр: ведущий диктует телефон голосом, а на экране в реальном времени
появляется заявка.

## Если кнопка бесконечно соединяется

По порядку: воркер запущен? имя агента совпадает? ключи LiveKit у сайта и у воркера от
одного проекта? если токен-роут отдаёт 429 — сработал лимит на IP, поднять `VOICE_RATE_MAX`.
