---
name: fb-api
description: Все вызовы Facebook Marketing API напрямую по ключам, без MCP — проверка доступа, поиск города и интересов, оценка охвата, загрузка видео, создание кампании, группы, креатива, объявления и включение. Использовать на любом этапе, где агент рекламы ходит в кабинет.
---

# Как ходить в Facebook

MCP-сервера нет. Агент дёргает Graph API напрямую — обычными запросами с токеном.
Всё, что ниже, работает через `curl` или `requests`; примеры даны на curl.

## Основа

```bash
# ключи: .env агента главнее общего .env репозитория, тот главнее ~/.config/vlad-webinar/.env
for f in "$HOME/.config/vlad-webinar/.env" ../../.env .env; do
  [ -f "$f" ] && { set -a; . "$f"; set +a; }
done
BASE="https://graph.facebook.com/${META_API_VERSION:-v23.0}"
```

## Подпись appsecret_proof

Приложение с включённой проверкой отклоняет запросы без подписи. Считается один раз
и добавляется ко всем вызовам.

```bash
PROOF=$(printf "%s" "$META_ACCESS_TOKEN" \
  | openssl dgst -sha256 -hmac "$META_APP_SECRET" | sed 's/^.* //')
```

Дальше в каждый запрос идут два параметра: `access_token` и `appsecret_proof`.
Если приложение проверку не требует, лишняя подпись не мешает — добавляй всегда.

## Проверка доступа перед работой

```bash
# что за токен, когда протухает, от какого приложения
curl -s "$BASE/debug_token?input_token=$META_ACCESS_TOKEN\
&access_token=$META_APP_ID|$META_APP_SECRET"

# какие права выданы — нужны ads_management и ads_read
curl -s "$BASE/me/permissions?access_token=$META_ACCESS_TOKEN&appsecret_proof=$PROOF"

# виден ли кабинет и в какой он валюте
curl -s "$BASE/me/adaccounts?fields=account_id,name,currency,timezone_name,account_status\
&access_token=$META_ACCESS_TOKEN&appsecret_proof=$PROOF"
```

`account_status` должен быть `1` — активен. Двойка означает, что кабинет отключён,
и создать в нём ничего не выйдет.

## Страница и Instagram

```bash
curl -s "$BASE/me/accounts?fields=id,name,instagram_business_account\
&access_token=$META_ACCESS_TOKEN&appsecret_proof=$PROOF"
```

Страница обязана быть привязана к кабинету — без неё объявление не создастся.

## Поиск города

```bash
curl -s -G "$BASE/search" \
  --data-urlencode "type=adgeolocation" \
  --data-urlencode "location_types=[\"city\"]" \
  --data-urlencode "q=Kyiv" \
  --data-urlencode "access_token=$META_ACCESS_TOKEN" \
  --data-urlencode "appsecret_proof=$PROOF"
```

Из ответа нужен `key`. Наугад его не подставляй: неверный ключ либо отвалится ошибкой,
либо покажет рекламу в другом городе, и это заметят не сразу.

## Поиск интересов

```bash
curl -s -G "$BASE/search" \
  --data-urlencode "type=adinterest" \
  --data-urlencode "q=dentistry" \
  --data-urlencode "limit=25" \
  --data-urlencode "access_token=$META_ACCESS_TOKEN" \
  --data-urlencode "appsecret_proof=$PROOF"
```

В ответе `id`, `name` и границы размера аудитории. Смотри на размер — см. `03-targeting.md`.

## Оценка охвата

```bash
curl -s -G "$BASE/$META_AD_ACCOUNT_ID/delivery_estimate" \
  --data-urlencode "optimization_goal=LINK_CLICKS" \
  --data-urlencode "targeting_spec=$TARGETING_JSON" \
  --data-urlencode "access_token=$META_ACCESS_TOKEN" \
  --data-urlencode "appsecret_proof=$PROOF"
```

Нужна, чтобы показать человеку цифру охвата до запуска.

## Загрузка картинки

Скачай креатив локально и загрузи файлом:

