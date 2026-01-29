# tg_user_clicker

Минимальный пользовательский клиент Telegram MTProto на базе Telethon.

## Настройка

1. Скопируйте `.env.example` в `.env` и заполните данные:
   - `TG_API_ID`
   - `TG_API_HASH`
   - `TG_PHONE`
   - `TG_2FA_PASSWORD` (необязательно)
   - `SESSION_NAME` (по умолчанию `user`)
   - `BOT_USERNAME` (необязательно для `press`, обязательно если не передаётся `--chat`)
   - `BUTTON_NEXT_TEXT`
   - `BUTTON_SERIES_TEXT`
   - `BUTTON_QUALITY_TEXT`
   - `BUTTON_BACK_TEXT`
   - `SEARCH_RESULTS_TIMEOUT_SECONDS`
   - `AFTER_PICK_TIMEOUT_SECONDS`
   - `SEARCH_SEND_PREFIX`
   - `STATE_PATH`
   - `TITLES_PATH`
   - `SENT_DEDUP_LIMIT`

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

## Использование

Авторизуйтесь и создайте файл сессии:

```bash
python -m app.cli login
```

Проверьте пользователя текущей сессии:

```bash
python -m app.cli me
```

Нажмите кнопку «Вперёд» из последних сообщений:

```bash
python -m app.cli press --contains "Вперёд"
```

Найдите тайтл и выберите первый результат:

```bash
python -m app.cli search --chat @BOT --title "Название"
```

Инлайн-поиск тайтла и выбор первого результата:

```bash
python -m app.cli search --chat @fvid_heb_bot --title "время приключений" --inline
```

Обработайте список тайтлов с поддержкой продолжения:

```bash
python -m app.cli run-list --chat @BOT --titles-file ./titles.txt
```

Пример `titles.txt`:

```text
# Строки, начинающиеся с #, игнорируются
Название 1
Название 2

Название 3
```

Запуск одного тайтла с сохранением состояния:

```bash
python -m app.cli run-one --chat @BOT --title "Название"
```

Инлайн-поиск серии и пересылка эпизодов:

```bash
python -m app.cli series --chat @fvid_heb_bot --title "декстер" --inline
```

Проверка статуса продолжения:

```bash
python -m app.cli status
```

Сброс состояния продолжения (нужно подтверждение):

```bash
python -m app.cli reset --yes
```

## Веб-интерфейс

Установите зависимости (FastAPI + Uvicorn уже включены в `requirements.txt`), затем запустите:

```bash
uvicorn app.web.server:app --host 127.0.0.1 --port 8080
```

Откройте <http://127.0.0.1:8080> в браузере, чтобы:

- запускать `run-one` и `run-list`,
- смотреть статус `state.json`,
- останавливать/сбрасывать раннер,
- читать логи.

### API endpoints

- `GET /api/status` — state.json + статус раннера.
- `POST /api/run/one` — `{ "title": str, "bot_username"?: str, "inline"?: bool }`.
- `POST /api/run/list` — `{ "titles": [str] | null, "titles_file"?: str | null, "bot_username"?: str, "inline"?: bool }`.
- `POST /api/stop` — мягкая остановка.
- `POST /api/reset` — сброс state.json.
- `GET /api/logs?tail=200` — последние строки логов.

Поведение при продолжении:

- Прогресс хранится в `state.json` (путь настраивается через `STATE_PATH`).
- При перезапуске `run-list` продолжает с `current_index` и пропускает media ID, уже находящиеся в `sent_ids`.
- Для каждого тайтла хранится ID последнего медиа-сообщения, чтобы продолжать сериалы без дублей.

Файл сессии сохраняется автоматически и используется при следующих запусках, поэтому код подтверждения вводить повторно не нужно.
