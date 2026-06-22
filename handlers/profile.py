from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database.queries import register_user_if_not_exists, get_full_profile, update_shop_name
from utils.economy import get_exp_next, get_warehouse_capacity
from keyboards.reply import get_main_menu_keyboard
from keyboards.inline import get_profile_inline

router = Router()

class ProfileStates(StatesGroup):
    input_shop_name = State()

@router.message(CommandStart())
@router.message(F.text.lower().in_(["старт", "начать", "привет"]))
async def start_cmd(message: Message, state: FSMContext) -> None:
    """Точка входа: регистрация сессии в БД и выдача Reply-сетки."""
    await state.clear()
    tg_id = message.from_user.id
    username = message.from_user.username
    
    # Регистрация в БД (если новый игрок)
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
    """Сборка и вывод полных данных профиля игрока."""
    tg_id = message.from_user.id
    profile = get_full_profile(tg_id)
    
    if not profile:
        await message.answer("❌ Профиль не найден. Напишите /start для инициализации.")
        return
        
    exp_next = get_exp_next(profile["level"])
    
    # Считаем текущую общую загрузку склада
    total_stock = (
        profile["bread"] + profile["milk"] + profile["meat"] + 
        profile["clothes"] + profile["phones"] + profile["contraband"]
    )
    capacity = get_warehouse_capacity(profile["warehouse_level"])
    
    # Визуальный индикатор прогресс-бара опыта (10 делений)
    progress_segments = int((profile["exp"] / exp_next) * 10) if exp_next > 0 else 0
    progress_bar = "▓" * progress_segments + "░" * (10 - progress_segments)
    
    # Эмуляция ТОПа (в рабочей версии заменяется на COUNT/RANK в SQL)
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
    
    await message.answer(profile_text, reply_markup=get_profile_inline())

@router.callback_query(F.data == "profile_rename")
async def start_rename_shop(callback: CallbackQuery, state: FSMContext) -> None:
    """Перевод пользователя в состояние FSM ожидания нового имени."""
    await callback.answer()
    await callback.message.answer("✏️ Введите новое название для вашей фирмы (до 20 символов):")
    await state.set_state(ProfileStates.input_shop_name)

@router.message(ProfileStates.input_shop_name)
async def process_shop_rename(message: Message, state: FSMContext) -> None:
    """Валидация и применение нового имени торговой точки."""
    new_name = message.text.strip()
    
    if len(new_name) > 20:
        await message.answer("❌ Название слишком длинное! Максимум 20 символов. Попробуйте еще раз:")
        return
        
    update_shop_name(message.from_user.id, new_name)
    await state.clear()
    await message.answer(f"✅ Название фирмы успешно изменено на: <b>\"{new_name}\"</b>")
    # Перевызываем показ профиля для обновления UI
    await show_profile(message)
