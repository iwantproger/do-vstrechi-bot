"""
Telegram Bot — До встречи v1.1
+ Inline режим
+ Без лишних эмодзи-стрелок
"""

import os
import logging
import traceback
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo,
    InlineQueryResultArticle, InputTextMessageContent
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN       = os.getenv("BOT_TOKEN")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
MINI_APP_URL    = os.getenv("MINI_APP_URL", "https://your-app.vercel.app")

logger.info(f"BACKEND={BACKEND_API_URL} | MINI_APP={MINI_APP_URL}")

bot     = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)

PLATFORM_NAMES = {
    "jitsi":       "Jitsi Meet",
    "google_meet": "Google Meet",
    "zoom":        "Zoom",
    "yandex":      "Яндекс.Телемост",
    "mts":         "МТС Линк",
}


# ───── FSM ─────
class CreateSchedule(StatesGroup):
    title   = State()
    dur     = State()
    buf     = State()
    wstart  = State()
    wend    = State()
    plat    = State()
    confirm = State()


# ───── API HELPER ─────
async def api(method: str, path: str, data=None, params=None):
    url = BACKEND_API_URL + path
    async with aiohttp.ClientSession() as sess:
        try:
            kw = dict(timeout=aiohttp.ClientTimeout(total=10))
            if method == "GET":
                async with sess.get(url, params=params, **kw) as r:
                    if r.status == 200:
                        return await r.json()
                    logger.warning(f"GET {path} {r.status}: {await r.text()}")
                    return None
            elif method == "POST":
                async with sess.post(url, json=data, **kw) as r:
                    body = await r.json()
                    if r.status in (200, 201):
                        return body
                    logger.warning(f"POST {path} {r.status}: {body}")
                    return body
        except Exception as e:
            logger.error(f"API {method} {path}: {e}")
            return None


# ───── KEYBOARDS ─────
def kb_main():
    return types.ReplyKeyboardMarkup(keyboard=[
        [types.KeyboardButton(text="Создать расписание")],
        [types.KeyboardButton(text="Мои расписания"), types.KeyboardButton(text="Помощь")]
    ], resize_keyboard=True)

def kb_dur():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="15 мин", callback_data="dur_15"),
         InlineKeyboardButton(text="30 мин", callback_data="dur_30")],
        [InlineKeyboardButton(text="45 мин", callback_data="dur_45"),
         InlineKeyboardButton(text="60 мин", callback_data="dur_60")],
        [InlineKeyboardButton(text="90 мин", callback_data="dur_90"),
         InlineKeyboardButton(text="120 мин", callback_data="dur_120")],
    ])

def kb_buf():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без перерыва", callback_data="buf_0"),
         InlineKeyboardButton(text="5 мин",  callback_data="buf_5")],
        [InlineKeyboardButton(text="10 мин", callback_data="buf_10"),
         InlineKeyboardButton(text="15 мин", callback_data="buf_15")],
        [InlineKeyboardButton(text="30 мин", callback_data="buf_30")],
    ])

def kb_wstart():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="08:00", callback_data="whs_08:00"),
         InlineKeyboardButton(text="09:00", callback_data="whs_09:00"),
         InlineKeyboardButton(text="10:00", callback_data="whs_10:00")],
        [InlineKeyboardButton(text="Ввести вручную", callback_data="whs_manual")],
    ])

def kb_wend():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="17:00", callback_data="whe_17:00"),
         InlineKeyboardButton(text="18:00", callback_data="whe_18:00"),
         InlineKeyboardButton(text="19:00", callback_data="whe_19:00")],
        [InlineKeyboardButton(text="20:00", callback_data="whe_20:00"),
         InlineKeyboardButton(text="Ввести вручную", callback_data="whe_manual")],
    ])

def kb_plat():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Jitsi Meet (бесплатно)", callback_data="pl_jitsi")],
        [InlineKeyboardButton(text="Google Meet",           callback_data="pl_google_meet")],
        [InlineKeyboardButton(text="Zoom",                  callback_data="pl_zoom")],
        [InlineKeyboardButton(text="Яндекс.Телемост",       callback_data="pl_yandex")],
        [InlineKeyboardButton(text="МТС Линк",              callback_data="pl_mts")],
    ])


# ───── /start ─────
@dp.message(CommandStart())
async def cmd_start(msg: types.Message):
    u = msg.from_user
    await api("POST", "/api/users/auth", {
        "telegram_id": u.id, "username": u.username,
        "first_name": u.first_name, "last_name": u.last_name,
    })
    await msg.answer(
        f"Привет, <b>{u.first_name}</b>!\n\n"
        "Я помогу организовать расписание встреч.\n\n"
        "Создай расписание — и получи ссылку для клиентов.\n"
        "Клиент открывает ссылку и сам выбирает время.\n\n"
        "Начни с кнопки ниже:",
        parse_mode="HTML",
        reply_markup=kb_main()
    )