```bash
curl -s -X POST "$BASE/$META_AD_ACCOUNT_ID/adimages" \
  -F "filename=@creatives/01-smile-contagious.png" \
  -F "access_token=$META_ACCESS_TOKEN" \
  -F "appsecret_proof=$PROOF"
```

В ответе `images.<имя файла>.hash` — этот хеш пойдёт в креатив.

## Создание кампании

```bash
curl -s -X POST "$BASE/$META_AD_ACCOUNT_ID/campaigns" \
  -F "name=Comfort_TRAFFIC_2026-08" \
  -F "objective=OUTCOME_TRAFFIC" \
  -F "status=PAUSED" \
  -F "special_ad_categories=[]" \
  -F "access_token=$META_ACCESS_TOKEN" -F "appsecret_proof=$PROOF"
```

`special_ad_categories` обязателен даже пустой. Без него запрос падает — это самая частая
ошибка на первом вызове. Стоматология, салон, детейлинг в спецкатегории не входят, так что
пустой список верный.

## Создание группы

```bash
curl -s -X POST "$BASE/$META_AD_ACCOUNT_ID/adsets" \
  -F "name=Interests_25-55_Kyiv15km_Stories" \
  -F "campaign_id=$CAMPAIGN_ID" \
  -F "daily_budget=2000" \
  -F "billing_event=IMPRESSIONS" \
  -F "optimization_goal=LINK_CLICKS" \
  -F "bid_strategy=LOWEST_COST_WITHOUT_CAP" \
  -F "targeting=$TARGETING_JSON" \
  -F "status=PAUSED" \
  -F "access_token=$META_ACCESS_TOKEN" -F "appsecret_proof=$PROOF"
```

`daily_budget` — в мелких единицах валюты кабинета. `2000` это 20 долларов или 20 гривен,
смотря какая валюта. Перепроверь порядок: лишний ноль здесь стоит дороже всего.

## Создание креатива

```bash
STORY_SPEC='{
  "page_id": "PAGE_ID",
  "link_data": {
    "image_hash": "HASH",
    "link": "https://site",
    "message": "основной текст",
    "name": "заголовок",
    "description": "описание",
    "call_to_action": {"type": "LEARN_MORE", "value": {"link": "https://site"}}
  }
}'

curl -s -X POST "$BASE/$META_AD_ACCOUNT_ID/adcreatives" \
  -F "name=01-smile-contagious_v1" \
  -F "object_story_spec=$STORY_SPEC" \
  -F "access_token=$META_ACCESS_TOKEN" -F "appsecret_proof=$PROOF"
```

Если есть Instagram — добавь в `object_story_spec` поле `instagram_actor_id`.

## Создание объявления

```bash
curl -s -X POST "$BASE/$META_AD_ACCOUNT_ID/ads" \
  -F "name=01-smile-contagious_v1" \
  -F "adset_id=$ADSET_ID" \
  -F "creative={\"creative_id\":\"$CREATIVE_ID\"}" \
  -F "status=PAUSED" \
  -F "access_token=$META_ACCESS_TOKEN" -F "appsecret_proof=$PROOF"
```

## Запуск

Три уровня, и каждый включается отдельно. Включить только кампанию мало — если группа
или объявление остались на паузе, показов не будет.

```bash
for ID in "$AD_ID" "$ADSET_ID" "$CAMPAIGN_ID"; do
  curl -s -X POST "$BASE/$ID" -F "status=ACTIVE" \
    -F "access_token=$META_ACCESS_TOKEN" -F "appsecret_proof=$PROOF"
done
```

Порядок снизу вверх: объявление, группа, кампания.

## Ссылка на кампанию в кабинете

```
https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=<без act_>&selected_campaign_ids=<id>
```

## Видео-креатив

Картинку грузят в `adimages`, видео — в `advideos`. Дальше видео нужно дождаться:
Facebook его перекодирует, и пока статус не `ready`, креатив из него не соберётся.

