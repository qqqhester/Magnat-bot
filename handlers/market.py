import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from database.engine import get_db_connection
from database.queries import get_full_profile
from keyboards.inline import get_market_inline

router = Router()

ITEM_NAMES = {
    "bread": "Хлеб 🍞",
    "milk": "Молоко 🥛",
    "phones": "Смартфоны 📱"
}

async def render_market_screen(message: Message, edit: bool = False) -> None:
    """Рендеринг аналитического среза рынка."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT item_id, demand_modifier FROM system_market;")
    rows = cursor.fetchall()
    conn.close()

    market_data = {row["item_id"]: row["demand_modifier"] for row in rows}
    
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

    if edit:
        await message.edit_text(text, reply_markup=get_market_inline())
    else:
        await message.answer(text, reply_markup=get_market_inline())

@router.message(F.text.lower().in_(["📊 спрос", "ценны", "рынок", "котировки"]))
async def show_demand(message: Message) -> None:
    await render_market_screen(message, edit=False)

@router.callback_query(F.data == "market_refresh")
async def refresh_market_callback(callback: CallbackQuery) -> None:
    """Обновление котировок по кнопке."""
    await callback.answer("🔄 Данные рынка обновлены!")
    await render_market_screen(callback.message, edit=True)

@router.callback_query(F.data == "market_analyst_tip")
async def process_analyst_tip(callback: CallbackQuery) -> None:
    """Платный совет аналитика."""
    tg_id = callback.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        await callback.answer("Профиль не найден.", show_alert=True)
        return

    if profile["energy"] < 5:
        await callback.answer("⛔ Недостаточно энергии! Требуется 5 AP.", show_alert=True)
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Тратим энергию
    cursor.execute("UPDATE users SET energy = energy - 5 WHERE tg_id = ?;", (tg_id,))
    cursor.execute("SELECT item_id, demand_modifier FROM system_market;")
    market_rows = cursor.fetchall()
    
    if not market_rows:
        conn.close()
        await callback.answer("Рынок пуст, аналитики разводят руками.", show_alert=True)
        return
        
    best_item = max(market_rows, key=lambda x: x["demand_modifier"])
    item_id = best_item["item_id"]
    modifier = best_item["demand_modifier"]
    
    conn.commit()
    conn.close()
    
    item_name_ru = ITEM_NAMES.get(item_id, item_id)
    
    alert_text = (
        f"💡 ИНСАЙД АНАЛИТИКА:\n\n"
        f"Сливай {item_name_ru} прямо сейчас!\n"
        f"Его индекс спроса равен {modifier:.2f}. "
        f"Покупатели готовы переплачивать!"
    )
    # Показываем инсайд алертом, сообщение рынка оставляем целым
    await callback.answer(text=alert_text, show_alert=True)
