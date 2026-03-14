"""
Telegram Bot для Schedule Booking App
Основной файл бота с обработчиками команд
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    WebAppInfo,
    MenuButtonWebApp
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = os.getenv('BOT_TOKEN')
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8000')
MINI_APP_URL = os.getenv('MINI_APP_URL', 'https://your-app.vercel.app')

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для создания расписания
class CreateScheduleStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_duration = State()
    waiting_for_buffer = State()
    waiting_for_work_hours_start = State()
    waiting_for_work_hours_end = State()
    waiting_for_work_days = State()
    waiting_for_video_platform = State()


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

async def api_request(method: str, endpoint: str, data: Optional[dict] = None):
    """Отправка запроса к Backend API"""
    url = f"{BACKEND_API_URL}{endpoint}"
    
    async with aiohttp.ClientSession() as session:
        try:
            if method == 'GET':
                async with session.get(url, params=data) as response:
                    return await response.json()
            elif method == 'POST':
                async with session.post(url, json=data) as response:
                    return await response.json()
            elif method == 'PATCH':
                async with session.patch(url, json=data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"API request error: {e}")
            return None


def get_main_keyboard():
    """Главная клавиатура"""
    keyboard = [
        [types.KeyboardButton(text="📅 Создать расписание")],
        [types.KeyboardButton(text="📋 Мои встречи"), types.KeyboardButton(text="📊 Статистика")],
        [types.KeyboardButton(text="⚙️ Настройки"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_duration_keyboard():
    """Клавиатура выбора длительности"""
    keyboard = [
        [
            InlineKeyboardButton(text="15 мин", callback_data="duration_15"),
            InlineKeyboardButton(text="30 мин", callback_data="duration_30")
        ],
        [
            InlineKeyboardButton(text="45 мин", callback_data="duration_45"),
            InlineKeyboardButton(text="60 мин", callback_data="duration_60")
        ],
        [InlineKeyboardButton(text="Другое", callback_data="duration_custom")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_buffer_keyboard():
    """Клавиатура выбора буфера"""
    keyboard = [
        [
            InlineKeyboardButton(text="Нет", callback_data="buffer_0"),
            InlineKeyboardButton(text="5 мин", callback_data="buffer_5")
        ],
        [
            InlineKeyboardButton(text="10 мин", callback_data="buffer_10"),
            InlineKeyboardButton(text="15 мин", callback_data="buffer_15")
        ],
        [InlineKeyboardButton(text="30 мин", callback_data="buffer_30")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_video_platform_keyboard():
    """Клавиатура выбора видеоплатформы"""
    keyboard = [
        [InlineKeyboardButton(text="🎥 Jitsi Meet", callback_data="video_jitsi")],
        [InlineKeyboardButton(text="📹 Google Meet", callback_data="video_google_meet")],
        [InlineKeyboardButton(text="💼 Zoom", callback_data="video_zoom")],
        [InlineKeyboardButton(text="🇷🇺 Яндекс.Телемост", callback_data="video_yandex")],
        [InlineKeyboardButton(text="📱 МТС Линк", callback_data="video_mts")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_work_days_keyboard():
    """Клавиатура выбора рабочих дней"""
    keyboard = [
        [
            InlineKeyboardButton(text="Пн", callback_data="day_toggle_0"),
            InlineKeyboardButton(text="Вт", callback_data="day_toggle_1"),
            InlineKeyboardButton(text="Ср", callback_data="day_toggle_2")
        ],
        [
            InlineKeyboardButton(text="Чт", callback_data="day_toggle_3"),
            InlineKeyboardButton(text="Пт", callback_data="day_toggle_4"),
            InlineKeyboardButton(text="Сб", callback_data="day_toggle_5")
        ],
        [
            InlineKeyboardButton(text="Вс", callback_data="day_toggle_6")
        ],
        [InlineKeyboardButton(text="✅ Готово", callback_data="days_done")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =============================================================================
# ОБРАБОТЧИКИ КОМАНД
# =============================================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user = message.from_user
    
    # Регистрируем или обновляем пользователя в БД
    user_data = {
        'telegram_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    
    await api_request('POST', '/api/users/auth', user_data)
    
    # Отправляем приветствие
    welcome_text = f"""👋 Привет, {user.first_name}!

