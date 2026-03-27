"""
Telegram Bot — Schedule Booking App v2.0
Fixes: cabinet mode, my meetings, emojis, cancel, clickable links
"""

import os
import logging
from datetime import datetime
from typing import Optional
import traceback

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, MenuButtonWebApp
)
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

logger.info(f"Bot starting | BACKEND: {BACKEND_API_URL} | MINI_APP: {MINI_APP_URL}")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ============================================================
# FSM STATES
# ============================================================

class CreateScheduleStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_duration = State()
    waiting_for_buffer = State()
    waiting_for_video_platform = State()


# ============================================================
# API HELPER
# ============================================================

async def api_request(method: str, endpoint: str, data: Optional[dict] = None):
    url = f"{BACKEND_API_URL}{endpoint}"
    logger.info(f"API {method} {url} | data={data}")

    async with aiohttp.ClientSession() as session:
        try:
            if method == 'GET':
                async with session.get(url, params=data) as resp:
                    text = await resp.text()
                    logger.info(f"Response {resp.status}: {text[:200]}")
                    return await resp.json() if resp.status == 200 else None

            elif method == 'POST':
                async with session.post(url, json=data) as resp:
                    text = await resp.text()
                    logger.info(f"Response {resp.status}: {text[:200]}")
                    return await resp.json() if resp.status in [200, 201] else None

        except Exception as e:
            logger.error(f"API Exception: {e}\n{traceback.format_exc()}")
            return None


# ============================================================
# KEYBOARDS
# ============================================================

def get_main_keyboard():
    """Main reply keyboard with emojis (Issue 7)"""
    keyboard = [
        [types.KeyboardButton(text="📅 Создать расписание")],
        [
            types.KeyboardButton(text="📋 Мои расписания"),
            types.KeyboardButton(text="👥 Мои встречи")   # Issue 2
        ],
        [types.KeyboardButton(text="❓ Помощь")]
    ]
    return types.ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_cancel_keyboard():
    """Keyboard with cancel button (Issue 5)"""
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


def get_cabinet_inline():
    """Inline button to open mini app cabinet (Issue 4 & 6)"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🗓 Кабинет",           # Issue 6: short name
            web_app=WebAppInfo(url=MINI_APP_URL)   # no schedule_id → cabinet mode
        )
    ]])


def get_schedule_inline(schedule_id: str, title: str):
    """Inline button to open specific schedule booking page (Issue 8)"""
    booking_url = f"{MINI_APP_URL}?schedule_id={schedule_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"📲 Открыть: {title}",
            web_app=WebAppInfo(url=booking_url)
        )
    ]])


# ============================================================
# /start
# ============================================================

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    logger.info(f"User {user.id} started bot")

    # Register user in backend
    await api_request('POST', '/api/users/auth', {
        'telegram_id': user.id,
        'username': user.username,
        'first_name': user.first_name
    })

    await message.answer(
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        "Управляй расписанием встреч прямо здесь:\n\n"
        "📅 <b>Создать расписание</b> — настроить слоты и получить ссылку\n"
        "📋 <b>Мои расписания</b> — ваши ссылки для записи\n"
        "👥 <b>Мои встречи</b> — кто и когда записался к вам\n"
        "🗓 <b>Кабинет</b> — открыть мини-приложение\n",
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

    # Issue 4 & 6: show cabinet button
    await message.answer(
        "👇 Открыть личный кабинет:",
        reply_markup=get_cabinet_inline()
    )


# ============================================================
# /help
# ============================================================

@dp.message(Command("help"))
@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Справка</b>\n\n"
        "📅 /create — создать расписание\n"
        "📋 /schedules — мои расписания\n"
        "👥 /meetings — мои встречи\n"
        "🗓 /cabinet — личный кабинет\n"
        "❌ /cancel — отменить текущее действие\n"
        "❓ /help — эта справка\n\n"
        "<b>Как это работает:</b>\n"
        "1. Создай расписание → получи ссылку\n"
        "2. Отправь ссылку клиенту\n"
        "3. Клиент записывается сам\n"
        "4. Ты получаешь уведомление",
        parse_mode='HTML'
    )


# ============================================================
# /cancel — Issue 5
# ============================================================

@dp.message(Command("cancel"))
@dp.message(F.text == "❌ Отмена")
async def cmd_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    await state.clear()
    if current:
        await message.answer(
            "❌ Действие отменено. Возврат в главное меню.",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "Нечего отменять. Ты в главном меню.",
            reply_markup=get_main_keyboard()
        )


# ============================================================
# /cabinet — Issue 4
# ============================================================

@dp.message(Command("cabinet"))
async def cmd_cabinet(message: types.Message):
    await message.answer(
        "🗓 Открыть личный кабинет:",
        reply_markup=get_cabinet_inline()
    )


# ============================================================
# CREATE SCHEDULE FLOW
# ============================================================

@dp.message(Command("create"))
@dp.message(F.text == "📅 Создать расписание")
async def cmd_create(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} starting schedule creation")
    await state.update_data(telegram_id=message.from_user.id)

    # Issue 5: show cancel button
    await message.answer(
        "📝 <b>Создаём расписание</b>\n\n"
        "Шаг 1 из 3\n"
        "Как назовём встречу?\n\n"
        "<i>Например: Консультация, Собеседование, Тренировка</i>\n\n"
        "Нажми ❌ Отмена чтобы прервать в любой момент.",
        parse_mode='HTML',
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateScheduleStates.waiting_for_title)


@dp.message(CreateScheduleStates.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    # Issue 5: handle cancel in mid-flow
    if message.text == "❌ Отмена":
        await cmd_cancel(message, state)
        return

    await state.update_data(title=message.text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏱ 15 мин", callback_data="dur_15"),
            InlineKeyboardButton(text="⏱ 30 мин", callback_data="dur_30"),
        ],
        [
            InlineKeyboardButton(text="⏱ 45 мин", callback_data="dur_45"),
            InlineKeyboardButton(text="⏱ 60 мин", callback_data="dur_60"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]  # Issue 5
    ])

    await message.answer(
        f"✅ Название: <b>{message.text}</b>\n\n"
        "Шаг 2 из 3\n"
        "⏱ Длительность одной встречи?",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(CreateScheduleStates.waiting_for_duration)


@dp.callback_query(F.data == "cancel")
async def cb_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Issue 5: cancel from inline keyboard"""
    await state.clear()
    await callback.message.edit_text("❌ Создание отменено.")
    await callback.message.answer(
        "Возврат в главное меню.",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("dur_"))
