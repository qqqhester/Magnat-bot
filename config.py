import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    DB_NAME: str = "matrix_economy.db"

settings = Settings()
