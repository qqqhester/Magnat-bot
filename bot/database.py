import sqlite3

conn = sqlite3.connect("magnat.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        tg_id INTEGER PRIMARY KEY,
        username TEXT,
        money INTEGER DEFAULT 100,
        crystals INTEGER DEFAULT 0,
        reputation INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        exp INTEGER DEFAULT 0,
        shop_level INTEGER DEFAULT 1,
        workers INTEGER DEFAULT 0,
        houses INTEGER DEFAULT 0,
        cars TEXT DEFAULT '[]',
        last_bonus TIMESTAMP DEFAULT '1970-01-01 00:00:00',
        total_earned INTEGER DEFAULT 0
    )
    ''')
    conn.commit()

def get_user(tg_id):
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return cursor.fetchone()

def update_user(tg_id, column, value):
    cursor.execute(f"UPDATE users SET {column} = ? WHERE tg_id = ?", (value, tg_id))
    conn.commit()
