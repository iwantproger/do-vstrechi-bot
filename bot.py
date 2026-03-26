"""Telegram Bot — Schedule Booking App v1.1.0"""
import os, logging
from datetime import datetime
from typing import Optional
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN       = os.getenv("BOT_TOKEN")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
MINI_APP_URL    = os.getenv("MINI_APP_URL", "https://your-app.vercel.app")

logger.info(f"Backend: {BACKEND_API_URL}")
logger.info(f"Mini App: {MINI_APP_URL}")

bot     = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)


# ── FSM ──────────────────────────────────────────────────────

class CreateSchedule(StatesGroup):
    title    = State()
    duration = State()
    buffer   = State()
    platform = State()


# ── API helper ───────────────────────────────────────────────

async def api(method: str, path: str, data: Optional[dict] = None, params: Optional[dict] = None):
    url = BACKEND_API_URL + path
    async with aiohttp.ClientSession() as session:
        try:
            if method == "GET":
                async with session.get(url, params=params) as r:
                    return await r.json() if r.status in (200, 201) else None
            elif method == "POST":
                async with session.post(url, json=data) as r:
                    return await r.json() if r.status in (200, 201) else None
            elif method == "PATCH":
                async with session.patch(url, json=data or {}) as r:
                    return await r.json() if r.status == 200 else None
        except Exception as e:
            logger.error(f"API {method} {path}: {e}")
            return None


# ── Keyboards ────────────────────────────────────────────────

def main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📅 Создать расписание")],
        [KeyboardButton(text="📋 Мои встречи"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="❓ Помощь")],
    ], resize_keyboard=True)


# ── /start ───────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    resp = await api("POST", "/api/users/auth", {
        "telegram_id": user.id, "username": user.username,
        "first_name": user.first_name, "last_name": user.last_name,
    })
    is_new = resp.get("is_new", True) if resp else True
    greeting = "Добро пожаловать!" if is_new else f"Привет снова, {user.first_name}!"
    await message.answer(
        f"👋 {greeting}\n\n"
        "Я помогаю <b>создавать расписание встреч</b>.\n\n"
        "<b>Как это работает:</b>\n"
        "1️⃣ Создай расписание\n"
        "2️⃣ Получи ссылку\n"
        "3️⃣ Клиенты записываются сами\n"
        "4️⃣ Получай уведомления\n\n"
        "Начни: /create 👇",
        parse_mode="HTML", reply_markup=main_keyboard(),
    )


# ── /help ────────────────────────────────────────────────────

@dp.message(Command("help"))
@dp.message(F.text == "❓ Помощь")
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>Команды</b>\n\n"
        "/create — Создать расписание\n"
        "/meetings — Мои встречи\n"
        "/stats — Статистика\n"
        "/health — Проверить сервис\n"
        "/help — Эта справка",
        parse_mode="HTML",
    )


# ── CREATE SCHEDULE ──────────────────────────────────────────

@dp.message(Command("create"))
@dp.message(F.text == "📅 Создать расписание")
async def cmd_create(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(telegram_id=message.from_user.id)
    await message.answer(
        "📝 <b>Создаём расписание</b>\n\nКак называется встреча?\n"
        "<i>Например: Консультация, Тренировка, Собеседование</i>",
        parse_mode="HTML", reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(CreateSchedule.title)


@dp.message(CreateSchedule.title)
async def process_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    if len(title) < 2:
        await message.answer("Название слишком короткое. Попробуй снова:"); return
    await state.update_data(title=title)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="15 мин", callback_data="dur_15"),
         InlineKeyboardButton(text="30 мин", callback_data="dur_30")],
        [InlineKeyboardButton(text="45 мин", callback_data="dur_45"),
         InlineKeyboardButton(text="60 мин", callback_data="dur_60")],
        [InlineKeyboardButton(text="90 мин", callback_data="dur_90"),
         InlineKeyboardButton(text="2 часа",  callback_data="dur_120")],
    ])
    await message.answer(
        f"✅ <b>{title}</b>\n\nСколько длится встреча?",
        parse_mode="HTML", reply_markup=kb,
    )
    await state.set_state(CreateSchedule.duration)


