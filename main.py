import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import logging
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("magnat.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    username TEXT,
    money INTEGER DEFAULT 100,
    crystals INTEGER DEFAULT 0,
    reputation INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    last_bonus TIMESTAMP DEFAULT '1970-01-01 00:00:00'
)
''')
conn.commit()

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Бонус")],
            [KeyboardButton(text="🏪 Магазин"), KeyboardButton(text="🏆 Топ")]
        ],
        resize_keyboard=True
    )

@dp.message(Command("start"))
async def start(message: types.Message):
    tg_id = message.from_user.id
    user = cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
    if not user:
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, message.from_user.username or "Аноним"))
        conn.commit()
    await message.answer("🏢 Добро пожаловать! Используй кнопки внизу.", reply_markup=main_menu())

@dp.message(lambda msg: msg.text == "👤 Профиль")
async def profile(message: types.Message):
    user = cursor.execute("SELECT * FROM users WHERE tg_id = ?", (message.from_user.id,)).fetchone()
    if not user:
        await message.answer("Напиши /start")
        return
    await message.answer(
        f"👤 Профиль\n"
        f"Деньги: {user[2]} 💵\n"
        f"Кристаллы: {user[3]} 💎\n"
        f"Репутация: {user[4]}\n"
        f"Уровень: {user[5]}\n"
    )

@dp.message(lambda msg: msg.text == "🎁 Бонус")
async def bonus_day(message: types.Message):
    tg_id = message.from_user.id
    user = cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
    if not user:
        await message.answer("Напиши /start")
        return
    last_bonus = datetime.fromisoformat(user[7]) if user[7] != '1970-01-01 00:00:00' else None
    if last_bonus and datetime.now() - last_bonus < timedelta(hours=24):
        await message.answer("❌ Бонус уже получен! Жди 24 часа.")
        return
    bonus = random.randint(50, 200)
    cursor.execute("UPDATE users SET money = money + ?, last_bonus = ? WHERE tg_id = ?", (bonus, datetime.now().isoformat(), tg_id))
    conn.commit()
    await message.answer(f"✅ Бонус получен! +{bonus} 💵")

@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет прав")
        return
    await message.answer("🔐 Админ-панель доступна.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