Я помогу тебе управлять расписанием встреч.

<b>Что я умею:</b>
📅 Создавать расписание для встреч
🔗 Генерировать ссылки для записи
📋 Управлять заявками на встречи
🔔 Отправлять напоминания
📊 Показывать статистику

Выбери действие из меню ниже или используй команды:
/create - Создать расписание
/meetings - Мои встречи
/help - Помощь
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_keyboard(),
        parse_mode='HTML'
    )
    
    # Устанавливаем кнопку меню с Mini App
    await bot.set_chat_menu_button(
        chat_id=message.chat.id,
        menu_button=MenuButtonWebApp(
            text="Открыть календарь",
            web_app=WebAppInfo(url=MINI_APP_URL)
        )
    )


@dp.message(Command("help"))
@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    """Обработчик команды /help"""
    help_text = """📖 <b>Справка по использованию бота</b>

<b>Основные команды:</b>
/start - Начать работу
/create - Создать расписание
/meetings - Список встреч
/help - Эта справка

<b>Как создать расписание:</b>
1. Нажми "📅 Создать расписание"
2. Следуй инструкциям бота
3. Получи ссылку для записи
4. Поделись ссылкой с клиентами

<b>Как клиенты записываются:</b>
1. Они переходят по твоей ссылке
2. Выбирают удобное время
3. Заполняют контактные данные
4. Ты получаешь уведомление

<b>Управление встречами:</b>
• Подтверждай или отклоняй заявки
• Получай напоминания за 24ч и 1ч
• Отменяй встречи при необходимости

Остались вопросы? Напиши @support
"""
    
    await message.answer(help_text, parse_mode='HTML')


@dp.message(Command("create"))
@dp.message(F.text == "📅 Создать расписание")
async def cmd_create_schedule(message: types.Message, state: FSMContext):
    """Начало создания расписания"""
    await message.answer(
        "📝 <b>Создаем новое расписание</b>\n\n"
        "Как назовем встречу?\n"
        "Например: <i>Консультация</i>, <i>Собеседование</i>, <i>Урок</i>",
        parse_mode='HTML'
    )
    
    await state.set_state(CreateScheduleStates.waiting_for_title)


