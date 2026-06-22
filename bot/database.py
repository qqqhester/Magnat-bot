import sqlite3
import json
from datetime import datetime

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
        total_earned INTEGER DEFAULT 0,
        achievements TEXT DEFAULT '[]',
        daily_quests TEXT DEFAULT '[]',
        weekly_quests TEXT DEFAULT '[]'
    )
    ''')
    conn.commit()

def get_user(tg_id):
    cursor.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
    return cursor.fetchone()

def update_user(tg_id, column, value):
    cursor.execute(f"UPDATE users SET {column} = ? WHERE tg_id = ?", (value, tg_id))
    conn.commit()

def add_exp(tg_id, amount):
    user = get_user(tg_id)
    if not user:
        return
    new_exp = user[6] + amount
    exp_needed = user[5] * 50
    if new_exp >= exp_needed:
        new_exp = 0
        new_level = user[5] + 1
        update_user(tg_id, "level", new_level)
        update_user(tg_id, "money", user[2] + new_level * 20)
        update_user(tg_id, "exp", 0)
    else:
        update_user(tg_id, "exp", new_exp)
