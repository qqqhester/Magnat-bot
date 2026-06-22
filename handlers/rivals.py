import random
import sqlite3
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.engine import get_db_connection
from database.queries import get_full_profile
from utils.economy import calculate_raid_chance
from keyboards.inline import get_rivals_inline

router = Router()

async def render_rivals_screen(tg_id: int, message: Message, edit: bool = False) -> None:
    """Универсальная отрисовка теневого сектора для актуализации данных в реальном времени."""
    profile = get_full_profile(tg_id)
    if not profile:
        return
        
    if profile["level"] < 5:
        text = (
            "🕵️ <b>ТЕНЕВОЙ СЕКТОР</b>\n\n"
            "Сюда пускают только проверенных людей. Наберись авторитета "
            "(<b>Нужен 5 уровень</b>)."
        )
        if edit:
            await message.edit_text(text, reply_markup=None)
        else:
            await message.answer(text)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, custom_price FROM user_prices WHERE tg_id = ?;", (tg_id,))
    prices_rows = cursor.fetchall()
    conn.close()
    
    user_prices = {row["item_id"]: row["custom_price"] for row in prices_rows}
    user_bread = user_prices.get("bread", "Не выставлена")
    user_phone = user_prices.get("phones", "Не выставлена")

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
        f"💼 Твой баланс: <b>{profile['money']:.2f} 💵</b> | Энергия: <b>{profile['energy']} AP</b>\n"
        f"📦 Нелегала на складе: <b>{profile['contraband']} ед.</b>\n"
        f"Текущий риск облавы силовиков: <b>{raid_chance}%</b>"
    )

    if edit:
        await message.edit_text(text, reply_markup=get_rivals_inline())
    else:
        await message.answer(text, reply_markup=get_rivals_inline())

@router.message(F.text.lower().in_(["🕵️ подполье", "подполье", "конкуренты", "нелегал"]))
async def list_rivals(message: Message) -> None:
    await render_rivals_screen(message.from_user.id, message, edit=False)

@router.callback_query(F.data == "rivals_dumping")
async def process_dumping(callback: CallbackQuery) -> None:
    """Демпинг рынка с моментальным обновлением UI."""
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
        cursor.execute(
            "UPDATE users SET energy = energy - 10, money = money - 200 WHERE tg_id = ?;", 
            (tg_id,)
        )
        cursor.execute("UPDATE system_market SET demand_modifier = max(0.4, demand_modifier - 0.3);")
        conn.commit()
        await callback.answer("📉 Рынок подорван! Цены конкурентов обрушились.", show_alert=True)
    except sqlite3.Error:
        conn.rollback()
        await callback.answer("Произошла ошибка при демпинге.", show_alert=True)
    finally:
        conn.close()
        
    # Моментально обновляем экран подполья
    await render_rivals_screen(tg_id, callback.message, edit=True)

@router.callback_query(F.data == "rivals_contraband")
async def process_contraband_gamble(callback: CallbackQuery) -> None:
    """Покупка контрабанды с триггером полицейского рейда и живым обновлением интерфейса."""
    tg_id = callback.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        return

    raid_chance = calculate_raid_chance(profile["security_level"])
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if random.randint(1, 100) <= raid_chance:
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
        cursor.execute("UPDATE warehouse_stock SET contraband = contraband + 5 WHERE tg_id = ?;", (tg_id,))
        await callback.answer("🍁 Успех! Контрабандный груз доставлен на склад (+5 ед. нелегала).", show_alert=True)
        
    conn.commit()
    conn.close()
    
    # Живое обновление! Игрок сразу увидит, потерял ли он баланс или добавился нелегал
    await render_rivals_screen(tg_id, callback.message, edit=True)
