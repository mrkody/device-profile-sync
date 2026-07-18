# Auto-Balancer RU White — live VPN subscription

`docs/build_config.py` скачивает список серверов из [igareck/vpn-configs-for-russia](https://github.com/igareck/vpn-configs-for-russia)
(`Vless-Reality-White-Lists-Rus-Mobile.txt`), убирает дубликаты (по fp=chrome > edge > firefox > ...),
выбрасывает серверы с меткой Russia и собирает два Xray-core JSON-конфига с авто-балансировщиком:

- `docs/Auto-Balancer-RU-White.json` — основной, стратегия `leastLoad` + `burstObservatory`
  (быстрая сходимость: трафик держится на 5 лучших по RTT серверах, а не мечется между всеми).
- `docs/Auto-Balancer-RU-White-leastPing-backup.json` — резервный, стратегия `leastPing` + `observatory`
  (более старая, но гарантированно рабочая в Happ, если `leastLoad` не поддерживается сборкой Xray-core).

## Как это становится "живой" подпиской

`.github/workflows/update-sub.yml` каждые ~20 минут (и по ручному запуску) перезапускает
`docs/build_config.py` и коммитит обновлённые JSON-файлы обратно в репозиторий.
GitHub Pages отдаёт `docs/` как статический сайт, поэтому у файлов появляется
постоянный публичный URL вида:

```
https://<твой-github-username>.github.io/<repo>/Auto-Balancer-RU-White.json
```

Именно этот URL нужно вставить в Happ как ссылку на подписку — при каждом обновлении
подписки в приложении будет подтягиваться свежий список серверов с GitHub.

## Разовая настройка (руками, на github.com)

1. Создать новый репозиторий на GitHub (публичный — приватные репо на GitHub Pages
   для personal-аккаунтов нужен platform GitHub Pro).
2. Запушить содержимое этой папки в `main`.
3. Settings → Pages → Source: **Deploy from a branch**, Branch: `main`, Folder: `/docs`.
4. Settings → Actions → General → Workflow permissions →
   **Read and write permissions** (иначе шаг `git push` в воркфлоу упадёт с ошибкой доступа).
5. Проверить: Actions → "Update VPN subscription" → Run workflow (ручной запуск),
   убедиться, что коммит с обновлённым JSON появился.
6. URL для Happ: `https://<username>.github.io/<repo>/Auto-Balancer-RU-White.json`.

## Важно про приватность

Репозиторий публичный, значит и сгенерированные JSON с UUID/паролями серверов будут
общедоступны по прямой ссылке. Утечки это не создаёт (сами серверы и так публично
раздаются в исходном списке на GitHub), но кто угодно, кто узнает твой URL подписки,
сможет забрать себе те же 26 серверов.

## Локальный запуск без GitHub

```
python3 docs/build_config.py
```

Всегда тянет самую свежую версию списка и перезаписывает оба JSON-файла в `docs/`.
