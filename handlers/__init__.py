from aiogram import Router
from .profile import router as profile_router
from .shop import router as shop_router

# Создаем единый мастер-роутер для легкого импорта в корневом main.py
router = Router()
router.include_routers(profile_router, shop_router)
