import sqlite3
import json
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.engine import get_db_connection
from database.queries import get_full_profile
from keyboards.inline import get_activation_inline

router = Router()

class PromoStates(StatesGroup):
    waiting_for_code = State()

async def render_bonus_menu(tg_id: int, message: Message, edit: bool = False) -> None:
    """Контролируемый рендеринг центра бонусов без дублирования сообщений."""
    profile = get_full_profile(tg_id)
    if not profile:
        return

    bonus_locked = False
    time_left_str = ""
    
    if profile["last_daily_bonus"]:
        last_bonus_time = datetime.strptime(profile["last_daily_bonus"], "%Y-%m-%d %H:%M:%S")
        time_passed = datetime.now() - last_bonus_time
        
        if time_passed < timedelta(days=1):
            bonus_locked = True
            time_left = timedelta(days=1) - time_passed
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_left_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    text = (
        "🎁 <b>РАСПРЕДЕЛИТЕЛЬНЫЙ ЦЕНТР</b>\n\n"
        "Здесь вы можете забрать ежедневную долю от подконтрольных точек "
        "или активировать секретный правительственный промокод."
    )
    
    if edit:
        await message.edit_text(text, reply_markup=get_activation_inline(bonus_locked, time_left_str))
    else:
        await message.answer(text, reply_markup=get_activation_inline(bonus_locked, time_left_str))

@router.message(F.text.lower().in_(["/bonus", "🎟️ активация", "активация", "бонус", "промо"]))
async def activation_menu(message: Message) -> None:
    await render_bonus_menu(message.from_user.id, message, edit=False)

@router.callback_query(F.data == "bonus_locked")
async def process_bonus_locked(callback: CallbackQuery) -> None:
    await callback.answer(
        "Рано, босс! Твои люди еще не собрали дань со всех точек.", 
        show_alert=True
    )

@router.callback_query(F.data == "bonus_claim")
async def process_bonus_claim(callback: CallbackQuery) -> None:
    """Выдача ежедневного бонуса с бесшовным обновлением интерфейса."""
    tg_id = callback.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users 
        SET money = money + 50.0, 
            energy = energy + 5, 
            last_daily_bonus = strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime')
        WHERE tg_id = ?;
    """, (tg_id,))
    conn.commit()
    conn.close()
    
    await callback.answer("🎉 Вы успешно забрали долю: +50.0 💵 и +5 AP (Overcharge)!", show_alert=True)
    # Вместо удаления сообщения, мы просто бесшовно его перерисовываем! Кнопка сменится на таймер
    await render_bonus_menu(tg_id, callback.message, edit=True)

@router.callback_query(F.data == "promo_activate")
async def process_promo_init(callback: CallbackQuery, state: FSMContext) -> None:
    """Перевод игрока в FSM для ввода промокода с изменением текста."""
    await callback.answer()
    await callback.message.edit_text(
        "🎟 ================ 🎟\n"
        "<b>Ввод наградного промокода</b>\n\n"
        "Отправьте секретный код ответным сообщением чат:",
        reply_markup=None
    )
    await state.set_state(PromoStates.waiting_for_code)

@router.message(PromoStates.waiting_for_code)
async def process_promo_validation(message: Message, state: FSMContext) -> None:
    """Проверка промокода и начисление награды."""
    code_input = message.text.strip()
    tg_id = message.from_user.id
    await state.clear()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM promocodes WHERE code = ?;", (code_input,))
    promo = cursor.fetchone()
    
    if not promo:
        await message.answer("❌ Такого промокода не существует или он устарел.")
        conn.close()
        await render_bonus_menu(tg_id, message, edit=False)
        return

    expires_at = datetime.strptime(promo["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expires_at:
        await message.answer("❌ Срок действия этого промокода истек.")
        conn.close()
        await render_bonus_menu(tg_id, message, edit=False)
        return

    if promo["current_activations"] >= promo["max_activations"]:
        await message.answer("❌ Этот промокод уже полностью исчерпан.")
        conn.close()
        await render_bonus_menu(tg_id, message, edit=False)
        return

    activated_users = json.loads(promo["activated_users"])
    if tg_id in activated_users:
        await message.answer("❌ Вы уже активировали этот промокод ранее!")
        conn.close()
        await render_bonus_menu(tg_id, message, edit=False)
        return

    reward_type = promo["reward_type"]
    reward_value = promo["reward_value"]
    
    try:
        cursor.execute("BEGIN TRANSACTION;")
        if reward_type == "money":
            cursor.execute("UPDATE users SET money = money + ? WHERE tg_id = ?;", (reward_value, tg_id))
            reward_text = f"{reward_value} 💵"
        elif reward_type == "crystals":
            cursor.execute("UPDATE users SET crystals = crystals + ? WHERE tg_id = ?;", (reward_value, tg_id))
            reward_text = f"{reward_value} 💎"
        elif reward_type == "energy":
            cursor.execute("UPDATE users SET energy = energy + ? WHERE tg_id = ?;", (reward_value, tg_id))
            reward_text = f"{reward_value} AP"
        else:
            raise ValueError("Неизвестный тип награды")

        activated_users.append(tg_id)
        cursor.execute("""
            UPDATE promocodes 
            SET current_activations = current_activations + 1,
                activated_users = ?
            WHERE code = ?;
        """, (json.dumps(activated_users), code_input))
        
        conn.commit()
        await message.answer(f"🎉 Промокод успешно активирован! Награда: <b>{reward_text}</b> доставлена на счет.")
    except Exception:
        conn.rollback()
        await message.answer("❌ Системный сбой при обработке транзакции.")
    finally:
        conn.close()
        # Возвращаем главное меню центра бонусов
        await render_bonus_menu(tg_id, message, edit=False)
