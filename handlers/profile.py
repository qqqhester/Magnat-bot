from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database.queries import register_user_if_not_exists, get_full_profile, update_shop_name
from utils.economy import get_exp_next, get_warehouse_capacity
from keyboards.reply import get_main_menu_keyboard
from keyboards.inline import get_profile_inline
from utils.ui_manager import register_active_profile # Импортируем трекер

router = Router()

class ProfileStates(StatesGroup):
    input_shop_name = State()

async def render_profile_screen(tg_id: int, message: Message, edit: bool = False) -> None:
    """Универсальная функция сборки и отрисовки профиля (без спама)."""
    profile = get_full_profile(tg_id)
    if not profile:
        if not edit:
            await message.answer("❌ Профиль не найден. Напишите /start для инициализации.")
        return
        
    exp_next = get_exp_next(profile["level"])
    
    total_stock = (
        profile["bread"] + profile["milk"] + profile["meat"] + 
        profile["clothes"] + profile["phones"] + profile["contraband"]
    )
    capacity = get_warehouse_capacity(profile["warehouse_level"])
    
    progress_segments = int((profile["exp"] / exp_next) * 10) if exp_next > 0 else 0
    progress_bar = "▓" * progress_segments + "░" * (10 - progress_segments)
    
    top_rank = 12 
    
    profile_text = (
        f"🏪 Империя: <b>\"{profile['shop_name']}\"</b>\n"
        f"👤 Магнат: @{profile['username'] if profile['username'] else 'Без имени'} | Статус: [Бизнесмен] (Ур. {profile['level']})\n"
        f"📈 Опыт: {profile['exp']}/{exp_next} [{progress_bar}]\n\n"
        f"💰 Баланс: <b>{profile['money']:.2f} 💵</b> | <b>{profile['crystals']} 💎</b>\n"
        f"⚡ Энергия: <b>{profile['energy']}/{profile['max_energy']} AP</b>\n"
        f"⭐ Авторитет: <b>{profile['reputation']}pt</b>\n\n"
        f"📦 Загрузка склада: {total_stock}/{capacity} ед.\n"
        f"──────────────────────────\n"
        f"👑 Место в глобальном ТОПе: #{top_rank}"
    )
    
    if edit:
        sent_msg = await message.edit_text(profile_text, reply_markup=get_profile_inline())
    else:
        sent_msg = await message.answer(profile_text, reply_markup=get_profile_inline())
        
    # Регистрируем ID сообщения в Live UI менеджере
    register_active_profile(tg_id, sent_msg.message_id)

@router.message(CommandStart())
@router.message(F.text.lower().in_(["старт", "начать", "привет"]))
async def start_cmd(message: Message, state: FSMContext) -> None:
    """Точка входа: регистрация сессии в БД и выдача Reply-сетки."""
    await state.clear()
    tg_id = message.from_user.id
    username = message.from_user.username
    
    is_new = register_user_if_not_exists(tg_id, username)
    
    welcome_text = (
        "🚀 <b>Добро пожаловать в экономический симулятор «Теневой Магнат»!</b>\n\n"
        "Вы начали свой путь с мелкой торговой точки. Ваша цель — построить монолитную "
        "бизнес-империю, нанимать персонал, управлять логистикой и обходить конкурентов.\n\n"
        "📊 Используйте нижнее меню для управления процессами."
    )
    if is_new:
        welcome_text += "\n\n🎁 Вам начислено стартовое пособие: <b>100.0 💵</b>"
        
    await message.answer(welcome_text, reply_markup=get_main_menu_keyboard())

@router.message(Command("profile"))
@router.message(F.text.lower().in_(["👤 моя империя", "проф", "стата"]))
async def show_profile(message: Message) -> None:
    """Сборка и вывод полных данных профиля игрока через текстовую команду."""
    await render_profile_screen(message.from_user.id, message, edit=False)

@router.callback_query(F.data == "profile_back")
async def profile_back_callback(callback: CallbackQuery) -> None:
    """Бесшовный возврат в главное меню профиля из подменю."""
    await callback.answer()
    await render_profile_screen(callback.from_user.id, callback.message, edit=True)

