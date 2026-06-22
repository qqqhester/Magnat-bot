import asyncio
import logging
import random
import sqlite3
from datetime import datetime
from aiogram import Bot

from database.engine import get_db_connection
from database.queries import check_and_execute_levelup
from utils.economy import calculate_client_interval, check_price_overhead

logger = logging.getLogger("shadow_tycoon_tickers")

BASE_PRICES = {
    "bread": 10.0,
    "milk": 15.0,
    "phones": 200.0
}

ITEM_NAMES_RU = {
    "bread": "Хлеб 🍞",
    "milk": "Молоко 🥛",
    "phones": "Смартфоны 📱"
}

async def energy_regen_ticker() -> None:
    """
    Движок регенерации энергии (AP).
    Каждые 5 минут начисляет игрокам по +1 AP, не превышая их max_energy.
    """
    while True:
        await asyncio.sleep(300)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE users 
                SET energy = MIN(max_energy, energy + 1)
                WHERE energy < max_energy;
            """)
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Ошибка при регенерации энергии: {e}")
        finally:
            conn.close()

async def market_ticker() -> None:
    """
    Авто-Тик глобального рынка.
    Каждые 30 минут случайным образом меняет коэффициенты спроса (demand_modifier) в диапазоне [0.6, 1.6].
    """
    while True:
        await asyncio.sleep(1800)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT item_id FROM system_market;")
            items = cursor.fetchall()
            
            cursor.execute("BEGIN TRANSACTION;")
            for item in items:
                new_mod = round(random.uniform(0.6, 1.6), 2)
                cursor.execute(
                    "UPDATE system_market SET demand_modifier = ? WHERE item_id = ?;",
                    (new_mod, item["item_id"])
                )
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"Ошибка при обновлении котировок рынка: {e}")
        finally:
            conn.close()

async def buyer_simulation_ticker(bot: Bot) -> None:
    """
    Движок симуляции покупателей (Продажи).
    Каждую минуту проверяет всех игроков на наступление таймера прихода клиента.
    """
    while True:
        await asyncio.sleep(60)
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT u.*, ws.bread, ws.milk, ws.phones, ws.contraband 
                FROM users u
                JOIN warehouse_stock ws ON u.tg_id = ws.tg_id;
            """)
            users = cursor.fetchall()
            
            now_ts = int(datetime.now().timestamp())
            
            for user in users:
                tg_id = user["tg_id"]
                interval = calculate_client_interval(user["reputation"], user["ad_level"])
                
                if now_ts - user["last_client_time"] < interval:
                    continue
                    
                available_items = []
                if user["bread"] > 0: available_items.append("bread")
                if user["milk"] > 0: available_items.append("milk")
                if user["phones"] > 0: available_items.append("phones")
                
                if not available_items:
                    cursor.execute("UPDATE users SET last_client_time = ? WHERE tg_id = ?;", (now_ts, tg_id))
                    continue
                    
                chosen_item = random.choice(available_items)
                
                cursor.execute("SELECT demand_modifier FROM system_market WHERE item_id = ?;", (chosen_item,))
                market_row = cursor.fetchone()
                demand_mod = market_row["demand_modifier"] if market_row else 1.0
                
                cursor.execute("SELECT custom_price FROM user_prices WHERE tg_id = ? AND item_id = ?;", (tg_id, chosen_item))
                price_row = cursor.fetchone()
                
                base_price = BASE_PRICES.get(chosen_item, 10.0)
                if not price_row or price_row["custom_price"] is None:
                    showcase_boost = 1.0 + (user["showcase_level"] - 1) * 0.05
                    final_price = round(base_price * demand_mod * showcase_boost, 2)
                    is_overpriced = False
                else:
                    final_price = price_row["custom_price"]
                    check = check_price_overhead(final_price, base_price, demand_mod)
                    is_overpriced = check["is_overpriced"]

                cursor.execute("BEGIN TRANSACTION;")
                
                if is_overpriced:
                    cursor.execute("""
                        UPDATE users 
                        SET reputation = MAX(0, reputation - 2), last_client_time = ? 
                        WHERE tg_id = ?;
                    """, (now_ts, tg_id))
                    conn.commit()
                    
                    try:
                        await bot.send_message(
                            tg_id,
                            f"🚷 <b>Покупатель ушел без покупки!</b>\n\n"
                            f"Его возмутила цена на {ITEM_NAMES_RU[chosen_item]} (<b>{final_price:.2f} 💵</b>).\n"
                            f"Вы получили <b>-2 очка авторитета</b> за попытку спекуляции сверх лимита."
                        )
                    except Exception:
                        pass
                else:
                    cursor.execute(
                        f"UPDATE warehouse_stock SET {chosen_item} = {chosen_item} - 1 WHERE tg_id = ?;",
                        (tg_id,)
                    )
                    cursor.execute("""
                        UPDATE users 
                        SET money = money + ?, exp = exp + 10, last_client_time = ? 
                        WHERE tg_id = ?;
                    """, (final_price, now_ts, tg_id))
                    conn.commit()
                    
                    lvl_check = check_and_execute_levelup(tg_id)
                    
                    try:
                        if lvl_check and lvl_check["leveled_up"]:
                            await bot.send_message(
                                tg_id,
                                f"🔥 <b>LEVEL UP! ВЫ ПЕРЕШЛИ НА НОВЫЙ УРОВЕНЬ!</b> 🔥\n\n"
                                f"📈 Теперь ваш уровень: <b>{lvl_check['new_level']}</b>\n"
                                f"⚡ Лимит энергии увеличен до: <b>{lvl_check['max_energy']} AP</b>\n"
                                f"🔋 Энергия полностью восстановлена!"
                            )
                        else:
                            await bot.send_message(
                                tg_id,
                                f"💰 <b>Успешная продажа!</b>\n\n"
                                f"Клиент приобрел {ITEM_NAMES_RU[chosen_item]} за <b>{final_price:.2f} 💵</b>.\n"
                                f"Получено: <b>+10 EXP</b> 📈"
                            )
                    except Exception:
                        pass

        except sqlite3.Error as e:
            if conn.in_transaction:
                conn.rollback()
            logger.error(f"Критическая ошибка в симуляторе продаж: {e}")
        finally:
            conn.close()
