# Три ключа — где взять

Готовится один раз, до эфира. Если не успели — агент попросит их сам, первым сообщением.

## 1. ID рекламного кабинета

Ads Manager → Настройки аккаунта. Или прямо в адресной строке после `act=`.
Записывается с префиксом: `act_123456789`.

## 2. Access Token

На developers.facebook.com создать приложение типа Business, добавить продукт Marketing API.
Затем Marketing API → Tools: выбрать кабинет и отметить права

```
ads_management
ads_read
pages_show_list
pages_read_engagement
```

Сгенерировать токен. Обычный живёт около 60 дней — для эфира этого хватит. Для постоянной
работы нужен System User в Business Manager: его токен не протухает.

## 3. App Secret

Там же: Settings → Basic → App Secret.

Он нужен, чтобы считать `appsecret_proof` — подпись запроса. Если у приложения включена
проверка, без подписи Facebook отклонит любой вызов.

## Куда положить

```bash
cd modules/05-ads
cp .env.example .env
```

Вписать значения. `.env` в git не попадает.

## Проверка живости

```bash
source .env
PROOF=$(printf "%s" "$META_ACCESS_TOKEN" | openssl dgst -sha256 -hmac "$META_APP_SECRET" | sed 's/^.* //')
curl -s "https://graph.facebook.com/$META_API_VERSION/me/adaccounts?fields=account_id,name,currency,account_status&access_token=$META_ACCESS_TOKEN&appsecret_proof=$PROOF"
```

Вернулся список кабинетов и `account_status: 1` — контур готов.
Ошибка про права — у токена нет `ads_management`.

## Что ещё должно быть в кабинете

- страница Facebook привязана — иначе объявление не создастся;
- добавлен способ оплаты — иначе кампания не запустится;
- у пользователя, чьим токеном работаем, есть доступ к кабинету в Business Manager.
