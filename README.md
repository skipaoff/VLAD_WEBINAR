# Бизнес под ключ

Четыре шага, за которые клиенту собирается работающий бизнес: сайт, продавец с
видеоконсультантом, рекламный ролик и запущенная реклама. Управление — обычным текстом
в Claude Code: ставишь скилл один раз и дальше просто говоришь, что нужно.

## Поставить скилл

```
mkdir -p ~/.claude/skills && curl -sL https://github.com/skipaoff/VLAD_WEBINAR/archive/refs/heads/main.tar.gz | tar -xz --strip-components=2 -C ~/.claude/skills VLAD_WEBINAR-main/skill
```

Новая сессия Claude Code подхватит его сама. Дальше пишешь человеческим текстом:

```
вот инфа про бизнес, сделай сайт
сделай продавца и видеоконсультанта
сделай видео
запускай рекламу
```

Скилл лежит в [skill/biznes-pod-klyuch](skill/biznes-pod-klyuch/), снести — `rm -rf ~/.claude/skills/biznes-pod-klyuch`.

## Четыре шага

На каждом шаге открывается экран работы: слева шаги, справа макет, внизу агенты. Экран
идёт сам 4–6 минут, в конце появляется кнопка с результатом. Для репетиции добавь к
адресу `?t=200` — откроется на нужной секунде.

| # | Шаг | Длительность | Экран работы | Что в конце |
|---|---|---|---|---|
| 1 | Сайт | 7:28 | [экран](https://skipaoff.github.io/VLAD_WEBINAR/modules/01-sajt/agent/) | [Сайт клиники](https://comfort-stom-1.vercel.app/) |
| 2 | Продавец и видеоконсультант | 5:44 | [экран](https://skipaoff.github.io/VLAD_WEBINAR/modules/02-prodavec/agent/) | [Тот же сайт, но с кнопкой звонка и Telegram](https://comfort-stom-2.vercel.app/) |
| 3 | Ролик | 4:36 | [экран](https://skipaoff.github.io/VLAD_WEBINAR/modules/03-video/agent/) | [Готовый ролик](https://skipaoff.github.io/VLAD_WEBINAR/modules/03-video/rolik/) |
| 4 | Реклама | 3:42 | [экран](https://skipaoff.github.io/VLAD_WEBINAR/modules/04-reklama/agent/) | [Объявление](https://skipaoff.github.io/VLAD_WEBINAR/modules/04-reklama/obyavlenie/) |

Шаги связаны: сайт со второго шага — тот же самый, что собрали на первом, только к нему
добавились звонок и Telegram. Ролик с третьего шага уходит в рекламу на четвёртом.

## Что внутри модулей

| Модуль | Что там лежит |
|---|---|
| [01-sajt](modules/01-sajt/) | сборщик сайта: шаблон, шаги сборки, запасной путь |
| [02-prodavec](modules/02-prodavec/) | [видеоконсультант](modules/02-prodavec/videokonsultant/) и [продавец в Telegram](modules/02-prodavec/telegram/) |
| [03-video](modules/03-video/) | библиотека промптов под ролики и [сам ролик](modules/03-video/rolik/) |
| [04-reklama](modules/04-reklama/) | агент рекламы: знания, скиллы, вызовы API, [объявление](modules/04-reklama/obyavlenie/) |

Код ничего не знает о бизнесе. Знание живёт в отдельных файлах, и поменять бизнес значит
поменять файлы, а не код. Ключей в репозитории нет — они лежат в `.env` на машине.

Всё собрано под стоматологию Comfort на Троєщині (Київ, пр. Червоної Калини 67).

## Архив

То, что делали раньше и оставили, но в четыре шага не вошло:

- [Поиск клиентов](https://skipaoff.github.io/VLAD_WEBINAR/modules/arhiv/poisk-klientov/agent/) — 16 стоматологий Киева с проверенным Телеграмом
- [Отдельные экраны](modules/arhiv/ekrany/) видеоконсультанта и продавца, пока они были двумя шагами
- [Консьерж](modules/arhiv/konsierzh/) — рассылка по найденным клиентам