@dp.message(Command("help"))
@dp.message(F.text == "Помощь")
async def cmd_help(msg: types.Message):
    await msg.answer(
        "<b>Как это работает:</b>\n\n"
        "1. Создай расписание — настрой слоты\n"
        "2. Получи ссылку — отправь клиенту\n"
        "3. Клиент открывает и выбирает время\n"
        "4. Ты получаешь уведомление о записи\n\n"
        "<b>Inline режим:</b>\n"
        "Напиши <code>@do_vstrechi_bot</code> в любом чате — "
        "появятся твои расписания. Нажми — отправишь ссылку собеседнику.\n\n"
        "<b>Команды:</b>\n"
        "/create — создать расписание\n"
        "/schedules — мои расписания\n"
        "/help — эта справка",
        parse_mode="HTML"
    )


# ───── CREATE ─────
@dp.message(Command("create"))
@dp.message(F.text == "Создать расписание")
async def cmd_create(msg: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(telegram_id=msg.from_user.id)
    await msg.answer(
        "<b>Создаём расписание</b>\n\nКак назовём встречу?\n"
        "Например: <i>Консультация</i>, <i>Собеседование</i>, <i>Сессия</i>",
        parse_mode="HTML"
    )
    await state.set_state(CreateSchedule.title)

@dp.message(CreateSchedule.title)
async def got_title(msg: types.Message, state: FSMContext):
    t = msg.text.strip()
    if len(t) < 2:
        await msg.answer("Слишком короткое название. Минимум 2 символа.")
        return
    await state.update_data(title=t)
    await msg.answer(
        f"<b>{t}</b>\n\nСколько длится встреча?",
        reply_markup=kb_dur(), parse_mode="HTML"
    )
    await state.set_state(CreateSchedule.dur)

@dp.callback_query(F.data.startswith("dur_"))
async def got_dur(cb: types.CallbackQuery, state: FSMContext):
    d = int(cb.data.split("_")[1])
    await state.update_data(duration=d)
    await cb.message.edit_text(
        f"Длительность: <b>{d} мин</b>\n\nПеррыв между встречами?",
        reply_markup=kb_buf(), parse_mode="HTML"
    )
    await state.set_state(CreateSchedule.buf)
    await cb.answer()

@dp.callback_query(F.data.startswith("buf_"))
async def got_buf(cb: types.CallbackQuery, state: FSMContext):
    b = int(cb.data.split("_")[1])
    await state.update_data(buffer_time=b)
    bt = f"{b} мин" if b else "без перерыва"
    await cb.message.edit_text(
        f"Перерыв: <b>{bt}</b>\n\nС какого часа принимаешь клиентов?",
        reply_markup=kb_wstart(), parse_mode="HTML"
    )
    await state.set_state(CreateSchedule.wstart)
    await cb.answer()

@dp.callback_query(F.data.startswith("whs_"))
async def got_wstart_cb(cb: types.CallbackQuery, state: FSMContext):
    v = cb.data.split("_", 1)[1]
    if v == "manual":
        await cb.message.edit_text("Введи время начала (формат HH:MM, например 10:00):")
        await state.set_state(CreateSchedule.wstart)
        await cb.answer()
        return
    await state.update_data(work_hours_start=v)
    await cb.message.edit_text(
        f"Начало: <b>{v}</b>\n\nДо какого часа?",
        reply_markup=kb_wend(), parse_mode="HTML"
    )
    await state.set_state(CreateSchedule.wend)
    await cb.answer()

@dp.message(CreateSchedule.wstart)
async def got_wstart_txt(msg: types.Message, state: FSMContext):
    v = msg.text.strip()
    if not _vt(v):
        await msg.answer("Неверный формат. Введи как HH:MM, например 09:30:")
        return
    await state.update_data(work_hours_start=v)
    await msg.answer(f"Начало: <b>{v}</b>\n\nДо какого часа?", reply_markup=kb_wend(), parse_mode="HTML")
    await state.set_state(CreateSchedule.wend)

@dp.callback_query(F.data.startswith("whe_"))
async def got_wend_cb(cb: types.CallbackQuery, state: FSMContext):
    v = cb.data.split("_", 1)[1]
    if v == "manual":
        await cb.message.edit_text("Введи время окончания (формат HH:MM, например 18:00):")
        await state.set_state(CreateSchedule.wend)
        await cb.answer()
        return
    await state.update_data(work_hours_end=v)
    await cb.message.edit_text(
        f"Конец: <b>{v}</b>\n\nГде будут встречи?",
        reply_markup=kb_plat(), parse_mode="HTML"
    )
    await state.set_state(CreateSchedule.plat)
    await cb.answer()

@dp.message(CreateSchedule.wend)
async def got_wend_txt(msg: types.Message, state: FSMContext):
    v = msg.text.strip()
    if not _vt(v):
        await msg.answer("Неверный формат. Введи как HH:MM, например 18:00:")
        return
    await state.update_data(work_hours_end=v)
    await msg.answer(f"Конец: <b>{v}</b>\n\nГде будут встречи?", reply_markup=kb_plat(), parse_mode="HTML")
    await state.set_state(CreateSchedule.plat)

@dp.callback_query(F.data.startswith("pl_"))
async def got_plat(cb: types.CallbackQuery, state: FSMContext):
    pl = cb.data.split("_", 1)[1]
    await state.update_data(video_platform=pl)
    d = await state.get_data()
    pn = PLATFORM_NAMES.get(pl, pl)
    bt = f"{d['buffer_time']} мин" if d['buffer_time'] else "нет"
    await cb.message.edit_text(
        f"<b>Проверь данные:</b>\n\n"
        f"Название: <b>{d['title']}</b>\n"
        f"Длительность: <b>{d['duration']} мин</b>\n"
        f"Перерыв: <b>{bt}</b>\n"
        f"Часы: <b>{d.get('work_hours_start','09:00')} — {d.get('work_hours_end','18:00')}</b>\n"
        f"Дни: <b>Пн–Пт</b>\n"
        f"Платформа: <b>{pn}</b>\n\n"
        f"Всё верно?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Создать", callback_data="do_create"),
             InlineKeyboardButton(text="Заново",  callback_data="restart")]
        ]),
        parse_mode="HTML"
    )
    await state.set_state(CreateSchedule.confirm)
    await cb.answer()

