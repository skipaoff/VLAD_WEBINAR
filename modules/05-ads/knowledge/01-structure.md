# Из чего состоит реклама

```
Кабинет
└── Кампания        цель и общий бюджет
    └── Группа      кому показываем: гео, возраст, интересы, плейсменты
        └── Объявление   картинка и текст
```

Одна кампания, одна-две группы, по объявлению на каждый креатив. Больше на старте не нужно:
бюджет размажется и ни одна группа не выйдет из обучения.

## Какую цель выбирать

| Что есть у бизнеса | Цель | На что оптимизируем |
|---|---|---|
| только сайт, пикселя нет | `OUTCOME_TRAFFIC` | `LINK_CLICKS` |
| пиксель стоит и ловит события | `OUTCOME_LEADS` | `OFFSITE_CONVERSIONS` по событию Lead |
| нужны заявки прямо в Facebook | `OUTCOME_LEADS` + лид-форма | `LEAD_GENERATION` |
| ведём в мессенджер | `OUTCOME_LEADS` + Click to Message | `CONVERSATIONS` |

Правило простое: **без пикселя на конверсии не оптимизируем**. Facebook нечему учиться, группа
не выйдет из обучения и открутит бюджет в пустоту. Нет пикселя — берём трафик и честно об этом
говорим.

## Порядок вызовов

```python
campaign = create_campaign(
    account_id=ACT, name=..., objective="OUTCOME_TRAFFIC",
    status="PAUSED", use_adset_level_budgets=True)

adset = create_adset(
    account_id=ACT, campaign_id=campaign["id"], name=...,
    optimization_goal="LINK_CLICKS", billing_event="IMPRESSIONS",
    daily_budget=2000,          # в центах: 2000 = $20
    targeting={...}, status="PAUSED")

image = upload_ad_image(account_id=ACT, image_url=<ссылка на креатив>)

creative = create_ad_creative(
    account_id=ACT, image_hash=image["hash"], page_id=PAGE,
    message=<основной текст>, headline=<заголовок>, description=<описание>,
    call_to_action_type="LEARN_MORE", link_url=SITE, name=...)

ad = create_ad(account_id=ACT, adset_id=adset["id"],
               creative_id=creative["id"], name=..., status="PAUSED")
```

Бюджет везде в центах. `$20` — это `2000`. Ошибка здесь стоит дороже всего.

## Плейсменты и формат картинки

Креативы из базы сделаны в 9:16 — это родной формат Stories и Reels. В ленте такая
картинка обрежется по бокам и текст уедет.

- только 9:16 на руках → ставь плейсменты `instagram_stories`, `facebook_story`, `instagram_reels`;
- нужна ещё лента → попроси человека догенерить те же посты в 4:5 и добавь их отдельными
  объявлениями, а не растягивай существующие.

Advantage+ Placements включать можно только когда есть оба формата: иначе Facebook сам
поставит вертикалку в ленту и обрежет.
