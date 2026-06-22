import random
import json
from datetime import datetime, timedelta
from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.database import get_user, update_user, cursor, conn
from bot.keyboards import main_menu
from bot.config import ADMIN_ID

# === ТОВАРЫ ===
PRODUCTS = {
    "bread": {"name": "🍞 Хлеб", "buy": 10, "sell": 15, "level": 1},
    "milk": {"name": "🥛 Молоко", "buy": 15, "sell": 22, "level": 1},
    "meat": {"name": "🥩 Мясо", "buy": 25, "sell": 38, "level": 2},
    "clothes": {"name": "👕 Одежда", "buy": 40, "sell": 60, "level": 3},
    "phone": {"name": "📱 Телефон", "buy": 80, "sell": 120, "level": 4},
    "car": {"name": "🚗 Автомобиль", "buy": 500, "sell": 750, "level": 5},
    "gold": {"name": "💍 Ювелирка", "buy": 1000, "sell": 1500, "level": 6},
}

# === ПОДПОЛЬНЫЕ ТОВАРЫ ===
UNDERGROUND = {
    "weapon": {"name": "🔫 Оружие", "buy": 3000, "sell": 5000, "risk": 20},
    "drugs": {"name": "💊 Наркотики", "buy": 10000, "sell": 20000, "risk": 60},
    "documents": {"name": "📄 Документы", "buy": 5000, "sell": 8000, "risk": 40},
}

# === КВЕСТЫ ===
DAILY_QUESTS = [
    {"text": "Продай 5 товаров", "target": 5, "reward": 50, "type": "sell"},
    {"text": "Заработай 200 монет", "target": 200, "reward": 75, "type": "earn"},
    {"text": "Сделай 1 улучшение", "target": 1, "reward": 100, "type": "upgrade"},
]
WEEKLY_QUESTS = [
    {"text": "Продай 50 товаров", "target": 50, "reward": 300, "type": "sell"},
    {"text": "Заработай 2000 монет", "target": 2000, "reward": 500, "type": "earn"},
    {"text": "Сделай 5 улучшений", "target": 5, "reward": 400, "type": "upgrade"},
]

# === ДОСТИЖЕНИЯ ===
ACHIEVEMENTS = {
    "first_sale": {"name": "Первая продажа", "desc": "Продай первый товар", "reward": 50, "type": "sales", "target": 1},
    "sales_10": {"name": "Торговец", "desc": "Продай 10 товаров", "reward": 100, "type": "sales", "target": 10},
    "sales_100": {"name": "Магнат", "desc": "Продай 100 товаров", "reward": 500, "type": "sales", "target": 100},
    "level_5": {"name": "Развитие", "desc": "Достигни 5 уровня", "reward": 200, "type": "level", "target": 5},
    "level_10": {"name": "Влияние", "desc": "Достигни 10 уровня", "reward": 500, "type": "level", "target": 10},
}

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def get_available_products(level):
    return {k: v for k, v in PRODUCTS.items() if v["level"] <= level}

def check_achievements(tg_id, achievement_type, value):
    user = get_user(tg_id)
    if not user:
        return []
    achievements = json.loads(user[13]) if len(user) > 13 and user[13] else []
    unlocked = []
    for key, ach in ACHIEVEMENTS.items():
        if key in achievements:
            continue
        if ach["type"] == achievement_type and value >= ach["target"]:
            achievements.append(key)
            update_user(tg_id, "money", user[2] + ach["reward"])
            unlocked.append(ach)
    update_user(tg_id, "achievements", json.dumps(achievements))
    return unlocked

