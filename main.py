import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from bot.config import TOKEN
from bot.database import init_db
from bot.handlers import register_handlers

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

async def set_commands():
    await bot.set_my_commands([
        BotCommand(command="start", description="🏁 Старт"),
        BotCommand(command="profile", description="👤 Профиль"),
        BotCommand(command="shop", description="🏪 Магазин"),
        BotCommand(command="casino", description="🎰 Казино"),
        BotCommand(command="underground", description="🕵️ Подполье"),
        BotCommand(command="bonus", description="🎁 Бонус"),
        BotCommand(command="quests", description="📜 Квесты"),
        BotCommand(command="top", description="🏆 Топ"),
        BotCommand(command="level", description="📈 Уровень"),
        BotCommand(command="admin", description="🔐 Админка"),
    ])

async def main():
    init_db()
    register_handlers(dp)
    await set_commands()
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
