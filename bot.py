import asyncio
import logging
import os
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== ПЕРЕМЕННЫЕ ==========
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_ID = os.getenv("ADMIN_ID")
if not CHANNEL_ID or not ADMIN_ID:
    raise ValueError("CHANNEL_ID и ADMIN_ID обязательны!")

try:
    CHANNEL_ID = int(CHANNEL_ID)
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError("CHANNEL_ID и ADMIN_ID должны быть числами!")

SERVER_IP = os.getenv("SERVER_IP", "vanilka.minecraft.surf")
SERVER_VERSION = os.getenv("SERVER_VERSION", "1.21.11")
SBER_CARD = os.getenv("SBER_CARD", "2202205046722309")

# ========== СОСТОЯНИЯ ==========
class Complaint(StatesGroup):
    waiting_nick = State()
    waiting_offender = State()
    waiting_desc = State()
    waiting_media = State()

class Question(StatesGroup):
    waiting_nick = State()
    waiting_text = State()

class ReplyState(StatesGroup):
    waiting_reply = State()

# ========== КЛАВИАТУРЫ ==========
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Правила")],
        [KeyboardButton(text="🛒 Магазин")],
        [KeyboardButton(text="⚠️ Жалоба"), KeyboardButton(text="❓ Вопрос")],
        [KeyboardButton(text="ℹ️ Информация")]
    ],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

finish_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="✅ Отправить"), KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

def get_shop_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🍦 Ванильки", callback_data="shop_vanilla")
    builder.button(text="🎁 Привилегии", callback_data="shop_privilege")
    builder.button(text="💝 Поддержка", callback_data="shop_support")
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_privilege_kb():
    builder = InlineKeyboardBuilder()
    privileges = [
        ("🍃 VIP", 150), ("⭐ PREMIUM", 300), ("👑 DELUXE", 500),
        ("💎 LEGEND", 1000), ("⚡ ULTRA", 2000), ("🔱 TITAN", 3500), ("👾 GOD", 5000)
    ]
    for name, price in privileges:
        builder.button(text=f"{name} - {price}₽", callback_data=f"priv_{name}")
    builder.button(text="⬅️ Назад", callback_data="back_shop")
    builder.adjust(1)
    return builder.as_markup()

def get_vanilla_kb():
    builder = InlineKeyboardBuilder()
    for amount in [100, 250, 500, 1000]:
        builder.button(text=f"🍦 {amount}₽", callback_data=f"vanilla_{amount}")
    builder.button(text="✏️ Своя сумма", callback_data="vanilla_custom")
    builder.button(text="⬅️ Назад", callback_data="back_shop")
    builder.adjust(2)
    return builder.as_markup()

