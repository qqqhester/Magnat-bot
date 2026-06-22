import random
from datetime import datetime, timedelta
from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.database import get_user, update_user, cursor, conn
from bot.keyboards import main_menu
from bot.config import ADMIN_ID

def register_handlers(dp):
    @dp.message(Command("start"))
    async def start(message: types.Message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if not user:
            cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?)", 
                          (tg_id, message.from_user.username or "Аноним"))
            conn.commit()
        await message.answer(
            "🏢 *Добро пожаловать в «Теневой Магнат»!*\n\n"
            "Строй империю, зарабатывай деньги и стань легендой.\n"
            "Используй кнопки внизу экрана.",
            reply_markup=main_menu(),
            parse_mode="Markdown"
        )

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
        user = get_user(tg_id)
        if not user:
            await message.answer("Напиши /start")
            return
        last_bonus = datetime.fromisoformat(user[11]) if user[11] != '1970-01-01 00:00:00' else None
        if last_bonus and datetime.now() - last_bonus < timedelta(hours=24):
            next_bonus = last_bonus + timedelta(hours=24)
            remaining = next_bonus - datetime.now()
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            seconds = remaining.seconds % 60
            await message.answer(f"⏳ Бонус через: {hours:02d}:{minutes:02d}:{seconds:02d}")
            return
        bonus = random.randint(50, 200)
        update_user(tg_id, "money", user[2] + bonus)
        update_user(tg_id, "last_bonus", datetime.now().isoformat())
        await message.answer(f"✅ Бонус получен! +{bonus} 💵")

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
        update_user(tg_id, "money", money - price)
        update_user(tg_id, "shop_level", level + 1)
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
        update_user(tg_id, "money", money - price)
        update_user(tg_id, "workers", workers + 1)
        await message.answer(f"✅ Нанят работник! Всего: {workers + 1}")

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

    @dp.message(Command("admin"))
    async def admin_panel(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("❌ Нет прав")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="💰 Выдать деньги", callback_data="admin_give")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        ])
        await message.answer("🔐 *Админ-панель*", reply_markup=keyboard, parse_mode="Markdown")

    @dp.callback_query(lambda c: c.data.startswith("admin_"))
    async def admin_actions(callback: types.CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("❌ Нет прав", show_alert=True)
            return
        action = callback.data.split("_")[1]
        if action == "stats":
            cursor.execute("SELECT COUNT(*) FROM users")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(money) FROM users")
            total_money = cursor.fetchone()[0] or 0
            await callback.message.edit_text(
                f"📊 *Статистика*\n\n"
                f"👥 Игроков: {total}\n"
                f"💰 Денег в системе: {total_money} 💵"
            )
        elif action == "give":
            await callback.message.edit_text("💰 Введи ID и сумму: /give 123456 500")
        elif action == "broadcast":
            await callback.message.edit_text("📢 Напиши сообщение для рассылки:")

    @dp.message(Command("give"))
    async def give_money(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            return
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Использование: /give tg_id сумма")
            return
        try:
            tg_id = int(parts[1])
            amount = int(parts[2])
            user = get_user(tg_id)
            if not user:
                await message.answer("❌ Игрок не найден")
                return
            update_user(tg_id, "money", user[2] + amount)
            await message.answer(f"✅ Игроку {tg_id} выдано {amount} 💵")
        except ValueError:
            await message.answer("❌ Неверный формат")