@dp.callback_query(F.data.startswith("dur_"), CreateSchedule.duration)
async def process_duration(cb: types.CallbackQuery, state: FSMContext):
    duration = int(cb.data.split("_")[1])
    await state.update_data(duration=duration)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без перерыва", callback_data="buf_0"),
         InlineKeyboardButton(text="5 мин",  callback_data="buf_5")],
        [InlineKeyboardButton(text="10 мин", callback_data="buf_10"),
         InlineKeyboardButton(text="15 мин", callback_data="buf_15")],
        [InlineKeyboardButton(text="30 мин", callback_data="buf_30")],
    ])
    await cb.message.edit_text(
        f"⏱ <b>{duration} мин</b>\n\nПерерыв между встречами?",
        parse_mode="HTML", reply_markup=kb,
    )
    await state.set_state(CreateSchedule.buffer)
    await cb.answer()


@dp.callback_query(F.data.startswith("buf_"), CreateSchedule.buffer)
async def process_buffer(cb: types.CallbackQuery, state: FSMContext):
    buffer = int(cb.data.split("_")[1])
    await state.update_data(buffer_time=buffer)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Jitsi Meet (бесплатно)", callback_data="plt_jitsi")],
        [InlineKeyboardButton(text="📹 Google Meet",            callback_data="plt_google_meet")],
        [InlineKeyboardButton(text="💼 Zoom",                   callback_data="plt_zoom")],
        [InlineKeyboardButton(text="🦊 Яндекс.Телемост",        callback_data="plt_yandex")],
        [InlineKeyboardButton(text="📡 МТС Линк",               callback_data="plt_mts")],
        [InlineKeyboardButton(text="🔀 Клиент выбирает сам",    callback_data="plt_choice")],
    ])
    buf_text = f"{buffer} мин" if buffer else "без перерыва"
    await cb.message.edit_text(
        f"🔄 Перерыв: <b>{buf_text}</b>\n\nГде проходят встречи?",
        parse_mode="HTML", reply_markup=kb,
    )
    await state.set_state(CreateSchedule.platform)
    await cb.answer()


PLATFORM_NAMES = {
    "jitsi": "Jitsi Meet", "google_meet": "Google Meet",
    "zoom": "Zoom", "yandex": "Яндекс.Телемост", "mts": "МТС Линк",
}

@dp.callback_query(F.data.startswith("plt_"), CreateSchedule.platform)
async def process_platform(cb: types.CallbackQuery, state: FSMContext):
    platform_raw  = cb.data.split("_", 1)[1]
    is_choice     = (platform_raw == "choice")
    platform      = "jitsi" if is_choice else platform_raw
    location_mode = "user_choice" if is_choice else "fixed"

    await state.update_data(video_platform=platform, location_mode=location_mode)
    await cb.message.edit_text("⏳ Создаю расписание...")

    data = await state.get_data()
    resp = await api("POST", "/api/schedules", {
        "telegram_id": data["telegram_id"], "title": data["title"],
        "duration": data["duration"], "buffer_time": data["buffer_time"],
        "work_hours_start": "09:00", "work_hours_end": "18:00",
        "work_days": [0, 1, 2, 3, 4],
        "video_platform": platform, "location_mode": location_mode,
    })

    if resp and "id" in resp:
        booking_link  = f"{MINI_APP_URL}?schedule_id={resp['id']}"
        plat_display  = "Клиент выбирает" if is_choice else PLATFORM_NAMES.get(platform, platform)
        share_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📅 Открыть расписание", web_app=WebAppInfo(url=booking_link))],
            [InlineKeyboardButton(text="📋 Показать ссылку", callback_data=f"showlink_{resp['id']}")],
        ])
        await cb.message.edit_text(
            f"✅ <b>Расписание создано!</b>\n\n"
            f"📋 {data['title']}\n"
            f"⏱ {data['duration']} мин · перерыв {data['buffer_time']} мин\n"
            f"🕐 09:00–18:00, Пн–Пт\n"
            f"🎥 {plat_display}\n\n"
            f"🔗 <b>Ссылка для клиентов:</b>\n<code>{booking_link}</code>\n\n"
            f"Отправь клиенту — он выберет время сам!",
            parse_mode="HTML", reply_markup=share_kb,
        )
    else:
        await cb.message.edit_text(
            "❌ <b>Не удалось создать расписание</b>\n\nПопробуй: /create",
            parse_mode="HTML",
        )

    await state.clear()
    await cb.answer()
    await bot.send_message(cb.from_user.id, "Главное меню 👇", reply_markup=main_keyboard())


@dp.callback_query(F.data.startswith("showlink_"))
async def show_link(cb: types.CallbackQuery):
    schedule_id = cb.data.split("_", 1)[1]
    link = f"{MINI_APP_URL}?schedule_id={schedule_id}"
    await cb.answer(f"Ссылка:\n{link}", show_alert=True)


