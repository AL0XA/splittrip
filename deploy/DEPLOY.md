# 🚀 Деплой на VPS (постоянная работа 24/7)

Инструкция для Ubuntu 22.04/24.04. Итог: мини-апп доступен по своему домену с HTTPS,
сервер и бот автозапускаются и перезапускаются при падении, база сохраняется.

Схема: **Telegram → Caddy (HTTPS, порт 443) → uvicorn (127.0.0.1:8000) + SQLite**,
рядом отдельным процессом крутится бот.

---

## 0. Что понадобится

- VPS с Ubuntu (Timeweb Cloud / Selectel / Hetzner и т.п.), самый дешёвый тариф ок.
- Домен (например, купленный на reg.ru / nic.ru).
- `BOT_TOKEN` от @BotFather.

---

## 1. Домен → IP сервера

В панели, где куплен домен, создай **A-запись**:

```
Тип: A    Имя: @ (или www)    Значение: <публичный IP твоего VPS>
```

Проверить, что записалось (может занять до 10–30 мин):
```bash
nslookup example.com
```

> Дальше в командах меняй `example.com` на свой домен, а пути оставляй как есть.

---

## 2. Подключиться к серверу и обновить систему

```bash
ssh root@<IP-сервера>
apt update && apt upgrade -y
apt install -y python3-venv python3-pip git ufw
```

Открой файрвол (SSH + web):
```bash
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable
```

---

## 3. Отдельный пользователь и код проекта

```bash
# системный пользователь без входа, от которого работают сервисы
adduser --system --group --home /opt/tg_miniapp cookie

# забрать код. Вариант А — через GitHub (рекомендуется):
git clone https://github.com/<твой-логин>/TG_MiniApp.git /opt/tg_miniapp
# Вариант Б — если без GitHub: залей папку проекта через scp/WinSCP в /opt/tg_miniapp
```

> Чтобы использовать GitHub: создай на github.com пустой репозиторий, затем локально на
> Windows выполни `git remote add origin <URL>` и `git push -u origin master`.

---

## 4. Виртуальное окружение и зависимости

```bash
cd /opt/tg_miniapp/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Создай `.env` (тот же формат, что локально, но **WEBAPP_URL теперь постоянный — твой домен**):
```bash
cat > /opt/tg_miniapp/backend/.env <<'EOF'
BOT_TOKEN=сюда_токен_от_BotFather
WEBAPP_URL=https://example.com
HOST=127.0.0.1
PORT=8000
EOF
```

Отдать проект пользователю `cookie` (чтобы он мог писать `game.db`):
```bash
chown -R cookie:cookie /opt/tg_miniapp
```

---

## 5. Автозапуск сервера и бота (systemd)

```bash
cp /opt/tg_miniapp/deploy/cookie-api.service /etc/systemd/system/
cp /opt/tg_miniapp/deploy/cookie-bot.service /etc/systemd/system/

systemctl daemon-reload
systemctl enable --now cookie-api
systemctl enable --now cookie-bot
```

Проверить статус (должно быть `active (running)`):
```bash
systemctl status cookie-api --no-pager
systemctl status cookie-bot --no-pager
```

Смотреть логи, если что-то не так:
```bash
journalctl -u cookie-api -e --no-pager
journalctl -u cookie-bot -e --no-pager
```

---

## 6. Caddy — HTTPS и проксирование

```bash
# установка Caddy (официальный репозиторий)
apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update && apt install -y caddy

# положить наш конфиг (не забудь заменить example.com внутри файла на свой домен!)
cp /opt/tg_miniapp/deploy/Caddyfile /etc/caddy/Caddyfile
nano /etc/caddy/Caddyfile     # поменяй example.com на свой домен, сохрани (Ctrl+O, Enter, Ctrl+X)

systemctl restart caddy
systemctl status caddy --no-pager
```

Caddy сам получит сертификат Let's Encrypt при первом обращении к домену (нужно, чтобы
A-запись из шага 1 уже указывала на этот сервер и порты 80/443 были открыты).

---

## 7. Проверка

- Открой `https://example.com` в браузере — страница игры загрузится (в браузере будет
  ошибка авторизации — это нормально, `initData` есть только внутри Telegram).
- В Telegram: бот → `/start` → кнопка **«🍪 Играть»** → игра работает по HTTPS.

Дополнительно в @BotFather можно задать кнопку меню чата:
`/setmenubutton` → выбрать бота → указать URL `https://example.com` и текст «Играть».

---

## 8. Обновление игры после правок

На локальной машине запушил изменения в GitHub, затем на сервере:
```bash
cd /opt/tg_miniapp
git pull
systemctl restart cookie-api cookie-bot   # bot перезапускать нужно только если менял bot.py
```
(если фронтенд менялся — статику отдаёт сервер, отдельной сборки нет, хватит `git pull`).

---

## Частые проблемы

| Симптом | Причина / решение |
|---|---|
| Caddy не выдаёт сертификат | A-запись ещё не обновилась, или закрыты порты 80/443 (`ufw status`) |
| Бот не отвечает | Неверный `BOT_TOKEN`; смотри `journalctl -u cookie-bot -e` |
| В Telegram «данные недействительны» / 401 | `WEBAPP_URL` в `.env` не совпадает с доменом, откуда открыт апп |
| `game.db` не пишется | Забыл `chown -R cookie:cookie /opt/tg_miniapp` |
| 502 от Caddy | `cookie-api` не запущен: `systemctl status cookie-api` |