@dp.callback_query(F.data == "restart")
async def do_restart(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Начнём заново. Как назовём встречу?")
    await state.set_state(CreateSchedule.title)
    await cb.answer()

@dp.callback_query(F.data == "do_create")
async def do_create(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.edit_text("Создаю расписание...")
    d = await state.get_data()
    payload = {
        "telegram_id":      d["telegram_id"],
        "title":            d["title"],
        "duration":         d["duration"],
        "buffer_time":      d["buffer_time"],
        "work_hours_start": d.get("work_hours_start", "09:00"),
        "work_hours_end":   d.get("work_hours_end",   "18:00"),
        "work_days":        [0, 1, 2, 3, 4],
        "video_platform":   d["video_platform"],
        "location_mode":    "fixed",
    }
    r = await api("POST", "/api/schedules", payload)
    if r and "id" in r:
        link = f"{MINI_APP_URL}?schedule_id={r['id']}"
        pn = PLATFORM_NAMES.get(d["video_platform"], d["video_platform"])
        bt = f"{d['buffer_time']} мин" if d['buffer_time'] else "нет"
        await cb.message.edit_text(
            f"Расписание создано!\n\n"
            f"<b>{d['title']}</b>\n"
            f"{d['duration']} мин · перерыв {bt}\n"
            f"{d.get('work_hours_start','09:00')}–{d.get('work_hours_end','18:00')} · Пн–Пт\n"
            f"{pn}\n\n"
            f"Ссылка для клиентов:\n<code>{link}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="Открыть расписание",
                    web_app=WebAppInfo(url=link)
                )],
                [InlineKeyboardButton(text="Мои расписания", callback_data="show_scheds")],
            ]),
            parse_mode="HTML"
        )
    else:
        err = r.get("detail", "Неизвестная ошибка") if r else "Нет ответа от сервера"
        await cb.message.edit_text(
            f"Ошибка при создании расписания\n\n{err}\n\nПопробуй ещё раз: /create",
            parse_mode="HTML"
        )
    await state.clear()
    await cb.answer()


