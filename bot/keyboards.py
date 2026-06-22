from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🏪 Магазин")],
            [KeyboardButton(text="🔧 Улучшения"), KeyboardButton(text="👨‍💼 Работники")],
            [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="🏆 Топ")]
        ],
        resize_keyboard=True
    )
