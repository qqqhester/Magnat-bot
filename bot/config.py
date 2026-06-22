import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # Парсим ID админов из строки через запятую в список целых чисел
    ADMIN_IDS: list[int] = [
        int(admin_id.strip()) 
        for admin_id in os.getenv("ADMIN_IDS", "").split(",") 
        if admin_id.strip().isdigit()
    ]
    
    DB_PATH: str = os.getenv("DB_PATH", "shadow_tycoon.db")

settings = Settings()