# ───── MY SCHEDULES ─────
@dp.message(Command("schedules"))
@dp.message(F.text == "Мои расписания")
@dp.callback_query(F.data == "show_scheds")
async def cmd_schedules(event):
    msg = event.message if hasattr(event, "message") else event
    uid = event.from_user.id
    r = await api("GET", "/api/schedules", params={"telegram_id": uid})
    scheds = r.get("schedules", []) if r else []
    if not scheds:
        text = "У тебя пока нет расписаний.\n\nСоздай первое: /create"
    else:
        lines = ["<b>Твои расписания:</b>\n"]
        for s in scheds:
            link = f"{MINI_APP_URL}?schedule_id={s['id']}"
            pn = PLATFORM_NAMES.get(s.get("video_platform", ""), "")
            lines.append(
                f"📌 <b>{s['title']}</b>\n"
                f"   {s['duration']} мин · {s.get('work_hours_start','09:00')}–{s.get('work_hours_end','18:00')}\n"
                f"   {pn}\n"
                f"   <code>{link}</code>\n"
            )
        text = "\n".join(lines)
    if hasattr(event, "message"):
        await event.message.answer(text, parse_mode="HTML")
        await event.answer()
    else:
        await msg.answer(text, parse_mode="HTML")


# ───── INCOMING BOOKINGS ─────
@dp.message(Command("meetings"))
async def cmd_meetings(msg: types.Message):
    r = await api("GET", "/api/bookings", params={"telegram_id": msg.from_user.id})
    bookings = r.get("bookings", []) if r else []
    org = [b for b in bookings if b.get("organizer_telegram_id") == msg.from_user.id and b.get("status") != "cancelled"]
    if not org:
        await msg.answer("Пока нет записей от клиентов.\n\nПоделись ссылкой на расписание: /schedules")
        return
    now = datetime.now()
    lines = ["<b>Входящие записи:</b>\n"]
    em_map = {"confirmed": "✅", "pending": "⏳", "pending_organizer_approval": "⏳",
              "cancelled": "❌", "completed": "✓"}
    for b in sorted(org, key=lambda x: x.get("scheduled_time", ""))[:10]:
        dt = datetime.fromisoformat(b["scheduled_time"].replace("Z", ""))
        em = em_map.get(b.get("status", ""), "•")
        ttl = b.get("meeting_title") or "Встреча"
        lines.append(f"{em} {dt.strftime('%d.%m %H:%M')} — {b.get('guest_name','?')} ({ttl})")
    await msg.answer("\n".join(lines), parse_mode="HTML")


# ───── INLINE MODE ─────
@dp.inline_query()
async def inline_query(query: types.InlineQuery):
    uid = query.from_user.id
    q = query.query.strip().lower()

    r = await api("GET", "/api/schedules", params={"telegram_id": uid})
    scheds = r.get("schedules", []) if r else []

    if q:
        scheds = [s for s in scheds if q in s.get("title", "").lower()]

    results = []
    for sch in scheds[:10]:
        link = f"{MINI_APP_URL}?schedule_id={sch['id']}"
        pn = PLATFORM_NAMES.get(sch.get("video_platform", ""), "")
        dur = sch.get("duration", 30)
        wstart = sch.get("work_hours_start", "09:00")
        wend   = sch.get("work_hours_end",   "18:00")

        results.append(
            InlineQueryResultArticle(
                id=sch["id"],
                title=sch["title"],
                description=f"{dur} мин · {wstart}–{wend}{' · ' + pn if pn else ''}",
                input_message_content=InputTextMessageContent(
                    message_text=(
                        f"Запись на встречу\n\n"
                        f"<b>{sch['title']}</b>\n"
                        f"Длительность: {dur} мин\n"
                        f"Платформа: {pn}\n\n"
                        f"Выбери удобное время по кнопке ниже:"
                    ),
                    parse_mode="HTML"
                ),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="Выбрать время и записаться",
                        url=link
                    )]
                ])
            )
        )

    if not results:
        results.append(
            InlineQueryResultArticle(
                id="empty",
                title="Нет расписаний" if not q else "Ничего не найдено",
                description="Создайте расписание через /create",
                input_message_content=InputTextMessageContent(
                    message_text="Создайте расписание: @do_vstrechi_bot → /create"
                )
            )
        )

    await query.answer(results, cache_time=30, is_personal=True)


# ───── UTILS ─────
def _vt(s):
    try: datetime.strptime(s, "%H:%M"); return True
    except ValueError: return False


# ───── MAIN ─────
async def main():
    logger.info("Starting bot...")
    await bot.delete_webhook(drop_pending_updates=True)
    # Set commands
    await bot.set_my_commands([
        types.BotCommand(command="start",     description="Начать работу"),
        types.BotCommand(command="create",    description="Создать расписание"),
        types.BotCommand(command="schedules", description="Мои расписания"),
        types.BotCommand(command="meetings",  description="Входящие записи"),
        types.BotCommand(command="help",      description="Помощь"),
    ])
    logger.info("Bot running!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