@dp.message(CreateScheduleStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    """Обработка названия встречи"""
    await state.update_data(title=message.text)
    
    await message.answer(
        f"✅ Отлично! Встреча: <b>{message.text}</b>\n\n"
        "Сколько времени будет длиться встреча?",
        reply_markup=get_duration_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(CreateScheduleStates.waiting_for_duration)


@dp.callback_query(F.data.startswith("duration_"))
async def process_duration(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора длительности"""
    duration_str = callback.data.split("_")[1]
    
    if duration_str == "custom":
        await callback.message.edit_text(
            "Введите длительность в минутах (например: 25)"
        )
        return
    
    duration = int(duration_str)
    await state.update_data(duration=duration)
    
    await callback.message.edit_text(
        f"⏱ Длительность: <b>{duration} минут</b>\n\n"
        "Нужен ли перерыв между встречами?",
        reply_markup=get_buffer_keyboard(),
        parse_mode='HTML'
    )
    
    await state.set_state(CreateScheduleStates.waiting_for_buffer)
    await callback.answer()


@dp.callback_query(F.data.startswith("buffer_"))
async def process_buffer(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора буфера"""
    buffer = int(callback.data.split("_")[1])
    await state.update_data(buffer_time=buffer)
    
    buffer_text = f"{buffer} минут" if buffer > 0 else "не нужен"
    
    await callback.message.edit_text(
        f"🔄 Перерыв: <b>{buffer_text}</b>\n\n"
        "Во сколько начинается рабочий день?\n"
        "Введите время в формате <code>09:00</code>",
        parse_mode='HTML'
    )
    
    await state.set_state(CreateScheduleStates.waiting_for_work_hours_start)
    await callback.answer()


@dp.message(CreateScheduleStates.waiting_for_work_hours_start)
async def process_work_hours_start(message: types.Message, state: FSMContext):
    """Обработка начала рабочего дня"""
    time_str = message.text.strip()
    
    # Простая валидация
    try:
        datetime.strptime(time_str, "%H:%M")
        await state.update_data(work_hours_start=time_str)
        
        await message.answer(
            f"🌅 Начало: <b>{time_str}</b>\n\n"
            "Во сколько заканчивается рабочий день?\n"
            "Введите время в формате <code>18:00</code>",
            parse_mode='HTML'
        )
        
        await state.set_state(CreateScheduleStates.waiting_for_work_hours_end)
    except ValueError:
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Используйте формат <code>09:00</code>",
            parse_mode='HTML'
        )


@dp.message(CreateScheduleStates.waiting_for_work_hours_end)
async def process_work_hours_end(message: types.Message, state: FSMContext):
    """Обработка окончания рабочего дня"""
    time_str = message.text.strip()
    
    try:
        datetime.strptime(time_str, "%H:%M")
        await state.update_data(work_hours_end=time_str, work_days=[])
        
        await message.answer(
            f"🌆 Окончание: <b>{time_str}</b>\n\n"
            "В какие дни ты работаешь?\n"
            "Выбери дни недели:",
            reply_markup=get_work_days_keyboard(),
            parse_mode='HTML'
        )
        
        await state.set_state(CreateScheduleStates.waiting_for_work_days)
    except ValueError:
        await message.answer(
            "❌ Неверный формат времени.\n"
            "Используйте формат <code>18:00</code>",
            parse_mode='HTML'
        )


@dp.callback_query(F.data.startswith("day_toggle_"))
async def toggle_work_day(callback: types.CallbackQuery, state: FSMContext):
    """Переключение рабочего дня"""
    day_index = int(callback.data.split("_")[2])
    
    data = await state.get_data()
    work_days = data.get('work_days', [])
    
    if day_index in work_days:
        work_days.remove(day_index)
    else:
        work_days.append(day_index)
    
    await state.update_data(work_days=work_days)
    
    # Обновляем текст с отметками
    days_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    selected_days = [days_names[i] for i in sorted(work_days)]
    days_text = ", ".join(selected_days) if selected_days else "не выбраны"
    
    await callback.message.edit_text(
        f"📅 Рабочие дни: <b>{days_text}</b>\n\n"
        "Выбери дни недели:",
        reply_markup=get_work_days_keyboard(),
        parse_mode='HTML'
    )
    
    await callback.answer()


@dp.callback_query(F.data == "days_done")
async def work_days_done(callback: types.CallbackQuery, state: FSMContext):
    """Завершение выбора рабочих дней"""
    data = await state.get_data()
    work_days = data.get('work_days', [])
    
    if not work_days:
        await callback.answer("❌ Выбери хотя бы один день!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "Где будут проходить встречи?\n"
        "Выбери видеоплатформу:",
        reply_markup=get_video_platform_keyboard()
    )
    
    await state.set_state(CreateScheduleStates.waiting_for_video_platform)
    await callback.answer()


@dp.callback_query(F.data.startswith("video_"))
async def process_video_platform(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора видеоплатформы"""
    platform = callback.data.split("_", 1)[1]
    
    platform_names = {
        'jitsi': 'Jitsi Meet',
        'google_meet': 'Google Meet',
        'zoom': 'Zoom',
        'yandex': 'Яндекс.Телемост',
        'mts': 'МТС Линк'
    }
    
    await state.update_data(video_platform=platform)
    
    # Получаем все данные
    data = await state.get_data()
    
    # Отправляем на backend
    schedule_data = {
        'telegram_id': callback.from_user.id,
        'title': data['title'],
        'duration': data['duration'],
        'buffer_time': data['buffer_time'],
        'work_hours_start': data['work_hours_start'],
        'work_hours_end': data['work_hours_end'],
        'work_days': data['work_days'],
        'video_platform': platform
    }
    
    response = await api_request('POST', '/api/schedules', schedule_data)
    
    if response and 'id' in response:
        # Генерируем ссылку для клиентов
        booking_link = f"{MINI_APP_URL}?schedule_id={response['id']}"
        
        await callback.message.edit_text(
            f"✅ <b>Расписание создано!</b>\n\n"
            f"📋 <b>{data['title']}</b>\n"
            f"⏱ {data['duration']} минут\n"
            f"🔄 Перерыв: {data['buffer_time']} мин\n"
            f"🕐 {data['work_hours_start']} - {data['work_hours_end']}\n"
            f"🎥 {platform_names[platform]}\n\n"
            f"🔗 <b>Ссылка для записи:</b>\n"
            f"<code>{booking_link}</code>\n\n"
            f"Поделись этой ссылкой с клиентами!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📤 Поделиться", 
                                     switch_inline_query=f"Записаться: {data['title']}")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при создании расписания.\n"
            "Попробуйте еще раз: /create"
        )
    
    await state.clear()
    await callback.answer()


@dp.message(Command("meetings"))
@dp.message(F.text == "📋 Мои встречи")
async def cmd_meetings(message: types.Message):
    """Просмотр встреч"""
    response = await api_request('GET', '/api/bookings', 
                                 {'telegram_id': message.from_user.id})
    
    if not response or not response.get('bookings'):
        await message.answer(
            "📭 У тебя пока нет запланированных встреч.\n\n"
            "Создай расписание: /create"
        )
        return
    
    bookings = response['bookings']
    
    # Группируем по статусам
    upcoming = [b for b in bookings if b['status'] == 'confirmed' 
                and datetime.fromisoformat(b['scheduled_time']) > datetime.now()]
    pending = [b for b in bookings if b['status'] == 'pending']
    
    text = "📋 <b>Твои встречи</b>\n\n"
    
    if upcoming:
        text += "<b>Предстоящие:</b>\n"
        for booking in upcoming[:5]:
            dt = datetime.fromisoformat(booking['scheduled_time'])
            text += f"• {dt.strftime('%d.%m %H:%M')} - {booking['guest_name']}\n"
        text += "\n"
    
    if pending:
        text += "<b>Требуют подтверждения:</b>\n"
        for booking in pending[:5]:
            dt = datetime.fromisoformat(booking['scheduled_time'])
            text += f"• {dt.strftime('%d.%m %H:%M')} - {booking['guest_name']}\n"
    
    await message.answer(text, parse_mode='HTML')


@dp.message(F.text == "📊 Статистика")
async def show_stats(message: types.Message):
    """Показать статистику"""
    response = await api_request('GET', '/api/stats', 
                                 {'telegram_id': message.from_user.id})
    
    if response:
        await message.answer(
            f"📊 <b>Твоя статистика</b>\n\n"
            f"📅 Всего расписаний: {response.get('total_schedules', 0)}\n"
            f"✅ Проведено встреч: {response.get('completed_meetings', 0)}\n"
            f"⏰ Предстоящих: {response.get('upcoming_meetings', 0)}\n"
            f"⏳ Ожидают подтверждения: {response.get('pending_meetings', 0)}",
            parse_mode='HTML'
        )
    else:
        await message.answer("📊 Статистика пока недоступна")


@dp.message(F.text == "⚙️ Настройки")
async def show_settings(message: types.Message):
    """Настройки"""
    await message.answer(
        "⚙️ <b>Настройки</b>\n\n"
        "Функция в разработке...",
        parse_mode='HTML'
    )


# =============================================================================
# INLINE MODE - для шаринга ссылок
# =============================================================================

@dp.inline_query()
async def inline_query_handler(inline_query: types.InlineQuery):
    """Обработчик inline-запросов для шаринга ссылок"""
    user_id = inline_query.from_user.id
    
    # Получаем расписания пользователя
    response = await api_request('GET', '/api/schedules', {'telegram_id': user_id})
    
    if not response or not response.get('schedules'):
        results = [
            types.InlineQueryResultArticle(
                id='no_schedules',
                title='Нет расписаний',
                description='Создайте расписание: /create',
                input_message_content=types.InputTextMessageContent(
                    message_text='У меня еще нет расписаний'
                )
            )
        ]
    else:
        results = []
        for schedule in response['schedules'][:10]:
            booking_link = f"{MINI_APP_URL}?schedule_id={schedule['id']}"
            
            results.append(
                types.InlineQueryResultArticle(
                    id=str(schedule['id']),
                    title=schedule['title'],
                    description=f"{schedule['duration']} минут",
                    input_message_content=types.InputTextMessageContent(
                        message_text=f"📅 <b>{schedule['title']}</b>\n\n"
                                   f"⏱ {schedule['duration']} минут\n\n"
                                   f"📝 Записаться:\n{booking_link}",
                        parse_mode='HTML'
                    ),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="📝 Записаться", url=booking_link)]
                    ])
                )
            )
    
    await inline_query.answer(results, cache_time=10)


# =============================================================================
# ОБРАБОТКА УВЕДОМЛЕНИЙ О НОВЫХ БРОНИРОВАНИЯХ
# =============================================================================

async def send_booking_notification(booking_data: dict):
    """Отправка уведомления о новом бронировании"""
    organizer_id = booking_data['organizer_telegram_id']
    
    dt = datetime.fromisoformat(booking_data['scheduled_time'])
    
    text = (
        f"🔔 <b>Новая запись!</b>\n\n"
        f"👤 {booking_data['guest_name']}\n"
        f"📧 {booking_data['guest_contact']}\n"
        f"📅 {dt.strftime('%d.%m.%Y')}\n"
        f"⏰ {dt.strftime('%H:%M')}\n"
        f"📋 {booking_data['meeting_title']}\n\n"
    )
    
    if booking_data.get('notes'):
        text += f"💬 Сообщение:\n{booking_data['notes']}\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", 
                               callback_data=f"confirm_{booking_data['id']}"),
            InlineKeyboardButton(text="❌ Отклонить", 
                               callback_data=f"decline_{booking_data['id']}")
        ],
        [InlineKeyboardButton(text="📝 Детали", 
                            callback_data=f"details_{booking_data['id']}")]
    ])
    
    try:
        await bot.send_message(organizer_id, text, 
                             parse_mode='HTML', 
                             reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_booking(callback: types.CallbackQuery):
    """Подтверждение встречи"""
    booking_id = callback.data.split("_")[1]
    
    response = await api_request('PATCH', f'/api/bookings/{booking_id}/confirm', {})
    
    if response:
        await callback.message.edit_text(
            "✅ Встреча подтверждена!\n"
            "Клиент получит уведомление.",
            parse_mode='HTML'
        )
        
        # Отправляем уведомление клиенту
        if response.get('client_telegram_id'):
            await bot.send_message(
                response['client_telegram_id'],
                f"✅ Ваша встреча подтверждена!\n\n"
                f"📅 {response['scheduled_time']}\n"
                f"🔗 Ссылка для встречи:\n{response['meeting_link']}"
            )
    
    await callback.answer()


@dp.callback_query(F.data.startswith("decline_"))
async def decline_booking(callback: types.CallbackQuery):
    """Отклонение встречи"""
    booking_id = callback.data.split("_")[1]
    
    response = await api_request('PATCH', f'/api/bookings/{booking_id}/cancel', {})
    
    if response:
        await callback.message.edit_text(
            "❌ Встреча отклонена.\n"
            "Клиент получит уведомление.",
            parse_mode='HTML'
        )
        
        # Отправляем уведомление клиенту
        if response.get('client_telegram_id'):
            await bot.send_message(
                response['client_telegram_id'],
                "❌ К сожалению, встреча была отменена организатором."
            )
    
    await callback.answer()


# =============================================================================
# ЗАПУСК БОТА
# =============================================================================

async def main():
    """Главная функция запуска бота"""
    logger.info("Starting bot...")
    
    # Удаляем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем polling
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
