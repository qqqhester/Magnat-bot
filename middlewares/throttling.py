import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, throttle_time: float = 1.0) -> None:
        self.throttle_time = throttle_time
        # Внутреннее хранилище таймстампов: {user_id: last_click_time}
        self.users: Dict[int, float] = {}
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Middleware работает и с сообщениями, и с колбэками
        user_id = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            current_time = time.time()
            last_time = self.users.get(user_id, 0.0)

            # Если интервал между кликами меньше заданного
            if current_time - last_time < self.throttle_time:
                self.users[user_id] = current_time  # Сбрасываем таймер флуда
                
                warning_text = (
                    "⚠️ Тормози, босс! Твои пальцы нажимают на кнопки быстрее, "
                    "чем думает твоя бухгалтерия. Подожди секунду."
                )
                
                if isinstance(event, Message):
                    await event.answer(warning_text)
                elif isinstance(event, CallbackQuery):
                    await event.answer(text=warning_text, show_alert=True)
                return  # Блокируем дальнейшую обработку апдейта

            self.users[user_id] = current_time

        return await handler(event, data)