def get_reply_kb(ticket_id, user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ответить", callback_data=f"reply_{ticket_id}_{user_id}")
    builder.button(text="❌ Закрыть", callback_data=f"close_{ticket_id}")
    builder.adjust(2)
    return builder.as_markup()

# ========== БОТ ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    await msg.answer("🎮 Добро пожаловать!\n\nИспользуй кнопки 👇", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cmd_cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено", reply_markup=main_kb)

@dp.message(F.text == "📋 Правила")
async def cmd_rules(msg: types.Message):
    await msg.answer("📜 Правила:\n1. Не читерить\n2. Не гриферить\n3. Уважать других")

@dp.message(F.text == "ℹ️ Информация")
async def cmd_info(msg: types.Message):
    await msg.answer(f"🖥️ Сервер Vanilka\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}")

@dp.message(F.text == "🛒 Магазин")
async def cmd_shop(msg: types.Message):
    await msg.answer("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())

# ========== ЖАЛОБЫ ==========
@dp.message(F.text == "⚠️ Жалоба")
async def start_complaint(msg: types.Message, state: FSMContext):
    await state.set_state(Complaint.waiting_nick)
    await msg.answer("📝 Жалоба\n\nШаг 1/4: Твой ник?", reply_markup=cancel_kb)

@dp.message(Complaint.waiting_nick)
async def complaint_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cmd_cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(Complaint.waiting_offender)
    await msg.answer("Шаг 2/4: Ник нарушителя?", reply_markup=cancel_kb)

@dp.message(Complaint.waiting_offender)
async def complaint_offender(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cmd_cancel(msg, state)
        return
    await state.update_data(offender=msg.text)
    await state.set_state(Complaint.waiting_desc)
    await msg.answer("Шаг 3/4: Что произошло?", reply_markup=cancel_kb)

@dp.message(Complaint.waiting_desc)
async def complaint_desc(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cmd_cancel(msg, state)
        return
    await state.update_data(desc=msg.text)
    await state.update_data(media=[])
    await state.set_state(Complaint.waiting_media)
    await msg.answer("Шаг 4/4: Отправь доказательства (фото/видео)\n\nКогда закончишь, нажми ✅ Отправить", reply_markup=finish_kb)

@dp.message(Complaint.waiting_media)
async def complaint_media(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cmd_cancel(msg, state)
        return

    if msg.text == "✅ Отправить":
        data = await state.get_data()
        media = data.get("media", [])
        ticket_id = f"comp_{int(time.time())}"

        # Текст в канал
        text = f"⚠️ НОВАЯ ЖАЛОБА\n\nID: {ticket_id}\n👤 {data['nick']}\n🤬 {data['offender']}\n📝 {data['desc']}\n📎 Доказательств: {len(media)}"
        await bot.send_message(CHANNEL_ID, text)

        # Медиа в канал
        for m in media:
            if m['type'] == 'photo':
                await bot.send_photo(CHANNEL_ID, m['id'], caption=f"📸 от {data['nick']}")
            elif m['type'] == 'video':
                await bot.send_video(CHANNEL_ID, m['id'], caption=f"🎥 от {data['nick']}")

        # Уведомление админу в ЛС
        admin_text = f"📨 НОВАЯ ЖАЛОБА\n\nID: {ticket_id}\n👤 {data['nick']}\n🤬 {data['offender']}\n📝 {data['desc']}"
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_kb(ticket_id, msg.from_user.id))

        await msg.answer("✅ Жалоба отправлена!", reply_markup=main_kb)
        await state.clear()
        return

    # Сохраняем медиа
    data = await state.get_data()
    media = data.get("media", [])
    if msg.photo:
        media.append({"type": "photo", "id": msg.photo[-1].file_id})
        await msg.answer(f"📸 Добавлено (всего: {len(media)})")
    elif msg.video:
        media.append({"type": "video", "id": msg.video.file_id})
        await msg.answer(f"🎥 Добавлено (всего: {len(media)})")
    else:
        await msg.answer("Отправь фото или видео")
        return
    await state.update_data(media=media)

# ========== ВОПРОСЫ ==========
@dp.message(F.text == "❓ Вопрос")
async def start_question(msg: types.Message, state: FSMContext):
    await state.set_state(Question.waiting_nick)
    await msg.answer("❓ Вопрос\n\nШаг 1/2: Твой ник?", reply_markup=cancel_kb)

@dp.message(Question.waiting_nick)
async def question_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cmd_cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(Question.waiting_text)
    await msg.answer("Шаг 2/2: Твой вопрос?", reply_markup=cancel_kb)

@dp.message(Question.waiting_text)
async def question_text(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cmd_cancel(msg, state)
        return
    data = await state.get_data()
    ticket_id = f"q_{int(time.time())}"

    # В канал
    await bot.send_message(CHANNEL_ID, f"❓ НОВЫЙ ВОПРОС\n\nID: {ticket_id}\n👤 {data['nick']}\n💬 {msg.text}")

    # Админу в ЛС
    admin_text = f"📨 НОВЫЙ ВОПРОС\n\nID: {ticket_id}\n👤 {data['nick']}\n💬 {msg.text}"
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_kb(ticket_id, msg.from_user.id))

    await msg.answer("✅ Вопрос отправлен!", reply_markup=main_kb)
    await state.clear()

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(lambda c: c.data.startswith("reply_"))
async def start_reply(call: types.CallbackQuery, state: FSMContext):
    _, ticket_id, user_id = call.data.split("_")
    await state.update_data(reply_user=int(user_id), reply_ticket=ticket_id)
    await state.set_state(ReplyState.waiting_reply)
    await call.message.answer(f"✏️ Введи ответ для {ticket_id}:")
    await call.answer()

@dp.message(ReplyState.waiting_reply)
async def send_reply(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_user")
    ticket_id = data.get("reply_ticket")
    if not user_id:
        await msg.answer("❌ Ошибка")
        await state.clear()
        return
    try:
        await bot.send_message(user_id, f"📨 Ответ администратора\n\nПо обращению {ticket_id}:\n\n{msg.text}")
        await msg.answer(f"✅ Ответ отправлен!")
        await bot.send_message(CHANNEL_ID, f"📨 ОТВЕТ АДМИНА\n\nID: {ticket_id}\n💬 {msg.text}")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("close_"))
async def close_ticket(call: types.CallbackQuery):
    ticket_id = call.data.split("_")[1]
    await call.message.edit_text(f"{call.message.text}\n\n✅ Обращение {ticket_id} закрыто")
    await call.answer()

# ========== МАГАЗИН ==========
@dp.callback_query(F.data == "main_menu")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("Главное меню:", reply_markup=main_kb)
    await call.answer()

@dp.callback_query(F.data == "back_shop")
async def back_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(call: types.CallbackQuery):
    await call.message.edit_text("🍦 Пополнение Ванилек\n1₽ = 1 Ванилька\n\nВыбери сумму:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(call: types.CallbackQuery):
    await call.message.edit_text("🎁 Привилегии:", reply_markup=get_privilege_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_support")
async def shop_support(call: types.CallbackQuery):
    await call.message.edit_text(f"💝 Поддержка сервера\n\nСпасибо!\n\nКарта: {SBER_CARD}\n\nПосле перевода напиши @vanilka_support")
    await call.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_amount(call: types.CallbackQuery):
    amount = call.data.split("_")[1]
    if amount == "custom":
        await call.message.edit_text(f"🍦 Введи сумму\n\nКарта: {SBER_CARD}\n\nПосле перевода напиши @vanilka_support")
    else:
        await call.message.edit_text(f"🍦 Пополнение на {amount}₽\n\nКарта: {SBER_CARD}\n\nПосле перевода напиши @vanilka_support")
    await call.answer()

@dp.callback_query(F.data.startswith("priv_"))
async def privilege_buy(call: types.CallbackQuery):
    name = call.data.split("_")[1]
    await call.message.edit_text(f"🎁 Покупка {name}\n\nКарта: {SBER_CARD}\n\nПосле перевода напиши @vanilka_support")
    await call.answer()

# ========== ЗАПУСК ==========
async def main():
    logging.info("🚀 Запуск...")
    await bot.delete_webhook()
    logging.info("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
