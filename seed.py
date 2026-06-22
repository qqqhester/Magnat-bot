import sqlite3
import json
import asyncio
from datetime import datetime, timedelta
from database.engine import init_db, get_db_connection

async def seed_system_data():
    # 1. Создаем таблицы, если их нет
    await init_db()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 2. Заливаем базовые товары на глобальный рынок
    # Это нужно, чтобы хэндлеры не ловили None до первого тика таймера
    default_market = [
        ("bread", 5.0, 1.0),
        ("milk", 12.0, 1.0),
        ("phones", 150.0, 1.0)
    ]
    
    cursor.executemany("""
        INSERT INTO system_market (item_id, base_price, demand_modifier, last_update)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(item_id) DO NOTHING;
    """, default_market)
    
    # 3. Генерируем тестовый промокод для проверки (Действует 7 дней)
    expiry_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO promocodes (code, reward_type, reward_value, max_activations, current_activations, activated_users, expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code) DO NOTHING;
    """, ("START2026", "money", 250.0, 50, 0, "[]", expiry_date))
    
    conn.commit()
    conn.close()
    print("✅ База данных успешно инициализирована и заполнена стартовыми котировками!")
    print("🎁 Добавлен тестовый промокод: START2026 (Дает 250.0 💵)")

if __name__ == "__main__":
    asyncio.run(seed_system_data())
