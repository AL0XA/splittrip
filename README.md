# 💸 Тусовка & Траты — Telegram Mini App

Мини-приложение для Telegram: создавай события («тусовки»), приглашай друзей,
добавляй общие траты — система сама считает, **кто кому и сколько должен перевести**
(с минимизацией числа переводов). Аналог Splitwise внутри Telegram.

- **Бэкенд:** FastAPI + aiogram, авторизация через Telegram initData
- **Хранилище:** SQLite (без внешних зависимостей), суммы в копейках
- **Фронтенд:** ванильный HTML/CSS/JS + Telegram WebApp SDK

## Как это работает

1. Пользователь создаёт событие → получает инвайт-ссылку `https://t.me/<bot>?startapp=<код>`.
2. Друзья открывают ссылку → автоматически вступают в событие.
3. Любой участник добавляет трату: сумма, за что, кто платил, между кем делить.
4. Сервер считает **чистый баланс** каждого (заплатил − своя доля) и сводит
   должников с кредиторами в минимальное число переводов.

## Структура

```
TG_MiniApp/
├── backend/
│   ├── app/
│   │   ├── main.py       # FastAPI: события, участники, траты
│   │   ├── split.py      # ядро расчёта долгов (балансы + минимизация переводов)
│   │   ├── database.py   # SQLite: users, events, members, expenses, expense_shares
│   │   ├── auth.py       # проверка подписи Telegram initData (HMAC)
│   │   └── config.py     # настройки из .env
│   ├── bot.py            # Telegram-бот с кнопкой запуска Mini App
│   ├── requirements.txt
│   └── .env.example
├── frontend/             # index.html, style.css, app.js (отдаётся сервером)
├── deploy/               # Caddyfile + systemd-юниты + DEPLOY.md (постоянный хостинг)
└── README.md
```

## API

| Метод | Путь | Назначение |
|---|---|---|
| POST | `/api/events` | Создать событие |
| GET | `/api/events` | Список моих событий |
| POST | `/api/events/join` | Вступить по коду (`{code}`) |
| GET | `/api/events/{id}` | Событие: участники, траты, балансы, переводы |
| POST | `/api/events/{id}/expenses` | Добавить трату |
| DELETE | `/api/events/{id}/expenses/{eid}` | Удалить трату (автор или владелец) |

## Быстрый старт (локально)

### 1. Бот
Напиши [@BotFather](https://t.me/BotFather) → `/newbot` → получи `BOT_TOKEN` и username.

### 2. Окружение
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env    # впиши BOT_TOKEN, BOT_USERNAME, WEBAPP_URL
```

### 3. HTTPS-адрес (обязателен для Mini App)
Локально подними туннель и вставь адрес в `WEBAPP_URL`:
```powershell
cloudflared tunnel --url http://localhost:8000
```

### 4. Запуск (два терминала)
```powershell
uvicorn app.main:app --port 8000   # API + фронтенд
python bot.py                      # бот
```

### 5. Настрой инвайт-ссылки (важно для `?startapp=`)
В @BotFather: **Bot Settings → Configure Mini App** (или `/setmenubutton`), указать
`WEBAPP_URL`. Без настроенного Mini App ссылки `https://t.me/<bot>?startapp=<код>`
не будут открывать приложение.

### 6. Пользуйся
Бот → `/start` → «💸 Открыть».

## Постоянный хостинг 24/7

См. подробную инструкцию для VPS + Caddy (авто-HTTPS) в
[deploy/DEPLOY.md](deploy/DEPLOY.md).

## Дорожная карта

- [ ] Неравное деление (доли/проценты, конкретные суммы на человека)
- [ ] Несколько валют и конвертация
- [ ] Отметка «долг погашен» (частичные расчёты)
- [ ] История и экспорт, комментарии к тратам
- [ ] Категории трат и иконки
- [ ] Миграция SQLite → PostgreSQL для продакшена
```
