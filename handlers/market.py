import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.engine import get_db_connection
from database.queries import get_full_profile
from keyboards.inline import get_market_inline

router = Router()

# Справочник названий для красивого вывода
ITEM_NAMES = {
    "bread": "Хлеб 🍞",
    "milk": "Молоко 🥛",
    "phones": "Смартфоны 📱"
}

@router.message(F.text.lower().in_(["📊 спрос", "ценны", "рынок", "котировки"]))
async def show_demand(message: Message) -> None:
    """Вывод актуальных коэффициентов спроса из таблицы system_market."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Извлекаем текущее состояние глобального рынка
    cursor.execute("SELECT item_id, demand_modifier FROM system_market;")
    rows = cursor.fetchall()
    conn.close()

    # Мапим индексы в читаемый вид
    market_data = {row["item_id"]: row["demand_modifier"] for row in rows}
    
    # Если в базе еще нет записей (до первого тика), ставим дефолт 1.0
    demand_bread = market_data.get("bread", 1.0)
    demand_milk = market_data.get("milk", 1.0)
    demand_phones = market_data.get("phones", 1.0)

    def get_status_emoji(mod: float) -> str:
        if mod < 0.9: return "(Низкий спрос 📉)"
        if mod > 1.2: return "(⚠️ ВЫСОКИЙ СПРОС! Покупатели переплачивают)"
        return "(Стабильно ⚖️)"

    text = (
        "🕒 <b>АНАЛИТИЧЕСКИЙ СРЕЗ РЫНКА</b>\n"
        "<i>Котировки обновляются автоматически фоновым движком.</i>\n\n"
        "📈 <b>Текущие индексы спроса на товары:</b>\n"
        f"• Хлеб: Коэф. <b>{demand_bread:.2f}</b> {get_status_emoji(demand_bread)}\n"
        f"• Молоко: Коэф. <b>{demand_milk:.2f}</b> {get_status_emoji(demand_milk)}\n"
        f"• Смартфоны: Коэф. <b>{demand_phones:.2f}</b> {get_status_emoji(demand_phones)}\n"
    )

    await message.answer(text, reply_markup=get_market_inline())

@router.callback_query(F.data == "market_analyst_tip")
async def process_analyst_tip(callback: CallbackQuery) -> None:
    """Платный совет: списывает 5 AP, находит лучший товар на складе для продажи."""
    tg_id = callback.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    # Проверка лимита энергии
    if profile["energy"] < 5:
        await callback.answer(
            "娱乐 ⛔ Недостаточно энергии! Для совета аналитика требуется 5 AP.", 
            show_alert=True
        )
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Списываем 5 единиц энергии
    cursor.execute("UPDATE users SET energy = energy - 5 WHERE tg_id = ?;", (tg_id,))
    
    # Берем котировки рынка
    cursor.execute("SELECT item_id, demand_modifier FROM system_market;")
    market_rows = cursor.fetchall()
    conn.close()
    
    if not market_rows:
        await callback.answer("Рынок пуст, аналитики разводят руками.", show_alert=True)
        return
        
    # Находим товар с максимальным коэффициентом спроса
    best_item = max(market_rows, key=lambda x: x["demand_modifier"])
    item_id = best_item["item_id"]
    modifier = best_item["demand_modifier"]
    
    item_name_ru = ITEM_NAMES.get(item_id, item_id)
    
    conn.commit() # Фиксируем трату энергии
    
    # Выдаем результат в формате alert-поп-апа
    alert_text = (
        f"💡 ИНСАЙД АНАЛИТИКА:\n\n"
        f"Сливай {item_name_ru} прямо сейчас!\n"
        f"Его индекс спроса равен {modifier:.2f}. "
        f"Покупатели готовы переплачивать!"
    )
    await callback.answer(text=alert_text, show_alert=True)
