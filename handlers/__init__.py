from aiogram import Router
from .profile import router as profile_router
from .shop import router as shop_router
from .market import router as market_router
from .rivals import router as rivals_router
from .admin import router as admin_router
from .bonus import router as bonus_router

# Единый мастер-роутер проекта
router = Router()

router.include_routers(
    admin_router,
    profile_router,
    shop_router,
    market_router,
    rivals_router,
    bonus_router
)
