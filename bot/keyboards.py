from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🏪 Магазин")],
            [KeyboardButton(text="🎰 Казино"), KeyboardButton(text="🕵️ Подполье")],
            [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="📜 Квесты")],
            [KeyboardButton(text="🏆 Топ"), KeyboardButton(text="📈 Уровень")]
        ],
        resize_keyboard=True
    )
