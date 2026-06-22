import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from config import settings
from database.engine import init_db

# Срезы фоновых задач и хэндлеров (будут созданы на следующих этапах)
# Импортируем роутеры. Если файлы еще не созданы, при первом запуске
# после сборки папок эти импорты встанут как влитые.
try:
    from handlers import admin, profile, shop, market, rivals
    from middlewares.throttling import ThrottlingMiddleware
    from middlewares.auth import AuthMiddleware
    from utils.tickers import market_ticker, buyer_simulation_ticker
except ImportError:
    # Заглушка для первоначального теста корня, пока папки не созданы
    admin = profile = shop = market = rivals = None
    ThrottlingMiddleware = AuthMiddleware = None
    market_ticker = buyer_simulation_ticker = None

async def main() -> None:
    # Настройка логирования в stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s (%(filename)s:%(lineno)d)",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)

    logger.info("Инициализация XUI-Матрицы: запуск ядра базы данных...")
    await init_db()

    # Проверка токена
    if not settings.BOT_TOKEN:
        logger.critical("BOT_TOKEN отсутствует в .env! Работа системы остановлена.")
        return

    # Инициализация бота и диспетчера (хранилище FSM в памяти)
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация Middlewares (Защита от флуда и проверка банов)
    if ThrottlingMiddleware and AuthMiddleware:
        dp.message.middleware(AuthMiddleware())
        dp.callback_query.middleware(AuthMiddleware())
        dp.message.middleware(ThrottlingMiddleware())
        logger.info("Системные Middlewares успешно интегрированы.")
    else:
        logger.warning("Middlewares пропущены: файлы еще не созданы.")

    # Подключение роутеров из архитектурных слоев
    if all([admin, profile, shop, market, rivals]):
        dp.include_routers(
            admin.router,
            profile.router,
            shop.router,
            market.router,
            rivals.router
        )
        logger.info("Маршрутизация команд и текстовых алиасов успешно настроена.")
    else:
        logger.warning("Хэндлеры пропущены: слои интерфейса еще не созданы.")

    # Запуск автономных фоновых движков (Рынок и Покупатели)
    if market_ticker and buyer_simulation_ticker:
        asyncio.create_task(market_ticker())
        asyncio.create_task(buyer_simulation_ticker())
        logger.info("Фоновые асинхронные тикеры микроэкономики запущены.")
    else:
        logger.warning("Фоновые процессы пропущены: модуль utils/tickers.py не найден.")

    logger.info("Бот «Теневой Магнат» успешно переведен в режим Production Polling.")
    
    try:
        # Пропускаем накопившиеся апдейты перед стартом
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception(f"Критический сбой при работе поллинга: {e}")
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта. Экосистема остановлена.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Система принудительно остановлена пользователем.")
