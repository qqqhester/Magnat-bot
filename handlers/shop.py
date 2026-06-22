import math
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from database.queries import get_full_profile, buy_goods, get_db_connection
from utils.economy import get_warehouse_capacity
from keyboards.inline import get_b2b_shop_main, get_buy_volume_keyboard

router = Router()

# Жесткая конфигурация товаров из ТЗ
ITEMS_CONFIG = {
    "bread": {"name": "Хлеб", "level": 1, "price": 5.0},
    "milk": {"name": "Молоко", "level": 2, "price": 12.0},
    "phones": {"name": "Смартфоны", "level": 5, "price": 150.0}
}

class ShopStates(StatesGroup):
    input_custom_price = State()

@router.message(F.text.lower().in_(["🏪 магазин b2b", "b2b", "магаз", "закуп"]))
async def open_shop(message: Message) -> None:
    """Главный экран управления торговой точкой и складом."""
    tg_id = message.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        return

    # Подсчет текущих запасов
    total_stock = (
        profile["bread"] + profile["milk"] + profile["meat"] + 
        profile["clothes"] + profile["phones"] + profile["contraband"]
    )
    capacity = get_warehouse_capacity(profile["warehouse_level"])
    free_slots = max(0, capacity - total_stock)

    text = (
        "📦 <b>УПРАВЛЕНИЕ ТОРГОВОЙ ТОЧКОЙ</b>\n\n"
        f"Склад: <b>{total_stock}/{capacity} ед.</b>\n"
        f"Свободно мест: <b>{free_slots} ед.</b>\n\n"
        "Доступные операции: закупка сырья у поставщиков, расширение "
        "логистических мощностей и наем персонала. Нажмите соответствующую кнопку."
    )
    await message.answer(text, reply_markup=get_b2b_shop_main())

@router.callback_query(F.data == "shop_buy_goods")
async def shop_buy_goods_menu(callback: CallbackQuery) -> None:
    """Вывод списка доступных товаров на основе уровня игрока."""
    await callback.answer()
    tg_id = callback.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        return

    user_level = profile["level"]
    builder = InlineKeyboardBuilder()

    text = "📦 <b>ДОСТУПНЫЕ ТОВАРЫ ДЛЯ ЗАКУПКИ:</b>\n\n"
    
    for item_id, info in ITEMS_CONFIG.items():
        if user_level >= info["level"]:
            # Игрок проходит по уровню
            current_stock = profile[item_id]
            text += f"• <b>{info['name']}</b> | Закупка: {info['price']} 💵 | На складе: {current_stock} шт.\n"
            builder.row(InlineKeyboardButton(
                text=f"Закупить {info['name']} ({info['price']} 💵)", 
                callback_data=f"buy_select:{item_id}:1" # По умолчанию объем = 1
            ))
        else:
            # Товар заблокирован
            text += f"🔒 <i>{info['name']} (Доступен с {info['level']} ур.)</i>\n"

    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="shop_back_to_main"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("buy_select:"))
