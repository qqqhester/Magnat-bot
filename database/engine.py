import sqlite3
import os

DB_PATH = "matrix_economy.db"

def get_db_connection() -> sqlite3.Connection:
    """Создание соединения с БД и мапингом строк в словари."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

async def init_db() -> None:
    """Создание всех таблиц экосистемы, если они отсутствуют."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Включаем WAL режим для избежания ошибок 'database is locked' при частых тиках
    cursor.execute("PRAGMA journal_mode=WAL;")

    # 1. Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            shop_name TEXT DEFAULT 'Мой первый киоск',
            level INTEGER DEFAULT 1,
            exp INTEGER DEFAULT 0,
            money REAL DEFAULT 100.0,
            crystals INTEGER DEFAULT 0,
            energy INTEGER DEFAULT 40,
            max_energy INTEGER DEFAULT 40,
            reputation INTEGER DEFAULT 10,
            is_ban INTEGER DEFAULT 0,
            last_daily_bonus TEXT,
            last_energy_regen TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Таблица уровней прокачки бизнеса (Улучшения)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            tg_id INTEGER PRIMARY KEY,
            warehouse_level INTEGER DEFAULT 1,
            ad_level INTEGER DEFAULT 1,
            showcase_level INTEGER DEFAULT 1,
            security_level INTEGER DEFAULT 1,
            FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        );
    """)

    # 3. Складские запасы товаров
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS warehouse_stock (
            tg_id INTEGER PRIMARY KEY,
            bread INTEGER DEFAULT 0,
            milk INTEGER DEFAULT 0,
            meat INTEGER DEFAULT 0,
            clothes INTEGER DEFAULT 0,
            phones INTEGER DEFAULT 0,
            contraband INTEGER DEFAULT 0,
            FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        );
    """)

    # 4. Кастомные розничные ценники игроков
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_prices (
            tg_id INTEGER,
            item_id TEXT,
            custom_price REAL,
            is_auto INTEGER DEFAULT 1,
            PRIMARY KEY (tg_id, item_id),
            FOREIGN KEY(tg_id) REFERENCES users(tg_id) ON DELETE CASCADE
        );
    """)

    # 5. Глобальные индексы спроса рынка
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_market (
            item_id TEXT PRIMARY KEY,
            base_price REAL DEFAULT 10.0,
            demand_modifier REAL DEFAULT 1.0,
            last_update TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 6. Система многоразовых/лимитированных промокодов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS promocodes (
            code TEXT PRIMARY KEY,
            reward_type TEXT NOT NULL, -- money, crystals, energy
            reward_value REAL NOT NULL,
            max_activations INTEGER DEFAULT 100,
            current_activations INTEGER DEFAULT 0,
            activated_users TEXT DEFAULT '[]', -- Сюда пишем JSON-массив из tg_id
            expires_at TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()