async def process_duration(callback: types.CallbackQuery, state: FSMContext):
    duration = int(callback.data.split("_")[1])
    await state.update_data(duration=duration)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🚫 Без перерыва", callback_data="buf_0"),
            InlineKeyboardButton(text="⏳ 5 мин", callback_data="buf_5"),
        ],
        [
            InlineKeyboardButton(text="⏳ 10 мин", callback_data="buf_10"),
            InlineKeyboardButton(text="⏳ 15 мин", callback_data="buf_15"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        f"✅ Длительность: <b>{duration} мин</b>\n\n"
        "⏳ Перерыв между встречами?",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(CreateScheduleStates.waiting_for_buffer)
    await callback.answer()


@dp.callback_query(F.data.startswith("buf_"))
async def process_buffer(callback: types.CallbackQuery, state: FSMContext):
    buffer = int(callback.data.split("_")[1])
    await state.update_data(buffer_time=buffer)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Jitsi Meet (бесплатно)", callback_data="platform_jitsi")],
        [InlineKeyboardButton(text="📹 Google Meet", callback_data="platform_google_meet")],
        [InlineKeyboardButton(text="💼 Zoom", callback_data="platform_zoom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

    buf_text = f"{buffer} мин" if buffer > 0 else "без перерыва"
    await callback.message.edit_text(
        f"✅ Перерыв: <b>{buf_text}</b>\n\n"
        "Шаг 3 из 3\n"
        "🎥 Где будут проходить встречи?",
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    await state.set_state(CreateScheduleStates.waiting_for_video_platform)
    await callback.answer()


@dp.callback_query(F.data.startswith("platform_"))
async def process_platform(callback: types.CallbackQuery, state: FSMContext):
    platform = callback.data.split("_", 1)[1]
    platform_names = {
        'jitsi': '🎥 Jitsi Meet',
        'google_meet': '📹 Google Meet',
        'zoom': '💼 Zoom'
    }

    data = await state.get_data()
    logger.info(f"Creating schedule with data: {data}")

    schedule_data = {
        'telegram_id': data['telegram_id'],
        'title': data['title'],
        'duration': data['duration'],
        'buffer_time': data['buffer_time'],
        'work_hours_start': '09:00',
        'work_hours_end': '18:00',
        'work_days': [0, 1, 2, 3, 4],
        'video_platform': platform
    }

    await callback.message.edit_text("⏳ Создаю расписание...")

    try:
        response = await api_request('POST', '/api/schedules', schedule_data)

        if response and 'id' in response:
            schedule_id = response['id']
            # Issue 8: clickable link
            booking_link = f"{MINI_APP_URL}?schedule_id={schedule_id}"

            await callback.message.edit_text(
                f"✅ <b>Расписание создано!</b>\n\n"
                f"📋 <b>{data['title']}</b>\n"
                f"⏱ {data['duration']} мин\n"
                f"⏳ Перерыв: {data['buffer_time']} мин\n"
                f"🕐 09:00–18:00 (Пн–Пт)\n"
                f"🎥 {platform_names.get(platform, platform)}\n\n"
                f"🔗 <b>Ссылка для записи (кликабельная):</b>\n"
                f"<a href=\"{booking_link}\">{booking_link}</a>",
                parse_mode='HTML',
                disable_web_page_preview=True
            )

            # Issue 8: inline button to open booking page directly
            await callback.message.answer(
                "Поделитесь ссылкой с клиентами. Можно открыть прямо здесь:",
                reply_markup=get_schedule_inline(schedule_id, data['title'])
            )
            logger.info(f"Schedule created: {schedule_id}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка при создании расписания.\n\n"
                "Попробуй ещё раз: /create"
            )

    except Exception as e:
        logger.error(f"process_platform error: {e}\n{traceback.format_exc()}")
        await callback.message.edit_text(
            f"❌ Ошибка: {str(e)}\n\nПопробуй: /create"
        )

    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()


# ============================================================
# MY SCHEDULES (renamed from meetings)
# ============================================================

@dp.message(Command("schedules"))
@dp.message(F.text == "📋 Мои расписания")
async def cmd_schedules(message: types.Message):
    logger.info(f"User {message.from_user.id} requested schedules")
    response = await api_request(
        'GET', '/api/schedules', {'telegram_id': message.from_user.id}
    )

    if response and response.get('schedules'):
        schedules = response['schedules']
        text = "📋 <b>Твои расписания:</b>\n\n"

        for s in schedules:
            booking_link = f"{MINI_APP_URL}?schedule_id={s['id']}"
            text += (
                f"📌 <b>{s['title']}</b>\n"
                f"⏱ {s['duration']} мин | 🎥 {s['video_platform']}\n"
                f"🔗 <a href=\"{booking_link}\">Ссылка для записи</a>\n\n"
            )

        await message.answer(
            text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )

        # Issue 8: inline buttons for each schedule
        inline_rows = [[
            InlineKeyboardButton(
                text=f"📲 {s['title']}",
                web_app=WebAppInfo(url=f"{MINI_APP_URL}?schedule_id={s['id']}")
            )
        ] for s in schedules]

        if inline_rows:
            await message.answer(
                "Открыть страницу записи:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=inline_rows)
            )
    else:
        await message.answer(
            "📭 Расписаний пока нет.\n\n"
            "Создай первое: /create"
        )


# ============================================================
# MY MEETINGS — Issue 2: bookings made TO me (as organizer)
# ============================================================

@dp.message(Command("meetings"))
@dp.message(F.text == "👥 Мои встречи")
async def cmd_meetings(message: types.Message):
    logger.info(f"User {message.from_user.id} requested bookings (as organizer)")
    response = await api_request(
        'GET', '/api/bookings', {'telegram_id': message.from_user.id}
    )

    if response and response.get('bookings'):
        bookings = response['bookings']

        # Separate upcoming and past
        now = datetime.utcnow()
        upcoming = []
        past = []

        for b in bookings:
            try:
                dt_str = b['scheduled_time'].replace('Z', '').replace('+00:00', '')
                dt = datetime.fromisoformat(dt_str)
                (upcoming if dt > now else past).append((dt, b))
            except Exception:
                upcoming.append((now, b))

        upcoming.sort(key=lambda x: x[0])

        status_map = {
            'pending': '⏳',
            'confirmed': '✅',
            'cancelled': '❌',
            'completed': '✓'
        }

        if not upcoming and not past:
            await message.answer(
                "📭 К вам пока никто не записался.\n\n"
                "Поделитесь ссылкой на расписание: /schedules"
            )
            return

        text = "👥 <b>Встречи у вас:</b>\n\n"

        if upcoming:
            text += "📅 <b>Предстоящие:</b>\n"
            for dt, b in upcoming[:15]:
                emoji = status_map.get(b.get('status', 'pending'), '❓')
                text += (
                    f"{emoji} <b>{dt.strftime('%d.%m %H:%M')}</b> — "
                    f"{b.get('guest_name', 'Гость')}\n"
                    f"   📋 {b.get('meeting_title', 'Встреча')}\n"
                )
                # Issue 8: clickable meeting link
                if b.get('meeting_link'):
                    text += f"   🔗 <a href=\"{b['meeting_link']}\">Ссылка на встречу</a>\n"
                if b.get('guest_contact'):
                    text += f"   📞 {b['guest_contact']}\n"
                text += "\n"

        if past:
            text += f"\n✓ <b>Прошедших встреч:</b> {len(past)}\n"

        await message.answer(
            text,
            parse_mode='HTML',
            disable_web_page_preview=True
        )
    else:
        await message.answer(
            "📭 К вам пока никто не записался.\n\n"
            "Поделитесь ссылкой: /schedules"
        )


# ============================================================
# STARTUP
# ============================================================

async def main():
    logger.info("Starting bot v2.0...")
    logger.info(f"Backend URL: {BACKEND_API_URL}")
    logger.info(f"Mini App URL: {MINI_APP_URL}")

    await bot.delete_webhook(drop_pending_updates=True)

    # Issue 6: set menu button (blue button) to "Кабинет"
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="🗓 Кабинет",
                web_app=WebAppInfo(url=MINI_APP_URL)
            )
        )
        logger.info("Menu button set to 'Кабинет'")
    except Exception as e:
        logger.warning(f"Could not set menu button: {e}")

    logger.info("Bot is running!")
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
