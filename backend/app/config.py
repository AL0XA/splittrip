"""Конфигурация приложения из переменных окружения."""
import os
from pathlib import Path

from dotenv import load_dotenv

# Загружаем .env из папки backend/
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
# Username бота без @ — нужен для инвайт-ссылок вида https://t.me/<bot>?startapp=<код>
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "http://localhost:8000")
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# Путь к файлу базы данных SQLite
DB_PATH: Path = BASE_DIR / "app.db"

# Папка со статикой фронтенда
FRONTEND_DIR: Path = BASE_DIR.parent / "frontend"

# Максимальный возраст initData (сек). Защищает от повторного использования.
INIT_DATA_MAX_AGE = 24 * 3600
