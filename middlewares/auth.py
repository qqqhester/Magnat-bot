from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from database.engine import get_db_connection

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)) or not event.from_user:
            return await handler(event, data)

        tg_id = event.from_user.id

        # Быстрая проверка флага блокировки (is_ban) напрямую из БД
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_ban FROM users WHERE tg_id = ?;", (tg_id,))
        user_row = cursor.fetchone()
        conn.close()

        # Если пользователь забанен — полностью игнорируем его действия
        if user_row and user_row["is_ban"] == 1:
            if isinstance(event, CallbackQuery):
                await event.answer("❌ Ваша империя ликвидирована. Доступ заблокирован.", show_alert=True)
            return

        return await handler(event, data)
