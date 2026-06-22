import sqlite3
from database.engine import get_db_connection

def register_user_if_not_exists(tg_id: int, username: str | None) -> bool:
    """Регистрирует игрока и создает ему связанные таблицы. Возвращает True, если новый."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT tg_id FROM users WHERE tg_id = ?;", (tg_id,))
    if cursor.fetchone():
        conn.close()
        return False
        
    try:
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("INSERT INTO users (tg_id, username) VALUES (?, ?);", (tg_id, username))
        cursor.execute("INSERT INTO inventory (tg_id) VALUES (?);", (tg_id,))
        cursor.execute("INSERT INTO warehouse_stock (tg_id) VALUES (?);", (tg_id,))
        conn.commit()
        return True
    except sqlite3.Error:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_full_profile(tg_id: int) -> sqlite3.Row | None:
    """Агрегирует данные игрока, его складов и апгрейдов одним JOIN-запросом."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, i.warehouse_level, i.ad_level, i.showcase_level, i.security_level,
               w.bread, w.milk, w.meat, w.clothes, w.phones, w.contraband
        FROM users u
        JOIN inventory i ON u.tg_id = i.tg_id
        JOIN warehouse_stock w ON u.tg_id = w.tg_id
        WHERE u.tg_id = ?;
    """, (tg_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_shop_name(tg_id: int, new_name: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET shop_name = ? WHERE tg_id = ?;", (new_name, tg_id))
    conn.commit()
    conn.close()

def buy_goods(tg_id: int, item_field: str, count: int, total_cost: float) -> None:
    """Атомарная транзакция B2B закупки: списывает cash/AP, добавляет товар, начисляет опыт."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN TRANSACTION;")
        # Списание денег и энергии + выдача 5 XP за коммерческую сделку
        cursor.execute("""
            UPDATE users 
            SET money = money - ?, 
                energy = max(0, energy - 1),
                exp = exp + 5 
            WHERE tg_id = ?;
        """, (total_cost, tg_id))
        
        # Наполнение склада
        cursor.execute(f"UPDATE warehouse_stock SET {item_field} = {item_field} + ? WHERE tg_id = ?;", (count, tg_id))
        
        # Проверка триггера уровня (Level Up) при ручной закупке
        cursor.execute("SELECT level, exp, max_energy FROM users WHERE tg_id = ?;", (tg_id,))
        user = cursor.fetchone()
        if user:
            exp_needed = 100 * (user["level"] ** 2)
            if user["exp"] >= exp_needed:
                new_level = user["level"] + 1
                new_max_energy = user["max_energy"] + 5
                cursor.execute("""
                    UPDATE users 
                    SET level = ?, 
                        exp = exp - ?, 
                        max_energy = ?, 
                        energy = ? 
                    WHERE tg_id = ?;
                """, (new_level, exp_needed, new_max_energy, new_max_energy, tg_id))
                
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
    finally:
        conn.close()

def check_and_execute_levelup(tg_id: int) -> dict | None:
    """
    Проверяет, набрал ли игрок достаточно опыта для Level Up (для фоновых процессов).
    Если да — повышает уровень, увеличивает лимит энергии (+5 за уровень),
    полностью восстанавливает её и возвращает новые параметры.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT level, exp, max_energy FROM users WHERE tg_id = ?;", (tg_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return None
        
    current_level = user["level"]
    current_exp = user["exp"]
    
    required_exp = 100 * (max(1, current_level) ** 2)
    
    if current_exp >= required_exp:
        new_level = current_level + 1
        new_max_energy = user["max_energy"] + 5
        leftover_exp = current_exp - required_exp
        
        cursor.execute("BEGIN TRANSACTION;")
        cursor.execute("""
            UPDATE users 
            SET level = ?, 
                exp = ?, 
                max_energy = ?, 
                energy = ?
            WHERE tg_id = ?;
        """, (new_level, leftover_exp, new_max_energy, new_max_energy, tg_id))
        conn.commit()
        conn.close()
        
        return {"leveled_up": True, "new_level": new_level, "max_energy": new_max_energy}
        
    conn.close()
    return {"leveled_up": False}