def register_handlers(dp):
    @dp.message(Command("start"))
    async def start(message: types.Message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if not user:
            cursor.execute("INSERT INTO users (tg_id, username, achievements) VALUES (?, ?, ?)", 
                          (tg_id, message.from_user.username or "Аноним", json.dumps([])))
            conn.commit()
        await message.answer(
            "🏢 *«Теневой Магнат»*\n\n"
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
        achievements = json.loads(user[13]) if len(user) > 13 and user[13] else []
        await message.answer(
            f"👤 *Профиль*\n"
            f"Имя: {user[1]}\n"
            f"💰 Деньги: {user[2]}\n"
            f"💎 Кристаллы: {user[3]}\n"
            f"⭐ Репутация: {user[4]}\n"
            f"📈 Уровень: {user[5]}\n"
            f"🏪 Магазин: Уровень {user[7]}\n"
            f"👨‍💼 Работников: {user[8]}\n"
            f"💰 Заработано: {user[10]}\n"
            f"🏆 Достижений: {len(achievements)}\n",
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
        user = get_user(message.from_user.id)
        if not user:
            await message.answer("Напиши /start")
            return
        available = get_available_products(user[5])
        text = "🏪 *Магазин*\n\n"
        for key, p in available.items():
            text += f"{p['name']} — Закуп: {p['buy']}, Продажа: {p['sell']}\n"
        text += "\nВведите номер товара, чтобы продать:\n1. Хлеб\n2. Молоко\n3. Мясо\n4. Одежда\n5. Телефон\n6. Автомобиль\n7. Ювелирка"
        await message.answer(text, parse_mode="Markdown")

    @dp.message(lambda msg: msg.text.isdigit() and 1 <= int(msg.text) <= 7)
    async def sell_product(message: types.Message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if not user:
            await message.answer("Напиши /start")
            return
        product_key = list(PRODUCTS.keys())[int(message.text) - 1]
        product = PRODUCTS[product_key]
        if product["level"] > user[5]:
            await message.answer(f"❌ Нужен уровень {product['level']} для продажи {product['name']}")
            return
        profit = product["sell"] - product["buy"]
        new_money = user[2] + profit
        update_user(tg_id, "money", new_money)
        update_user(tg_id, "total_earned", user[10] + profit)
        
        # Проверка достижений
        unlocked = check_achievements(tg_id, "sales", user[10] + profit)
        msg = f"✅ {product['name']} продан! +{profit} 💵"
        if unlocked:
            msg += "\n\n🏆 *Достижения разблокированы:*\n" + "\n".join([f"{ach['name']} (+{ach['reward']} 💵)" for ach in unlocked])
        await message.answer(msg, parse_mode="Markdown")

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

    @dp.message(Command("casino"))
    async def casino(message: types.Message):
        await message.answer(
            "🎰 *Казино*\n\n"
            "🎲 Рулетка — ставка 50 💵 (шанс 50%)\n"
            "🃏 Блэкджек — ставка 100 💵 (шанс 40%)\n\n"
            "Напиши /roulette 50 или /blackjack 100",
            parse_mode="Markdown"
        )

    @dp.message(Command("roulette"))
    async def roulette(message: types.Message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if not user:
            await message.answer("Напиши /start")
            return
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Использование: /roulette 50")
            return
        try:
            bet = int(parts[1])
        except ValueError:
            await message.answer("❌ Ставка должна быть числом")
            return
        if bet < 50:
            await message.answer("❌ Минимальная ставка 50 💵")
            return
        if user[2] < bet:
            await message.answer("❌ Недостаточно денег")
            return
        if random.random() < 0.5:
            win = bet * 2
            update_user(tg_id, "money", user[2] + win)
            await message.answer(f"✅ Вы выиграли! +{win} 💵")
        else:
            update_user(tg_id, "money", user[2] - bet)
            await message.answer(f"❌ Вы проиграли! -{bet} 💵")

    @dp.message(Command("blackjack"))
    async def blackjack(message: types.Message):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if not user:
            await message.answer("Напиши /start")
            return
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Использование: /blackjack 100")
            return
        try:
            bet = int(parts[1])
        except ValueError:
            await message.answer("❌ Ставка должна быть числом")
            return
        if bet < 100:
            await message.answer("❌ Минимальная ставка 100 💵")
            return
        if user[2] < bet:
            await message.answer("❌ Недостаточно денег")
            return
        if random.random() < 0.4:
            win = bet * 2.5
            update_user(tg_id, "money", user[2] + win)
            await message.answer(f"✅ Вы выиграли! +{int(win)} 💵")
        else:
            update_user(tg_id, "money", user[2] - bet)
            await message.answer(f"❌ Вы проиграли! -{bet} 💵")

    @dp.message(Command("underground"))
    async def underground(message: types.Message):
        text = "🕵️ *Подпольный рынок*\n\n"
        for key, p in UNDERGROUND.items():
            text += f"{p['name']} — Закуп: {p['buy']}, Продажа: {p['sell']}, Риск: {p['risk']}%\n"
        text += "\nНапиши /sell_weapon, /sell_drugs или /sell_documents"
        await message.answer(text, parse_mode="Markdown")

    @dp.message(Command("sell_weapon"))
    async def sell_weapon(message: types.Message):
        await sell_underground(message, "weapon")

    @dp.message(Command("sell_drugs"))
    async def sell_drugs(message: types.Message):
        await sell_underground(message, "drugs")

    @dp.message(Command("sell_documents"))
    async def sell_documents(message: types.Message):
        await sell_underground(message, "documents")

    async def sell_underground(message: types.Message, key):
        tg_id = message.from_user.id
        user = get_user(tg_id)
        if not user:
            await message.answer("Напиши /start")
            return
        product = UNDERGROUND[key]
        if user[2] < product["buy"]:
            await message.answer("❌ Недостаточно денег для закупки")
            return
        if random.random() < product["risk"] / 100:
            await message.answer(f"❌ Проверка! Товар изъят, потеряно {product['buy']} 💵")
            update_user(tg_id, "money", user[2] - product["buy"])
            return
        profit = product["sell"] - product["buy"]
        update_user(tg_id, "money", user[2] + profit)
        await message.answer(f"✅ {product['name']} продан! +{profit} 💵")

    @dp.message(Command("quests"))
    async def quests(message: types.Message):
        user = get_user(message.from_user.id)
        if not user:
            await message.answer("Напиши /start")
            return
        text = "📜 *Ежедневные квесты*\n\n"
        for q in DAILY_QUESTS:
            text += f"• {q['text']} — Награда: {q['reward']} 💵\n"
        text += "\n📜 *Еженедельные квесты*\n\n"
        for q in WEEKLY_QUESTS:
            text += f"• {q['text']} — Награда: {q['reward']} 💵\n"
        await message.answer(text, parse_mode="Markdown")

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
            [InlineKeyboardButton(text="🎟️ Промокод", callback_data="admin_promo")],
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
        elif action == "promo":
            await callback.message.edit_text("🎟️ Введи промокод и награду: /promo SUMMER 100")

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

    @dp.message(Command("promo"))
    async def promo(message: types.Message):
        if message.from_user.id != ADMIN_ID:
            return
        parts = message.text.split()
        if len(parts) != 3:
            await message.answer("❌ Использование: /promo КОД 100")
            return
        code, reward = parts[1], int(parts[2])
        await message.answer(f"🎟️ Промокод {code} создан на {reward} 💵")

    @dp.message(Command("level"))
    async def level_info(message: types.Message):
        user = get_user(message.from_user.id)
        if not user:
            await message.answer("Напиши /start")
            return
        exp_needed = user[5] * 50
        await message.answer(
            f"📈 *Уровень*\n\n"
            f"Текущий уровень: {user[5]}\n"
            f"Опыт: {user[6]}/{exp_needed}\n"
            f"Награда за уровень: +{user[5] * 20} 💵\n"
            f"Доступно товаров: {len(get_available_products(user[5]))}",
            parse_mode="Markdown"
        )
