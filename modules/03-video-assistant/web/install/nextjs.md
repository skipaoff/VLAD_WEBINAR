# Next.js

1. Скопируйте `web/react/TavusWidget.tsx` в `components/TavusWidget.tsx`.
2. Подключите компонент в `app/layout.tsx` или `pages/_app.tsx`:

```tsx
<TavusWidget
  deploymentId={process.env.NEXT_PUBLIC_TAVUS_DEPLOYMENT_ID!}
  greeting="Здравствуйте! Чем могу помочь?"
  context="Цель звонка: проконсультировать посетителя сайта."
/>
```

3. Установите `NEXT_PUBLIC_TAVUS_DEPLOYMENT_ID` на значение Deployment ID.
4. Добавьте production-домен сайта в `allowed_origins` Deployment.

Если пользователь авторизован, можно передать `memoryStore`, собранный из стабильного внутреннего UUID. Не используйте email или телефон в названии store.

