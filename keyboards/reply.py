from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Генерация постоянной Reply-сетки главного меню империи."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="👤 Моя Империя"),
                KeyboardButton(text="🏪 Магазин B2B")
            ],
            [
                KeyboardButton(text="📊 Спрос"),
                KeyboardButton(text="🕵️ Подполье")
            ],
            [
                KeyboardButton(text="📜 Задания & Топ"),
                KeyboardButton(text="🎟️ Активация")
            ]
        ],
        resize_keyboard=True,
        persistent=True  # Закрепляем сетку намертво внизу экрана
    )
    return keyboard