@router.callback_query(F.data == "profile_rename")
async def start_rename_shop(callback: CallbackQuery, state: FSMContext) -> None:
    """Перевод пользователя в состояние FSM ожидания нового имени."""
    await callback.answer()
    sent_msg = await callback.message.edit_text(
        "✏️ <b>Режим переименования фирмы</b>\n\n"
        "Введите новое название для вашей торговой марки прямо в чат (до 20 символов):",
        reply_markup=None
    )
    # Сохраняем ID сообщения, чтобы потом почистить его или обновить
    await state.update_data(edit_msg_id=sent_msg.message_id)
    await state.set_state(ProfileStates.input_shop_name)

@router.message(ProfileStates.input_shop_name)
async def process_shop_rename(message: Message, state: FSMContext) -> None:
    """Валидация и применение нового имени торговой точки."""
    new_name = message.text.strip()
    state_data = await state.get_data()
    edit_msg_id = state_data.get("edit_msg_id")
    
    if len(new_name) > 20:
        await message.answer("❌ Название слишком длинное! Максимум 20 символов. Попробуйте еще раз:")
        return
        
    update_shop_name(message.from_user.id, new_name)
    await state.clear()
    
    # Стираем инструкцию ввода, превращая её обратно в обновленный профиль
    if edit_msg_id:
        try:
            from aiogram.types import Chat
            dummy_message = Message(message_id=edit_msg_id, date=None, chat=Chat(id=message.from_user.id, type="private"))
            await render_profile_screen(message.from_user.id, dummy_message, edit=True)
            await message.answer(f"✅ Название фирмы успешно изменено на: <b>\"{new_name}\"</b>")
            return
        except Exception:
            pass

    # Паллбэк, если сообщение инструкции было удалено
    await message.answer(f"✅ Название фирмы успешно изменено на: <b>\"{new_name}\"</b>")
    await render_profile_screen(message.from_user.id, message, edit=False)

@router.callback_query(F.data == "profile_property")
async def show_profile_property(callback: CallbackQuery) -> None:
    """Экран недвижимости и автопарка магната (Бесшовный)."""
    await callback.answer()
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в профиль", callback_data="profile_back")]
    ])
    text = (
        "🏠 <b>НЕДВИЖИМОСТЬ И ЛИЧНЫЙ АВТОПАРК</b>\n\n"
        "Здесь будет отображаться твое элитное имущество, прикрывающее теневые доходы.\n\n"
        "🚗 <b>Автопарк:</b> ВАЗ-2112 (Тюнинг: Сток)\n"
        "🏢 <b>Офисы:</b> Съемная точка на рынке (Ур. 1)\n"
        "🏭 <b>Предприятия:</b> Отсутствуют\n\n"
        "<i>⚙️ Раздел кастомизации и покупки авто/офисов находится в разработке.</i>"
    )
    await callback.message.edit_text(text, reply_markup=back_kb)

@router.callback_query(F.data == "profile_achievements")
async def show_profile_achievements(callback: CallbackQuery) -> None:
    """Экран достижения магната (Бесшовный)."""
    await callback.answer()
    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в профиль", callback_data="profile_back")]
    ])
    text = (
        "🏆 <b>ДОСТИЖЕНИЯ И ЗАЛ СЛАВЫ</b>\n\n"
        "Твои знаковые вехи в построении монополии:\n\n"
        "🥈 <code>Первый рубль</code> — Заработать 100 баксов (🔒 Блокировано)\n"
        "🥇 <code>Контрабандист</code> — Успешно завезти нелегал 5 раз (🔒 Блокировано)\n"
        "💀 <code>Гроза силовиков</code> — Откупиться или пережить облаву (🔒 Блокировано)\n\n"
        "<i>Каждое achievement будет приносить ценные 💎 кристаллы!</i>"
    )
    await callback.message.edit_text(text, reply_markup=back_kb)
