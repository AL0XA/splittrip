"""Проверка подлинности Telegram Mini App initData.

Telegram передаёт в Web App строку initData, подписанную секретным ключом на
основе токена бота. Проверяем HMAC-подпись, чтобы убедиться, что данные
пользователя настоящие и не подделаны.
Документация: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from .config import BOT_TOKEN, INIT_DATA_MAX_AGE


def validate_init_data(init_data: str) -> dict | None:
    """Проверяет initData и возвращает данные пользователя (dict) либо None."""
    if not init_data or not BOT_TOKEN:
        return None

    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    # Строка для проверки: все поля кроме hash, отсортированные по ключу.
    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )

    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        return None

    # Проверка свежести, чтобы нельзя было переиспользовать старый initData.
    auth_date = parsed.get("auth_date")
    if auth_date and INIT_DATA_MAX_AGE > 0:
        try:
            if time.time() - int(auth_date) > INIT_DATA_MAX_AGE:
                return None
        except ValueError:
            return None

    user_raw = parsed.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None

    if "id" not in user:
        return None
    return user
