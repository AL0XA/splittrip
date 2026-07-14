"""Telegram-бот на aiogram: команда /start с кнопкой запуска Mini App."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
)

from app.config import BOT_TOKEN, WEBAPP_URL

logging.basicConfig(level=logging.INFO)

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message) -> None:
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="💸 Открыть",
                web_app=WebAppInfo(url=WEBAPP_URL),
            )
        ]]
    )
    await message.answer(
        "💸 <b>Тусовка &amp; Траты</b>\n\n"
        "Создавай события, зови друзей и добавляй общие траты — "
        "приложение само посчитает, кто кому и сколько должен перевести.\n\n"
        "Жми кнопку ниже, чтобы начать:",
        reply_markup=keyboard,
    )


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN не задан. Заполни backend/.env (см. .env.example)")
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
