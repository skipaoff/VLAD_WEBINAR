# Выбор рецепта установки

| Что находится в проекте сайта | Инструкция |
|---|---|
| Обычный `index.html`, Astro или CMS с HTML-вставкой | [static-html.md](static-html.md) |
| Vite/React/Remix | [react.md](react.md) |
| Next.js с `app/` или `pages/` | [nextjs.md](nextjs.md) |

Приветствие и контекст, которые уходят в кнопку на сайте, пишутся на языке из
`business/brand.json` → `language`: надписи внутри кнопки Tavus уже переведены при setup,
а эти две строки задаёт сайт.

Для managed Deployment серверный endpoint не требуется. В браузере находится только безопасный `deployment-id`; `TAVUS_API_KEY` используется один раз серверным setup-скриптом и остаётся вне сайта.