async def shop_deal_screen(callback: CallbackQuery) -> None:
    """Экран конкретной сделки с калькулятором объемов."""
    await callback.answer()
    _, item_id, volume_str = callback.data.split(":")
    tg_id = callback.from_user.id
    
    profile = get_full_profile(tg_id)
    if not profile or item_id not in ITEMS_CONFIG:
        return

    info = ITEMS_CONFIG[item_id]
    base_price = info["price"]
    
    # Расчет лимитов склада
    total_stock = (
        profile["bread"] + profile["milk"] + profile["meat"] + 
        profile["clothes"] + profile["phones"] + profile["contraband"]
    )
    capacity = get_warehouse_capacity(profile["warehouse_level"])
    free_slots = max(0, capacity - total_stock)
    
    # Расчет максимального объема закупки
    max_by_money = math.floor(profile["money"] / base_price)
    max_volume = min(max_by_money, free_slots)
    if max_volume < 0:
        max_volume = 0

    # Обработка объема
    if volume_str == "max":
        volume = max_volume
    else:
        volume = int(volume_str)

    total_cost = volume * base_price

    text = (
        f"📱 <b>Закупка: {info['name']}</b>\n"
        f"Текущая цена партии: <b>{base_price:.2f} 💵</b> за ед.\n"
        f"Доступно кэша: <b>{profile['money']:.2f} 💵</b>\n"
        f"Свободно мест на складе: <b>{free_slots} ед.</b>\n\n"
        f"Выбранный объем: <b>{volume} шт.</b>\n"
        f"Итоговая стоимость партии: <b>{total_cost:.2f} 💵</b>\n\n"
        "Выберите объем закупки (Управляется кнопками):"
    )

    # Динамическая пересборка инлайн-кнопок под текущий объем
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="+1", callback_data=f"buy_select:{item_id}:{min(max_volume, volume + 1)}"),
        InlineKeyboardButton(text="+10", callback_data=f"buy_select:{item_id}:{min(max_volume, volume + 10)}"),
        InlineKeyboardButton(text="МАКС", callback_data=f"buy_select:{item_id}:max")
    )
    builder.row(InlineKeyboardButton(text="✅ Подтвердить Сделку", callback_data=f"buy_execute:{item_id}:{volume}"))
    builder.row(InlineKeyboardButton(text="⚙️ Настроить Свою Цену", callback_data=f"price_config:{item_id}"))
    builder.row(InlineKeyboardButton(text="⬅️ К списку товаров", callback_data="shop_buy_goods"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("buy_execute:"))
async def shop_execute_deal(callback: CallbackQuery) -> None:
    _, item_id, volume_str = callback.data.split(":")
    volume = int(volume_str)
    tg_id = callback.from_user.id
    
    profile = get_full_profile(tg_id)
    if not profile or volume <= 0:
        await callback.answer("❌ Выберите корректный объем товара!", show_alert=True)
        return

    # Проверка AP
    if profile["energy"] < 1:
        await callback.answer(
            "⛔ Усталость сковала движения. Твой персонаж истощен (0 AP). "
            "Дождись регенерации энергии или забери суточную долю в меню 'Активация'.",
            show_alert=True
        )
        return

    info = ITEMS_CONFIG[item_id]
    total_cost = volume * info["price"]

    # Проверка денег
    if profile["money"] < total_cost:
        await callback.answer("❌ Недостаточно средств для проведения сделки!", show_alert=True)
        return

    # Проверка емкости склада
    total_stock = (
        profile["bread"] + profile["milk"] + profile["meat"] + 
        profile["clothes"] + profile["phones"] + profile["contraband"]
    )
    capacity = get_warehouse_capacity(profile["warehouse_level"])
    if total_stock + volume > capacity:
        await callback.answer(
            "📦 Склад забит до отказа! Логисты отказываются принимать товар. "
            "Повысь уровень склада в меню улучшений или дождись автоматической розничной продажи.",
            show_alert=True
        )
        return

    # Проведение атомарной транзакции в БД
    buy_goods(tg_id, item_field=item_id, count=volume, total_cost=total_cost)
    
    await callback.answer("🎉 Сделка успешно заключена! Товар на складе.", show_alert=True)
    # Возвращаем пользователя в главное меню магазина
    await callback.message.delete()
    await open_shop(callback.message)

@router.callback_query(F.data.startswith("price_config:"))
async def shop_price_config_init(callback: CallbackQuery, state: FSMContext) -> None:
    """Перевод игрока в режим FSM для изменения розничной цены."""
    await callback.answer()
    _, item_id = callback.data.split(":")
    
    await state.update_data(target_item_id=item_id)
    await callback.message.answer(
        f"⚙️ <b>Настройка цены для позиции: {ITEMS_CONFIG[item_id]['name']}</b>\n"
        f"Введите желаемую розничную стоимость за 1 единицу (целое или дробное число).\n\n"
        "<i>Внимание: Если цена превысит рыночную более чем на 20%, вы начнете терять авторитет. "
        "Если превысит на 50% — шанс покупки упадет до 5%.</i>"
    )
    await state.set_state(ShopStates.input_custom_price)

@router.message(ShopStates.input_custom_price)
async def shop_price_config_process(message: Message, state: FSMContext) -> None:
    """Валидация и сохранение кастомной цены в БД."""
    raw_price = message.text.replace(",", ".").strip()
    
    try:
        custom_price = float(raw_price)
        if custom_price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите корректное положительное число!")
        return

    state_data = await state.get_data()
    item_id = state_data["target_item_id"]
    tg_id = message.from_user.id

    # Сохраняем цену в таблицу user_prices, отключая авторежим ценообразования (is_auto=0)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_prices (tg_id, item_id, custom_price, is_auto)
        VALUES (?, ?, ?, 0)
        ON CONFLICT(tg_id, item_id) DO UPDATE SET
            custom_price = EXCLUDED.custom_price,
            is_auto = 0;
    """, (tg_id, item_id, custom_price))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(
        f"✅ Розничная цена на <b>{ITEMS_CONFIG[item_id]['name']}</b> успешно зафиксирована на отметке <b>{custom_price:.2f} 💵</b>.\n"
        "Автоматическое ценообразование отключено."
    )

@router.callback_query(F.data == "shop_back_to_main")
async def shop_back_to_main(callback: CallbackQuery) -> None:
    """Возврат из подменю товаров на главный экран магазина."""
    await callback.answer()
    await callback.message.delete()
    await open_shop(callback.message)
