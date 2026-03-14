"""
Telegram Bot для Schedule Booking App - ИСПРАВЛЕННАЯ ВЕРСИЯ
С логированием ошибок и правильной обработкой
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
import traceback

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, MenuButtonWebApp
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
BACKEND_API_URL = os.getenv('BACKEND_API_URL', 'http://localhost:8000')
MINI_APP_URL = os.getenv('MINI_APP_URL', 'https://your-app.vercel.app')

logger.info(f"Bot starting with BACKEND_API_URL: {BACKEND_API_URL}")
logger.info(f"MINI_APP_URL: {MINI_APP_URL}")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class CreateScheduleStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_duration = State()
    waiting_for_buffer = State()
    waiting_for_work_hours_start = State()
    waiting_for_work_hours_end = State()
    waiting_for_work_days = State()
    waiting_for_video_platform = State()

async def api_request(method: str, endpoint: str, data: Optional[dict] = None):
    """Запрос к Backend API с логированием"""
    url = f"{BACKEND_API_URL}{endpoint}"
    logger.info(f"API Request: {method} {url}")
    logger.info(f"Data: {data}")
    
    async with aiohttp.ClientSession() as session:
        try:
            if method == 'GET':
                async with session.get(url, params=data) as response:
                    response_text = await response.text()
                    logger.info(f"Response status: {response.status}")
                    logger.info(f"Response: {response_text}")
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API Error: {response.status} - {response_text}")
                        return None
            elif method == 'POST':
                async with session.post(url, json=data) as response:
                    response_text = await response.text()
                    logger.info(f"Response status: {response.status}")
                    logger.info(f"Response: {response_text}")
                    if response.status in [200, 201]:
                        return await response.json()
                    else:
                        logger.error(f"API Error: {response.status} - {response_text}")
                        return None
            elif method == 'PATCH':
                async with session.patch(url, json=data) as response:
                    response_text = await response.text()
                    logger.info(f"Response status: {response.status}")
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API Error: {response.status} - {response_text}")
                        return None
        except Exception as e:
            logger.error(f"API Request Exception: {e}")
            logger.error(traceback.format_exc())
            return None

def get_main_keyboard():
    keyboard = [
        [types.KeyboardButton(text="📅 Создать расписание")],
        [types.KeyboardButton(text="📋 Мои встречи"), types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Команда /start"""
    logger.info(f"User {message.from_user.id} started bot")
    user = message.from_user
    
    user_data = {
        'telegram_id': user.id,
        'username': user.username,
        'first_name': user.first_name
    }
    
    response = await api_request('POST', '/api/users/auth', user_data)
    logger.info(f"Auth response: {response}")
    
    await message.answer(
        f"👋 Привет, {user.first_name}!\n\n"
        "Я помогу создать расписание встреч.\n\n"
        "Используй команды:\n"
        "/create - Создать расписание\n"
        "/meetings - Мои встречи\n"
        "/help - Помощь",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("help"))
@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    """Помощь"""
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "/create - Создать расписание\n"
        "/meetings - Список встреч\n"
        "/help - Эта справка\n\n"
        "<b>Как создать расписание:</b>\n"
        "1. Нажми /create\n"
        "2. Следуй инструкциям\n"
        "3. Получи ссылку для клиентов",
        parse_mode='HTML'
    )

@dp.message(Command("create"))
@dp.message(F.text == "📅 Создать расписание")
async def cmd_create(message: types.Message, state: FSMContext):
    """Начало создания расписания"""
    logger.info(f"User {message.from_user.id} creating schedule")
    await message.answer(
        "📝 Создаем расписание\n\n"
        "Как назовем встречу?\n"
        "Например: <i>Консультация</i> или <i>Собеседование</i>",
        parse_mode='HTML'
    )
    await state.set_state(CreateScheduleStates.waiting_for_title)

