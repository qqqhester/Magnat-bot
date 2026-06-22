import asyncio
import random
import logging
import sqlite3
from datetime import datetime
from aiogram import Bot
from database.engine import get_db_connection
from utils.economy import calculate_client_interval, get_final_price

logger = logging.getLogger(__name__)

async def market_ticker() -> None:
    """
    Фоновый цикл обновления глобального рынка.
    Каждые 30 минут случайным образом меняет коэффициенты спроса на товары.
    """
    items = ["bread", "milk", "meat", "clothes", "phones"]
    while True:
        try:
            await asyncio.sleep(1800) # 30 минут
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Проверяем, не запущен ли глобальный кризис админом (когда у всех 0.5)
            cursor.execute("SELECT demand_modifier FROM system_market WHERE item_id = 'bread';")
            row = cursor.fetchone()
            if row and row["demand_modifier"] == 0.5:
                # Если идет форсированный кризис, не перебиваем его случайным тиком
                conn.close()
                continue

            for item in items:
                # Случайный коэффициент спроса от 0.7 (низкий) до 1.5 (высокий бум)
                new_modifier = round(random.uniform(0.7, 1.5), 2)
                cursor.execute("""
                    INSERT INTO system_market (item_id, base_price, demand_modifier, last_update)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(item_id) DO UPDATE SET 
                        demand_modifier = EXCLUDED.demand_modifier,
                        last_update = CURRENT_TIMESTAMP;
                """, (item, 10.0 if item == "bread" else 25.0, new_modifier)) # условная базовая цена
                
            conn.commit()
            conn.close()
            logger.info("Глобальные котировки рынка успешно обновлены.")
        except Exception as e:
            logger.error(f"Ошибка в market_ticker: {e}")
            await asyncio.sleep(5)

async def buyer_simulation_ticker(bot: Bot) -> None:
    """
    Служба розничных покупателей. 
    Каждые 30 секунд проверяет активных игроков и симулирует приход клиентов.
    """
    while True:
        try:
            await asyncio.sleep(30)
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Извлекаем данные всех незабаненных игроков, у которых есть хоть какой-то товар
            cursor.execute("""
                SELECT u.tg_id, u.username, u.reputation, u.money,
                       i.ad_level, i.showcase_level,
                       w.bread, w.milk, w.meat, w.clothes, w.phones
                FROM users u
                JOIN inventory i ON u.tg_id = i.tg_id
                JOIN warehouse_stock w ON u.tg_id = w.tg_id
                WHERE u.is_ban = 0;
            """)
            players = cursor.fetchall()
            
            for player in players:
                tg_id = player["tg_id"]
                
                # Расчет индивидуального интервала прихода клиента
                interval = calculate_client_interval(player["reputation"], player["ad_level"])
                
                # Вероятность того, что клиент совершит покупку именно в этот 30-секундный тик
                if random.randint(1, 100) > (30 / interval * 100):
                    continue
                
                # Собираем список доступных легальных товаров на складе игрока
                stock = {
                    "bread": player["bread"], "milk": player["milk"],
                    "meat": player["meat"], "clothes": player["clothes"], "phones": player["phones"]
                }
                available_items = [item for item, count in stock.items() if count > 0]
                
                if not available_items:
                    # Склад пуст. Если запущена реклама (ad_level > 1), игрок теряет репутацию
                    if player["ad_level"] > 1:
                        cursor.execute("UPDATE users SET reputation = max(0, reputation - 1) WHERE tg_id = ?;", (tg_id,))
                        try:
                            await bot.send_message(
                                tg_id, 
                                "📉 Клиент ушел ни с чем. Вы теряете репутацию из-за пустого склада!"
                            )
                        except Exception:
                            pass
                    continue
                
                # Выбираем случайный товар из тех, что есть в наличии
                chosen_item = random.choice(available_items)
                
                # Получаем рыночные параметры товара
                cursor.execute("SELECT base_price, demand_modifier FROM system_market WHERE item_id = ?;", (chosen_item,))
                market_row = cursor.fetchone()
                base_price = market_row["base_price"] if market_row else 20.0
                demand_mod = market_row["demand_modifier"] if market_row else 1.0
                
                # Получаем кастомную цену игрока
                cursor.execute("SELECT custom_price, is_auto FROM user_prices WHERE tg_id = ? AND item_id = ?;", (tg_id, chosen_item))
                price_row = cursor.fetchone()
                
                is_auto = price_row["is_auto"] if price_row else 1
                custom_price = price_row["custom_price"] if price_row else None
                
                # Вычисляем финальную стоимость продажи
                final_price = get_final_price(is_auto, custom_price, base_price, player["showcase_level"], demand_mod)
                
                # Проверка жестких экономических ограничений из ТЗ
                purchase_allowed = True
                if is_auto == 0 and custom_price:
                    # Если цена завышена более чем на 50%, шанс покупки падает до 5%
                    if custom_price > (base_price * 1.5) and random.randint(1, 100) > 5:
                        purchase_allowed = False
                    # Если превышает рынок на 20% — штраф к репутации за каждую продажу
                    elif custom_price > (base_price * 1.2):
                        cursor.execute("UPDATE users SET reputation = max(0, reputation - 2) WHERE tg_id = ?;", (tg_id,))
                
                if not purchase_allowed:
                    continue
                
                # Проводим транзакцию продажи 1 единицы товара
                cursor.execute(f"UPDATE warehouse_stock SET {chosen_item} = {chosen_item} - 1 WHERE tg_id = ?;", (tg_id,))
                cursor.execute("UPDATE users SET money = money + ? WHERE tg_id = ?;", (final_price, tg_id))
                
                item_names_ru = {"bread": "Хлеб", "milk": "Молоко", "meat": "Мясо", "clothes": "Одежду", "phones": "Смартфоны"}
                
                try:
                    await bot.send_message(
                        tg_id,
                        f"🛒 Покупатель приобрел {item_names_ru[chosen_item]} за {final_price} 💵!\n"
                        f"Твоя чистая прибыль: +{final_price} 💵"
                    )
                except Exception:
                    pass
                    
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Ошибка в buyer_simulation_ticker: {e}")
            await asyncio.sleep(5)
