# Статический HTML, Astro или CMS

1. Скопируйте содержимое `web/static-snippet.html` перед закрывающим `</body>`.
2. Замените `YOUR_DEPLOYMENT_ID` на значение из `.tavus/state.json`.
3. Передайте в `conversational-context` текущую страницу и цель звонка.
4. Добавьте production-домен в `allowed_origins` Deployment через PAL Maker.

Не задавайте одинаковый `memory-stores` для всех посетителей. Для анонимного сайта оставьте атрибут пустым. Для авторизованного пользователя формируйте store из внутреннего UUID пользователя и PAL ID.