# ── MY MEETINGS ──────────────────────────────────────────────

@dp.message(Command("meetings"))
@dp.message(F.text == "📋 Мои встречи")
async def cmd_meetings(message: types.Message):
    resp = await api("GET", "/api/bookings", params={"telegram_id": message.from_user.id})
    if not resp or not resp.get("bookings"):
        await message.answer(
            "📭 <b>Встреч пока нет</b>\n\nСоздай расписание: /create",
            parse_mode="HTML",
        ); return

    now = datetime.now()
    upcoming, past = [], []
    for b in resp["bookings"]:
        try:
            dt = datetime.fromisoformat(b["scheduled_time"].replace("Z", ""))
        except Exception:
            dt = now
        (upcoming if dt > now and b.get("status") not in ("cancelled",) else past).append((dt, b))

    upcoming.sort(key=lambda x: x[0])
    past.sort(key=lambda x: x[0], reverse=True)

    icons = {"confirmed": "✅", "pending": "⏳", "cancelled": "❌", "completed": "✓"}
    text = ""

    if upcoming:
        text += "📅 <b>Предстоящие:</b>\n\n"
        for dt, b in upcoming[:5]:
            icon = icons.get(b.get("status", ""), "📌")
            text += (f"{icon} <b>{b.get('meeting_title') or 'Встреча'}</b>\n"
                     f"   👤 {b.get('guest_name','—')} · {dt.strftime('%d.%m %H:%M')}\n\n")

    if past:
        text += "📋 <b>Прошедшие:</b>\n\n"
        for dt, b in past[:3]:
            icon = icons.get(b.get("status", ""), "✓")
            text += f"{icon} {b.get('meeting_title') or 'Встреча'} · {b.get('guest_name','—')} · {dt.strftime('%d.%m')}\n"

    if not text:
        text = "📭 Нет встреч"

    # Кнопки для pending
    buttons = []
    for dt, b in upcoming:
        if b.get("status") == "pending":
            label = f"{b.get('meeting_title','Встреча')} ({b.get('guest_name','—')}) {dt.strftime('%d.%m %H:%M')}"
            buttons.append([
                InlineKeyboardButton(text=f"✅ Подтвердить", callback_data=f"confirm_{b['id']}"),
                InlineKeyboardButton(text=f"❌ Отклонить",   callback_data=f"decline_{b['id']}"),
            ])
            text += f"\n⏳ Ожидает: <b>{label}</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@dp.callback_query(F.data.startswith("confirm_"))
async def confirm_meeting(cb: types.CallbackQuery):
    resp = await api("PATCH", f"/api/bookings/{cb.data.split('_',1)[1]}/confirm")
    await cb.answer("✅ Встреча подтверждена!" if resp else "❌ Ошибка", show_alert=True)
    if resp:
        await cb.message.edit_reply_markup(reply_markup=None)


@dp.callback_query(F.data.startswith("decline_"))
async def decline_meeting(cb: types.CallbackQuery):
    resp = await api("PATCH", f"/api/bookings/{cb.data.split('_',1)[1]}/cancel")
    await cb.answer("Встреча отклонена" if resp else "Ошибка", show_alert=True)
    if resp:
        await cb.message.edit_reply_markup(reply_markup=None)


# ── STATS ────────────────────────────────────────────────────

@dp.message(Command("stats"))
@dp.message(F.text == "📊 Статистика")
async def cmd_stats(message: types.Message):
    resp = await api("GET", "/api/stats", params={"telegram_id": message.from_user.id})
    if resp:
        await message.answer(
            f"📊 <b>Статистика</b>\n\n"
            f"📋 Всего: <b>{resp.get('total', 0)}</b>\n"
            f"📅 Предстоящих: <b>{resp.get('upcoming', 0)}</b>\n"
            f"✓ Завершённых: <b>{resp.get('completed', 0)}</b>",
            parse_mode="HTML",
        )
    else:
        await message.answer("📊 Статистика временно недоступна")


@dp.message(Command("health"))
async def cmd_health(message: types.Message):
    resp = await api("GET", "/health")
    if resp:
        icon = "✅" if resp.get("status") == "healthy" else "❌"
        await message.answer(f"{icon} Backend: <b>{resp.get('status')}</b>\nDB: {resp.get('supabase')}", parse_mode="HTML")
    else:
        await message.answer("❌ Backend недоступен")


# ── MAIN ─────────────────────────────────────────────────────

async def main():
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is running!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
