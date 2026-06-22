from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import random

from database.engine import get_db_connection

router = Router()

# Список ID администраторов (внеси сюда свой Telegram ID)
ADMIN_IDS = [7014140645]

class AdminStates(StatesGroup):
    waiting_for_tg_id = State()
    waiting_for_money = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def admin_panel_main(message: Message) -> None:
    """Главное меню админ-панели (доступно только по белому списку)."""
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ Команда не найдена. Возможно, вы ошиблись в написании.")
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💰 Выдать кэш игроку", callback_data="admin_give_money"))
    builder.row(InlineKeyboardButton(text="🔄 Ротация рынка (Тик)", callback_data="admin_market_tick"))
    builder.row(InlineKeyboardButton(text="📊 Серверная статистика", callback_data="admin_server_stats"))

    text = (
        "⚡ <b>РЕЖИМ ГЕЙМ-МАСТЕРА</b>\n\n"
        "Добро пожаловать в пульт управления макроэкономикой бота.\n"
        "Здесь вы можете корректировать базу данных «на лету»."
    )
    await message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "admin_give_money")
async def admin_give_money_init(callback: CallbackQuery, state: FSMContext) -> None:
    """Начало цепочки изменения баланса пользователя."""
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    await callback.message.answer("Введите Telegram ID игрока, которому хотите изменить баланс:")
    await state.set_state(AdminStates.waiting_for_tg_id)

@router.message(AdminStates.waiting_for_tg_id)
async def admin_process_tg_id(message: Message, state: FSMContext) -> None:
    """Валидация существования пользователя в базе."""
    try:
        target_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ ID должен состоять только из цифр. Повторите ввод:")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT level, money FROM users WHERE tg_id = ?;", (target_id,))
    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        await message.answer("❌ Пользователь с таким Telegram ID не зарегистрирован в игре. Повторите ввод:")
        return

    await state.update_data(target_tg_id=target_id)
    await message.answer(
        f"👤 Игрок найден.\n"
        f"Текущий уровень: {user_row['level']}\n"
        f"Баланс: {user_row['money']:.2f} 💵\n\n"
        f"Введите сумму, которую нужно **добавить** (или вычесть, указав минус):"
    )
    await state.set_state(AdminStates.waiting_for_money)

@router.message(AdminStates.waiting_for_money)
async def admin_process_money_amount(message: Message, state: FSMContext) -> None:
    """Атомарное начисление / списание средств через админку."""
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректное число!")
        return

    state_data = await state.get_data()
    target_id = state_data["target_tg_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Применяем изменения баланса
    cursor.execute(
        "UPDATE users SET money = max(0.0, money + ?) WHERE tg_id = ?;", 
        (amount, target_id)
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ Баланс игрока {target_id} успешно скорректирован на {amount:+.2f} 💵.")

@router.callback_query(F.data == "admin_market_tick")
async def admin_force_market_tick(callback: CallbackQuery) -> None:
    """Принудительная генерация новых ценовых коэффициентов на рынке."""
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    items = ["bread", "milk", "phones"]
    conn = get_db_connection()
    cursor = conn.cursor()

    # Симулируем поведение фонового планировщика задач
    for item in items:
        # Генерируем случайный коэффициент спроса от 0.5 до 1.6
        new_modifier = round(random.uniform(0.5, 1.6), 2)
        cursor.execute("""
            INSERT INTO system_market (item_id, demand_modifier)
            VALUES (?, ?)
            ON CONFLICT(item_id) DO UPDATE SET demand_modifier = EXCLUDED.demand_modifier;
        """, (item, new_modifier))

    conn.commit()
    conn.close()

    await callback.message.answer(
        "🔄 <b>ЭКОНОМИЧЕСКИЙ ТИК ВЫПОЛНЕН</b>\n\n"
        "Глобальные индексы спроса успешно пересчитаны. "
        "Цены розничных продаж подстроены под новые реалии рынка."
    )

@router.callback_query(F.data == "admin_server_stats")
async def admin_show_server_stats(callback: CallbackQuery) -> None:
    """Вывод агрегированной аналитики по серверу."""
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(id) as total_users, SUM(money) as total_cash FROM users;")
    stats = cursor.fetchone()
    
    cursor.execute("""
        SELECT SUM(bread) as b, SUM(milk) as m, SUM(phones) as p 
        FROM warehouse_stock;
    """)
    stock = cursor.fetchone()
    conn.close()

    text = (
        "📊 <b>СЕРВЕРНАЯ СТАТИСТИКА ЭКОНОМИКИ</b>\n\n"
        f"• Всего коммерсантов в базе: <b>{stats['total_users']}</b>\n"
        f"• Суммарная денежная масса: <b>{stats['total_cash']:.2f} 💵</b>\n\n"
        "📦 <b>Всего товаров на складах:</b>\n"
        f"— Хлеб: {stock['b'] or 0} шт.\n"
        f"— Молоко: {stock['m'] or 0} шт.\n"
        f"— Смартфоны: {stock['p'] or 0} шт."
    )
    await callback.message.answer(text)
