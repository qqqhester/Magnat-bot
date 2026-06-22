import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.engine import get_db_connection
from keyboards.inline import get_admin_main, get_admin_back, get_admin_cancel

router = Router()

# Список ID администраторов
ADMIN_IDS = [7014140645]

class AdminStates(StatesGroup):
    waiting_for_tg_id = State()
    waiting_for_money = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def show_admin_dashboard(event: Message | CallbackQuery) -> None:
    """Отрисовка главного экрана управления гейм-мастера."""
    text = (
        "⚡ <b>РЕЖИМ ГЕЙМ-МАСТЕРА</b>\n\n"
        "Добро пожаловать в пульт управления макроэкономикой бота.\n"
        "Здесь вы можете корректировать базу данных «на лету»."
    )
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=get_admin_main())
    else:
        await event.answer(text, reply_markup=get_admin_main())

@router.message(Command("admin"))
async def admin_panel_main(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ Команда не найдена. Возможно, вы ошиблись в написании.")
        return
    await show_admin_dashboard(message)

@router.callback_query(F.data == "admin_main_menu")
async def admin_main_menu_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Возврат в корень панели из любого подменю и сброс состояний ввода."""
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    await state.clear()
    await show_admin_dashboard(callback)

@router.callback_query(F.data == "admin_close")
async def admin_close_panel(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.answer("Пульт управления закрыт.")
    await callback.message.delete()

@router.callback_query(F.data == "admin_give_money")
async def admin_give_money_init(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()
    
    await callback.message.edit_text(
        "👤 <b>ИЗМЕНЕНИЕ БАЛАНСА ИГРОКА</b>\n\n"
        "Введите Telegram ID пользователя, чьи счета нужно скорректировать:",
        reply_markup=get_admin_cancel()
    )
    await state.set_state(AdminStates.waiting_for_tg_id)

@router.message(AdminStates.waiting_for_tg_id)
async def admin_process_tg_id(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
        
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
        await message.answer("❌ Пользователь с таким Telegram ID не найден. Повторите ввод:")
        return

    await state.update_data(target_tg_id=target_id)
    await message.answer(
        f"👤 <b>Игрок найден в системе:</b>\n"
        f"Текущий уровень: <b>{user_row['level']}</b>\n"
        f"Баланс: <b>{user_row['money']:.2f} 💵</b>\n\n"
        f"Введите сумму, которую нужно <b>добавить</b> (для списания укажите минус, например: -500):"
    )
    await state.set_state(AdminStates.waiting_for_money)

@router.message(AdminStates.waiting_for_money)
async def admin_process_money_amount(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        return
        
    try:
        amount = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректное число!")
        return

    state_data = await state.get_data()
    target_id = state_data["target_tg_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET money = max(0.0, money + ?) WHERE tg_id = ?;", 
        (amount, target_id)
    )
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"✅ Баланс игрока <code>{target_id}</code> успешно скорректирован на <b>{amount:+.2f} 💵</b>.\n"
        f"Откройте панель команд заново: /admin"
    )

@router.callback_query(F.data == "admin_market_tick")
async def admin_force_market_tick(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    items = ["bread", "milk", "phones"]
    conn = get_db_connection()
    cursor = conn.cursor()

    for item in items:
        new_modifier = round(random.uniform(0.5, 1.6), 2)
        cursor.execute("""
            INSERT INTO system_market (item_id, demand_modifier)
            VALUES (?, ?)
            ON CONFLICT(item_id) DO UPDATE SET demand_modifier = EXCLUDED.demand_modifier;
        """, (item, new_modifier))

    conn.commit()
    conn.close()

    text = (
        "🔄 <b>ЭКОНОМИЧЕСКИЙ ТИК ВЫПОЛНЕН</b>\n\n"
        "Глобальные индексы спроса успешно пересчитаны.\n"
        "Цены розничных продаж подстроены под новые реалии товарного рынка."
    )
    await callback.message.edit_text(text, reply_markup=get_admin_back())

@router.callback_query(F.data == "admin_server_stats")
async def admin_show_server_stats(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        return
    await callback.answer()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(id) as total_users, SUM(money) as total_cash FROM users;")
    stats = cursor.fetchone()
    
    cursor.execute("SELECT SUM(bread) as b, SUM(milk) as m, SUM(phones) as p FROM warehouse_stock;")
    stock = cursor.fetchone()
    conn.close()

    text = (
        "📊 <b>СЕРВЕРНАЯ СТАТИСТИКА ЭКОНОМИКИ</b>\n\n"
        f"• Всего коммерсантов в базе: <b>{stats['total_users']}</b>\n"
        f"• Суммарная денежная масса: <b>{stats['total_cash']:.2f} 💵</b>\n\n"
        "📦 <b>Всего товаров на складах игроков:</b>\n"
        f"— Хлеб: <b>{stock['b'] or 0} шт.</b>\n"
        f"— Молоко: <b>{stock['m'] or 0} шт.</b>\n"
        f"— Смартфоны: <b>{stock['p'] or 0} шт.</b>"
    )
    await callback.message.edit_text(text, reply_markup=get_admin_back())
