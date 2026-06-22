import asyncio
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import logging
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

bot = Bot(token=TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# === БАЗА ДАННЫХ ===
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
    shop_level INTEGER DEFAULT 1,
    workers INTEGER DEFAULT 0,
    last_bonus TIMESTAMP DEFAULT '1970-01-01 00:00:00',
    total_earned INTEGER DEFAULT 0
)
''')
conn.commit()

def get_user(tg_id):
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return cursor.fetchone()

def update_user(tg_id, column, value):
    cursor.execute(f"UPDATE users SET {column} = ? WHERE tg_id = ?", (value, tg_id))
    conn.commit()

# === КЛАВИАТУРЫ ===
def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🏪 Магазин")],
            [KeyboardButton(text="🔧 Улучшения"), KeyboardButton(text="👨‍💼 Работники")],
            [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="🏆 Топ")]
        ],
        resize_keyboard=True
    )

def bonus_button(tg_id):
    user = get_user(tg_id)
    if not user:
        return None
    last_bonus = datetime.fromisoformat(user[9]) if user[9] != '1970-01-01 00:00:00' else None
    if last_bonus is None or datetime.now() - last_bonus >= timedelta(hours=24):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Забрать бонус", callback_data="take_bonus")]
        ])
    next_bonus = last_bonus + timedelta(hours=24)
    remaining = next_bonus - datetime.now()
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60
    seconds = remaining.seconds % 60
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⏳ Бонус через: {hours:02d}:{minutes:02d}:{seconds:02d}",
            callback_data="bonus_soon"
        )]
    ])

# === КОМАНДЫ ===
@dp.message(Command("start"))
async def start(message: types.Message):
    tg_id = message.from_user.id
    user = get_user(tg_id)
    if not user:
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", (tg_id, message.from_user.username or "Аноним"))
        conn.commit()
    await message.answer("🏢 Добро пожаловать! Используй кнопки внизу.", reply_markup=main_menu())

@dp.message(lambda msg: msg.text == "👤 Профиль")
async def profile(message: types.Message):
    user = get_user(message.from_user.id)
    if not user:
        await message.answer("Напиши /start")
        return
    await message.answer(
        f"👤 *Профиль*\n"
        f"Имя: {user[1]}\n"
        f"💰 Деньги: {user[2]}\n"
        f"💎 Кристаллы: {user[3]}\n"
        f"⭐ Репутация: {user[4]}\n"
        f"📈 Уровень: {user[5]}\n"
        f"🏪 Магазин: Уровень {user[7]}\n"
        f"👨‍💼 Работников: {user[8]}\n"
        f"💰 Заработано: {user[10]}\n",
        parse_mode="Markdown"
    )

@dp.message(lambda msg: msg.text == "🎁 Бонус")
async def bonus_day(message: types.Message):
    tg_id = message.from_user.id
    keyboard = bonus_button(tg_id)
    if keyboard:
        await message.answer("🎁 *Бонус дня*", reply_markup=keyboard, parse_mode="Markdown")
    else:
        await message.answer("❌ Ошибка")

@dp.callback_query(lambda c: c.data == "take_bonus")
async def take_bonus(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    user = get_user(tg_id)
    if not user:
        await callback.answer("Ошибка", show_alert=True)
        return
    last_bonus = datetime.fromisoformat(user[9]) if user[9] != '1970-01-01 00:00:00' else None
    if last_bonus and datetime.now() - last_bonus < timedelta(hours=24):
        await callback.answer("❌ Бонус уже получен!", show_alert=True)
        return
    bonus = random.randint(50, 200)
    cursor.execute("UPDATE users SET money = money + ?, last_bonus = ? WHERE tg_id = ?", (bonus, datetime.now().isoformat(), tg_id))
    conn.commit()
    await callback.message.edit_text(f"✅ Бонус получен! +{bonus} 💵")

@dp.callback_query(lambda c: c.data == "bonus_soon")
async def bonus_soon(callback: types.CallbackQuery):
    await callback.answer("❌ Бонус ещё не готов!", show_alert=True)

@dp.message(lambda msg: msg.text == "🏪 Магазин")
async def shop(message: types.Message):
    await message.answer(
        "🏪 *Магазин*\n\n"
        "🍞 Хлеб (Закуп: 10, Продажа: 15)\n"
        "🥛 Молоко (Закуп: 15, Продажа: 22)\n"
        "🥩 Мясо (Закуп: 25, Продажа: 38)\n"
        "👕 Одежда (Закуп: 40, Продажа: 60)\n"
        "📱 Телефоны (Закуп: 80, Продажа: 120)\n\n"
        "⬆️ /upgrade_shop — улучшить магазин\n"
        "👨‍💼 /hire_worker — нанять работника",
        parse_mode="Markdown"
    )

@dp.message(Command("upgrade_shop"))
async def upgrade_shop(message: types.Message):
    tg_id = message.from_user.id
    user = get_user(tg_id)
    if not user:
        await message.answer("Напиши /start")
        return
    money = user[2]
    level = user[7]
    price = 200 * (1.3 ** level)
    if money < price:
        await message.answer(f"❌ Нужно {int(price)} 💵")
        return
    cursor.execute("UPDATE users SET money = money - ?, shop_level = shop_level + 1 WHERE tg_id = ?", (price, tg_id))
    conn.commit()
    await message.answer(f"✅ Уровень магазина повышен до {level + 1}!")

@dp.message(Command("hire_worker"))
async def hire_worker(message: types.Message):
    tg_id = message.from_user.id
    user = get_user(tg_id)
    if not user:
        await message.answer("Напиши /start")
        return
    money = user[2]
    workers = user[8]
    price = 200 * (1.2 ** workers)
    if money < price:
        await message.answer(f"❌ Нужно {int(price)} 💵")
        return
    cursor.execute("UPDATE users SET money = money - ?, workers = workers + 1 WHERE tg_id = ?", (price, tg_id))
    conn.commit()
    await message.answer(f"✅ Нанят работник! Всего: {workers + 1}")

@dp.message(Command("admin"))
async def admin(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет прав")
        return
    await message.answer("🔐 Админ-панель доступна.")

@dp.message(Command("top"))
async def top(message: types.Message):
    cursor.execute("SELECT username, money, level FROM users ORDER BY money DESC LIMIT 10")
    rows = cursor.fetchall()
    if not rows:
        await message.answer("📊 Пока нет игроков")
        return
    text = "🏆 *Топ игроков:*\n\n"
    for i, row in enumerate(rows, 1):
        text += f"{i}. {row[0] or 'Аноним'} — 💰{row[1]} (Уровень {row[2]})\n"
    await message.answer(text, parse_mode="Markdown")

async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
