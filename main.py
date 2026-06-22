import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode

from config import settings
from database.engine import init_db
from handlers import router as main_router
from middlewares.throttling import ThrottlingMiddleware
from middlewares.auth import AuthMiddleware
from utils.tickers import market_ticker, buyer_simulation_ticker, energy_regen_ticker

async def main() -> None:
    # Конфигурация логирования в stdout
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger("shadow_tycoon_core")

    logger.info("Старт ядра... Развертывание реляционных таблиц (WAL режим)...")
    await init_db()

    # Инициализация компонентов aiogram 3.x
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация Middlewares (Безопасность и Anti-Spam)
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(ThrottlingMiddleware(throttle_time=1.0))
    logger.info("Защитный слой Middlewares успешно активирован.")

    # Подключение единого роутера маршрутизации
    dp.include_router(main_router)
    logger.info("Монолитная XUI-маршрутизация успешно развернута.")

    # Запуск автономных фоновых движков микроэкономики
    asyncio.create_task(market_ticker())
    asyncio.create_task(buyer_simulation_ticker(bot=bot))
    asyncio.create_task(energy_regen_ticker())
    logger.info("Все фоновые асинхронные службы запущены штатно.")

    logger.info("Бот «Теневой Магнат» заступил на дежурство. Ожидание апдейтов...")
    
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Критическое исключение пулинга: {e}")
    finally:
        await bot.session.close()
        logger.info("Сессия закрыта. Экосистема выключена.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger("shadow_tycoon_core").info("Система принудительно остановлена.")
