import random
import sqlite3
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.engine import get_db_connection
from database.queries import get_full_profile
from utils.economy import calculate_raid_chance
from keyboards.inline import get_rivals_inline

router = Router()

@router.message(F.text.lower().in_(["🕵️ подполье", "подполье", "конкуренты", "нелегал"]))
async def list_rivals(message: Message) -> None:
    """Экран теневого сектора. Доступ строго с 5 уровня."""
    tg_id = message.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        return
        
    # Защитный барьер по уровню
    if profile["level"] < 5:
        await message.answer(
            "🕵️ <b>ТЕНЕВОЙ СЕКТОР</b>\n\n"
            "Сюда пускают только проверенных людей. Наберись авторитета "
            "(<b>Нужен 5 уровень</b>)."
        )
        return

    # Запрашиваем кастомные цены игрока для сравнения
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, custom_price FROM user_prices WHERE tg_id = ?;", (tg_id,))
    prices_rows = cursor.fetchall()
    conn.close()
    
    user_prices = {row["item_id"]: row["custom_price"] for row in prices_rows}
    
    user_bread = user_prices.get("bread", "Не выставлена")
    user_phone = user_prices.get("phones", "Не выставлена")

    # Эмуляция розничных цен ботов-конкурентов из ТЗ
    bot_artem_bread = 12.0
    bot_sergey_phones = 210.0
    
    raid_chance = calculate_raid_chance(profile["security_level"])

    text = (
        "🕵️ <b>ТЕНЕВОЙ СЕКТОР И КОНКУРЕНТЫ</b>\n\n"
        "Здесь отображаются розничные цены твоих прямых конкурентов. "
        "Если твоя цена выше их цен, клиенты будут уходить к ним.\n\n"
        f"1. Артем 👨‍💼 (Rep: 600) — Хлеб: <b>{bot_artem_bread} 💵</b> "
        f"(У тебя: <i>{user_bread}</i> 💵)\n"
        f"2. Сергей 🧔‍♂️ (Rep: 300) — Смартфоны: <b>{bot_sergey_phones} 💵</b> "
        f"(У тебя: <i>{user_phone}</i> 💵)\n"
        f"──────────────────────────\n"
        f"🍁 Доступен контрабандный груз для закупки!\n"
        f"Текущий риск облавы силовиков: <b>{raid_chance}%</b>"
    )

    await message.answer(text, reply_markup=get_rivals_inline())

@router.callback_query(F.data == "rivals_dumping")
async def process_dumping(callback: CallbackQuery) -> None:
    """Демпинг рынка: списывает 10 AP и 200 денег."""
    tg_id = callback.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        return

    if profile["energy"] < 10 or profile["money"] < 200:
        await callback.answer("❌ Недостаточно ресурсов! Нужно: 10 AP и 200 💵.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION;")
        # Списываем ресурсы за подрыв рынка
        cursor.execute(
            "UPDATE users SET energy = energy - 10, money = money - 200 WHERE tg_id = ?;", 
            (tg_id,)
        )
        # Искусственно обрушаем demand_modifier в системе на час (эмуляция через скрутку индексов)
        cursor.execute("UPDATE system_market SET demand_modifier = max(0.4, demand_modifier - 0.3);")
        conn.commit()
        await callback.answer("📉 Рынок подорван! Цены конкурентов обрушились, адаптируйте свои ценники.", show_alert=True)
    except sqlite3.Error:
        conn.rollback()
        await callback.answer("Произошла ошибка при демпинге.", show_alert=True)
    finally:
        conn.close()

@router.callback_query(F.data == "rivals_contraband")
async def process_contraband_gamble(callback: CallbackQuery) -> None:
    """Покупка контрабанды с триггером полицейского рейда."""
    tg_id = callback.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        return

    raid_chance = calculate_raid_chance(profile["security_level"])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Генерация шанса рейда
    if random.randint(1, 100) <= raid_chance:
        # Рейд успешен: штраф 30% денег, конфискация нелегала, -50 репутации
        new_money = profile["money"] * 0.7
        cursor.execute("""
            UPDATE users 
            SET money = ?, reputation = max(0, reputation - 50) 
            WHERE tg_id = ?;
        """, (new_money, tg_id))
        cursor.execute("UPDATE warehouse_stock SET contraband = 0 WHERE tg_id = ?;", (tg_id,))
        
        await callback.answer(
            "🚨 ОБЛАВА СИЛОВИКОВ!\n\n"
            "Ваш склад накрыли. Изъят весь нелегальный товар, списано 50 очков репутации "
            "и наложен штраф на кэш (-30%).", 
            show_alert=True
        )
    else:
        # Успешный завоз: +5 единиц контрабанды на склад бесплатно
        cursor.execute("UPDATE warehouse_stock SET contraband = contraband + 5 WHERE tg_id = ?;", (tg_id,))
        await callback.answer("🍁 Успех! Контрабандный груз доставлен на склад (+5 ед. нелегала).", show_alert=True)
        
    conn.commit()
    conn.close()