```bash
# загрузка
curl -s -X POST "$BASE/$META_AD_ACCOUNT_ID/advideos" \
  -F "source=@kreativ/video.mp4" \
  -F "name=01-video_v1" \
  -F "access_token=$META_ACCESS_TOKEN" -F "appsecret_proof=$PROOF"
# → {"id": "VIDEO_ID"}

# ждём обработку: повторять раз в 10 секунд, пока video_status не станет ready
curl -s "$BASE/$VIDEO_ID?fields=status&access_token=$META_ACCESS_TOKEN&appsecret_proof=$PROOF"

# обложка: Facebook предлагает свои, берём ту, где is_preferred
curl -s "$BASE/$VIDEO_ID/thumbnails?access_token=$META_ACCESS_TOKEN&appsecret_proof=$PROOF"
```

Креатив из видео собирается через `video_data`, а не `link_data`. Обложка обязательна —
без `image_url` Facebook креатив не примет.

```bash
STORY_SPEC='{
  "page_id": "PAGE_ID",
  "video_data": {
    "video_id": "VIDEO_ID",
    "image_url": "URL_ОБЛОЖКИ",
    "message": "основной текст",
    "title": "заголовок",
    "link_description": "описание",
    "call_to_action": {"type": "LEARN_MORE", "value": {"link": "https://site"}}
  }
}'
```

В `video_data` заголовок называется `title`, а описание — `link_description`. Это не опечатка:
у картинок те же поля называются `name` и `description`.

Формат видео узнаётся до загрузки:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration \
  -of csv=p=0 kreativ/video.mp4
```

От соотношения сторон зависит, где показывать, — таблица в конце этого файла.

## Инструменты MCP → вызовы API

Скиллы `campaign-manager`, `targeting-expert`, `creative-analyzer` и `account-onboarding`
записывают вызовы Facebook как инструменты MCP. MCP-сервера здесь нет — каждый вызов делается
напрямую, по этой таблице. Параметры переносятся как есть, меняется только транспорт.

| В скилле | Прямой вызов |
|---|---|
| `get_ad_accounts()` | `GET /me/adaccounts` |
| `get_account_pages(account_id)` | `GET /me/accounts` |
| `search_geo_locations(query, location_types)` | `GET /search?type=adgeolocation` |
| `search_interests(query, limit)` | `GET /search?type=adinterest` |
| `get_interest_suggestions(interest_list)` | `GET /search?type=adinterestsuggestion` |
| `search_demographics()` | `GET /search?type=adTargetingCategory&class=demographics` |
| `estimate_audience_size(...)` | `GET /act_X/delivery_estimate` |
| `create_campaign(...)` | `POST /act_X/campaigns` |
| `create_adset(...)` | `POST /act_X/adsets` |
| `upload_ad_image(...)` | `POST /act_X/adimages` |
| `upload_video(...)` | `POST /act_X/advideos` |
| `get_video_status(video_id)` | `GET /{video_id}?fields=status` |
| `create_ad_creative(...)` | `POST /act_X/adcreatives` |
| `create_ad(...)` | `POST /act_X/ads` |
| `resume_ad` / `resume_adset` / `resume_campaign` | `POST /{id}` с `status=ACTIVE` |
| `get_campaigns()` / `get_ads()` | `GET /act_X/campaigns`, `GET /act_X/ads` |

Каждый вызов — с `access_token` и `appsecret_proof`, как в начале этого файла.

Вызовы из скиллов, которые до запуска не нужны: `get_insights` — метрик у новой кампании
ещё нет; `create_lookalike_audience` — нет исходной аудитории. Их не делаешь.

## Где показывать — по формату видео

| Видео | `facebook_positions` | `instagram_positions` |
|---|---|---|
| 9:16, вертикальное | `story`, `facebook_reels` | `story`, `reels` |
| 4:5 или 1:1 | `feed`, `story` | `stream`, `story` |
| 16:9, горизонтальное | `feed` | `stream` |

Для вертикального — ещё `device_platforms: ["mobile"]`: на компьютере сторис и рилс нет.