@dp.message(CreateScheduleStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    """Обработка названия"""
    logger.info(f"Got title: {message.text}")
    await state.update_data(title=message.text, telegram_id=message.from_user.id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="15 мин", callback_data="dur_15"),
            InlineKeyboardButton(text="30 мин", callback_data="dur_30")
        ],
        [
            InlineKeyboardButton(text="45 мин", callback_data="dur_45"),
            InlineKeyboardButton(text="60 мин", callback_data="dur_60")
        ]
    ])
    
    await message.answer(
        f"✅ Отлично! <b>{message.text}</b>\n\n"
        "Сколько времени будет длиться встреча?",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(CreateScheduleStates.waiting_for_duration)

@dp.callback_query(F.data.startswith("dur_"))
async def process_duration(callback: types.CallbackQuery, state: FSMContext):
    """Обработка длительности"""
    duration = int(callback.data.split("_")[1])
    logger.info(f"Got duration: {duration}")
    await state.update_data(duration=duration)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Нет", callback_data="buf_0"),
            InlineKeyboardButton(text="5 мин", callback_data="buf_5")
        ],
        [
            InlineKeyboardButton(text="10 мин", callback_data="buf_10"),
            InlineKeyboardButton(text="15 мин", callback_data="buf_15")
        ]
    ])
    
    await callback.message.edit_text(
        f"⏱ Длительность: <b>{duration} минут</b>\n\n"
        "Нужен ли перерыв между встречами?",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(CreateScheduleStates.waiting_for_buffer)
    await callback.answer()

@dp.callback_query(F.data.startswith("buf_"))
async def process_buffer(callback: types.CallbackQuery, state: FSMContext):
    """Обработка буфера"""
    buffer = int(callback.data.split("_")[1])
    logger.info(f"Got buffer: {buffer}")
    await state.update_data(buffer_time=buffer)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Jitsi Meet", callback_data="platform_jitsi")],
        [InlineKeyboardButton(text="📹 Google Meet", callback_data="platform_google_meet")],
        [InlineKeyboardButton(text="💼 Zoom", callback_data="platform_zoom")]
    ])
    
    buffer_text = f"{buffer} минут" if buffer > 0 else "не нужен"
    await callback.message.edit_text(
        f"🔄 Перерыв: <b>{buffer_text}</b>\n\n"
        "Где будут проходить встречи?\n"
        "Выбери платформу:",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(CreateScheduleStates.waiting_for_video_platform)
    await callback.answer()

@dp.callback_query(F.data.startswith("platform_"))
async def process_platform(callback: types.CallbackQuery, state: FSMContext):
    """Обработка выбора платформы - ФИНАЛЬНЫЙ ШАГ"""
    platform = callback.data.split("_", 1)[1]
    logger.info(f"Got platform: {platform}")
    
    platform_names = {
        'jitsi': 'Jitsi Meet',
        'google_meet': 'Google Meet',
        'zoom': 'Zoom'
    }
    
    # Получаем все данные
    data = await state.get_data()
    logger.info(f"Full data before sending: {data}")
    
    # Подготавливаем данные для отправки
    schedule_data = {
        'telegram_id': data['telegram_id'],
        'title': data['title'],
        'duration': data['duration'],
        'buffer_time': data['buffer_time'],
        'work_hours_start': '09:00',  # По умолчанию
        'work_hours_end': '18:00',     # По умолчанию
        'work_days': [0, 1, 2, 3, 4],  # Пн-Пт
        'video_platform': platform
    }
    
    logger.info(f"Sending schedule data: {schedule_data}")
    
    # Показываем что идет обработка
    await callback.message.edit_text("⏳ Создаю расписание...")
    
    try:
        # Отправляем на backend
        response = await api_request('POST', '/api/schedules', schedule_data)
        
        logger.info(f"Response from backend: {response}")
        
        if response and 'id' in response:
            # Успех!
            booking_link = f"{MINI_APP_URL}?schedule_id={response['id']}"
            
            await callback.message.edit_text(
                f"✅ <b>Расписание создано!</b>\n\n"
                f"📋 <b>{data['title']}</b>\n"
                f"⏱ {data['duration']} минут\n"
                f"🔄 Перерыв: {data['buffer_time']} мин\n"
                f"🕐 09:00 - 18:00 (Пн-Пт)\n"
                f"🎥 {platform_names[platform]}\n\n"
                f"🔗 <b>Ссылка для записи:</b>\n"
                f"<code>{booking_link}</code>\n\n"
                f"Поделись этой ссылкой с клиентами!",
                parse_mode='HTML'
            )
            logger.info(f"Schedule created successfully! ID: {response['id']}")
        else:
            # Ошибка от backend
            error_msg = response.get('detail', 'Unknown error') if response else 'No response from backend'
            logger.error(f"Backend error: {error_msg}")
            await callback.message.edit_text(
                f"❌ Ошибка при создании расписания\n\n"
                f"Детали: {error_msg}\n\n"
                f"Попробуй еще раз: /create",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Exception in process_platform: {e}")
        logger.error(traceback.format_exc())
        await callback.message.edit_text(
            f"❌ Произошла ошибка\n\n"
            f"Детали: {str(e)}\n\n"
            f"Попробуй еще раз: /create"
        )
    
    await state.clear()
    await callback.answer()

@dp.message(Command("meetings"))
@dp.message(F.text == "📋 Мои встречи")
async def cmd_meetings(message: types.Message):
    """Список встреч"""
    logger.info(f"User {message.from_user.id} requested meetings")
    response = await api_request('GET', '/api/bookings', {'telegram_id': message.from_user.id})
    
    if response and response.get('bookings'):
        text = "📋 <b>Твои встречи:</b>\n\n"
        for b in response['bookings'][:10]:
            dt = datetime.fromisoformat(b['scheduled_time'].replace('Z', '+00:00'))
            status_emoji = {
                'pending': '⏳',
                'confirmed': '✅',
                'cancelled': '❌'
            }.get(b.get('status', 'pending'), '❓')
            
            text += f"{status_emoji} {dt.strftime('%d.%m %H:%M')} - {b['guest_name']}\n"
        
        await message.answer(text, parse_mode='HTML')
    else:
        await message.answer(
            "📭 У тебя пока нет встреч\n\n"
            "Создай расписание: /create"
        )

async def main():
    """Главная функция"""
    logger.info("Starting bot...")
    logger.info(f"Backend URL: {BACKEND_API_URL}")
    logger.info(f"Mini App URL: {MINI_APP_URL}")
    
    # Удаляем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем polling
    logger.info("Bot is running!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
