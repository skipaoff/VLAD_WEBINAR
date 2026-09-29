# React, Vite или Remix

1. Скопируйте `web/react/TavusWidget.tsx` в папку компонентов сайта.
2. Добавьте компонент в layout или корневую страницу:

```tsx
<TavusWidget
  deploymentId={import.meta.env.VITE_TAVUS_DEPLOYMENT_ID}
  greeting="Здравствуйте! Чем могу помочь?"
  context={`Текущая страница: ${window.location.pathname}`}
/>
```

3. Задайте `VITE_TAVUS_DEPLOYMENT_ID`. Deployment ID можно показывать в браузере; API-ключ нельзя.
4. Добавьте домен сайта в `allowed_origins` Deployment.

