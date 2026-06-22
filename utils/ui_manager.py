import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger("shadow_tycoon_ui")

# Хранилище активных экранов в формате {tg_id: message_id}
_active_profiles = {}

def register_active_profile(tg_id: int, message_id: int) -> None:
    """Запоминает последнее сообщение с профилем игрока."""
    _active_profiles[tg_id] = message_id

def unregister_active_profile(tg_id: int) -> None:
    """Удаляет запись об активном экране."""
    _active_profiles.pop(tg_id, None)

async def refresh_user_profile_live(tg_id: int, bot: Bot) -> bool:
    """
    Пытается бесшовно обновить открытый профиль игрока в реальном времени.
    Полезно при Level Up из фонового тикера или после переименования компании.
    """
    msg_id = _active_profiles.get(tg_id)
    if not msg_id:
        return False # У игрока сейчас закрыт профиль, обновлять нечего

    # Импортируем функцию рендеринга из хэндлера, избегая циклического импорта
    from handlers.profile import render_profile_screen
    from aiogram.types import Message, Chat

    try:
        # Создаем виртуальный объект сообщения для рендерера
        dummy_chat = Chat(id=tg_id, type="private")
        dummy_message = Message(
            message_id=msg_id,
            date=None,
            chat=dummy_chat
        )
        # Принудительно обновляем текст и клавиатуру
        await render_profile_screen(tg_id=tg_id, message=dummy_message, edit=True)
        return True
    except TelegramAPIError as e:
        # Если юзер удалил сообщение или нажал другую Reply-кнопку
        logger.debug(f"Не удалось обновить Live UI для {tg_id}: {e}")
        unregister_active_profile(tg_id)
        return False
