import asyncio
import logging
import os
import re
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

try:
    CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
except ValueError:
    raise ValueError("CHANNEL_ID и ADMIN_ID должны быть числами!")

SERVER_IP = os.getenv("SERVER_IP", "vanilka.minecraft.surf")
SERVER_VERSION = os.getenv("SERVER_VERSION", "1.21.11")
SBER_CARD = os.getenv("SBER_CARD", "2202205046722309")

# Привилегии
PRIVILEGES = [
    {"name": "VIP", "price": 150, "emoji": "🍃"},
    {"name": "PREMIUM", "price": 300, "emoji": "⭐"},
    {"name": "DELUXE", "price": 500, "emoji": "👑"},
    {"name": "LEGEND", "price": 1000, "emoji": "💎"},
    {"name": "ULTRA", "price": 2000, "emoji": "⚡"},
    {"name": "TITAN", "price": 3500, "emoji": "🔱"},
    {"name": "GOD", "price": 5000, "emoji": "👾"}
]

PRESET_AMOUNTS = [100, 250, 500, 1000]

# ========== СОСТОЯНИЯ ==========
class ComplaintState(StatesGroup):
    nick = State()
    offender = State()
    description = State()
    proof = State()

class QuestionState(StatesGroup):
    nick = State()
    question = State()

class DonateState(StatesGroup):
    amount = State()
    nick = State()

class SupportState(StatesGroup):
    nick = State()
    amount = State()

class PrivilegeState(StatesGroup):
    nick = State()

class ReplyState(StatesGroup):
    text = State()

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
    keyboard=[
        [KeyboardButton(text="✅ Отправить")],
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)

# Инлайн кнопки
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
    for p in PRIVILEGES:
        builder.button(text=f"{p['emoji']} {p['name']} - {p['price']}₽", callback_data=f"priv_{p['name']}")
    builder.button(text="⬅️ Назад", callback_data="back_shop")
    builder.adjust(1)
    return builder.as_markup()

def get_vanilla_kb():
    builder = InlineKeyboardBuilder()
    for a in PRESET_AMOUNTS:
        builder.button(text=f"🍦 {a}₽", callback_data=f"vanilla_{a}")
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

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🎮 Добро пожаловать на сервер Vanilka!\n\nИспользуй кнопки ниже 👇", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено", reply_markup=main_kb)

@dp.message(F.text == "📋 Правила")
async def rules(msg: types.Message):
    await msg.answer("📜 Правила:\n1. Не читерить\n2. Не гриферить\n3. Уважать других")

@dp.message(F.text == "ℹ️ Информация")
async def info(msg: types.Message):
    await msg.answer(f"🖥️ Сервер Vanilka\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}")

@dp.message(F.text == "🛒 Магазин")
async def shop(msg: types.Message):
    await msg.answer("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())

# ========== ЖАЛОБЫ ==========
@dp.message(F.text == "⚠️ Жалоба")
async def complaint_start(msg: types.Message, state: FSMContext):
    await state.set_state(ComplaintState.nick)
    await msg.answer("📝 Жалоба\n\nШаг 1/4: Твой ник?", reply_markup=cancel_kb)

@dp.message(ComplaintState.nick)
async def complaint_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(ComplaintState.offender)
    await msg.answer("Шаг 2/4: Ник нарушителя?")

@dp.message(ComplaintState.offender)
async def complaint_offender(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(offender=msg.text)
    await state.set_state(ComplaintState.description)
    await msg.answer("Шаг 3/4: Что произошло?")

@dp.message(ComplaintState.description)
async def complaint_desc(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(desc=msg.text)
    await state.update_data(proofs=[])
    await state.set_state(ComplaintState.proof)
    await msg.answer("Шаг 4/4: Отправь доказательства (фото/видео)\n\nКогда закончишь - нажми ✅ Отправить", reply_markup=finish_kb)

@dp.message(ComplaintState.proof)
async def complaint_proof(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return

    if msg.text == "✅ Отправить":
        data = await state.get_data()
        proofs = data.get("proofs", [])
        ticket_id = f"comp_{int(time.time())}"

        # В канал
        text = f"⚠️ ЖАЛОБА\nID: {ticket_id}\n👤 {data['nick']}\n🤬 {data['offender']}\n📝 {data['desc']}\n📎 Доказательств: {len(proofs)}"
        await bot.send_message(CHANNEL_ID, text)
        for p in proofs:
            if p['type'] == 'photo':
                await bot.send_photo(CHANNEL_ID, p['id'], caption=f"📸 от {data['nick']}")
            elif p['type'] == 'video':
                await bot.send_video(CHANNEL_ID, p['id'], caption=f"🎥 от {data['nick']}")

        # Админу в ЛС
        admin_text = f"📨 ЖАЛОБА\nID: {ticket_id}\n👤 {data['nick']}\n🤬 {data['offender']}\n📝 {data['desc']}"
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_kb(ticket_id, msg.from_user.id))

        await msg.answer("✅ Жалоба отправлена!", reply_markup=main_kb)
        await state.clear()
        return

    # Сохраняем доказательства
    data = await state.get_data()
    proofs = data.get("proofs", [])
    if msg.photo:
        proofs.append({"type": "photo", "id": msg.photo[-1].file_id})
        await msg.answer(f"📸 Добавлено (всего: {len(proofs)})")
    elif msg.video:
        proofs.append({"type": "video", "id": msg.video.file_id})
        await msg.answer(f"🎥 Добавлено (всего: {len(proofs)})")
    else:
        await msg.answer("Отправь фото или видео")
        return
    await state.update_data(proofs=proofs)

# ========== ВОПРОСЫ ==========
@dp.message(F.text == "❓ Вопрос")
async def question_start(msg: types.Message, state: FSMContext):
    await state.set_state(QuestionState.nick)
    await msg.answer("❓ Вопрос\n\nШаг 1/2: Твой ник?", reply_markup=cancel_kb)

@dp.message(QuestionState.nick)
async def question_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(QuestionState.question)
    await msg.answer("Шаг 2/2: Твой вопрос?")

@dp.message(QuestionState.question)
async def question_text(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    ticket_id = f"q_{int(time.time())}"

    # В канал
    await bot.send_message(CHANNEL_ID, f"❓ ВОПРОС\nID: {ticket_id}\n👤 {data['nick']}\n💬 {msg.text}")

    # Админу в ЛС
    admin_text = f"📨 ВОПРОС\nID: {ticket_id}\n👤 {data['nick']}\n💬 {msg.text}"
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_kb(ticket_id, msg.from_user.id))

    await msg.answer("✅ Вопрос отправлен!", reply_markup=main_kb)
    await state.clear()

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(lambda c: c.data.startswith("reply_"))
async def reply_start(call: types.CallbackQuery, state: FSMContext):
    _, ticket_id, user_id = call.data.split("_")
    await state.update_data(reply_user=int(user_id), reply_ticket=ticket_id)
    await state.set_state(ReplyState.text)
    await call.message.answer(f"✏️ Ответ для {ticket_id}:")
    await call.answer()

@dp.message(ReplyState.text)
async def reply_send(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("reply_user")
    ticket_id = data.get("reply_ticket")
    if not user_id:
        await msg.answer("Ошибка")
        await state.clear()
        return
    try:
        await bot.send_message(user_id, f"📨 Ответ админа\nПо обращению {ticket_id}:\n\n{msg.text}")
        await msg.answer("✅ Отправлено!")
        await bot.send_message(CHANNEL_ID, f"📨 Ответ\nID: {ticket_id}\n💬 {msg.text}")
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("close_"))
async def reply_close(call: types.CallbackQuery):
    ticket_id = call.data.split("_")[1]
    await call.message.edit_text(f"{call.message.text}\n\n✅ Закрыто")
    await call.answer()

# ========== МАГАЗИН (инлайн) ==========
@dp.callback_query(F.data == "main_menu")
async def cb_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("Главное меню:", reply_markup=main_kb)
    await call.answer()

@dp.callback_query(F.data == "back_shop")
async def cb_back_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_vanilla")
async def cb_vanilla(call: types.CallbackQuery):
    await call.message.edit_text("🍦 Пополнение Ванилек\n1₽ = 1 Ванилька\n\nВыбери сумму:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_privilege")
async def cb_privilege_list(call: types.CallbackQuery):
    await call.message.edit_text("🎁 Привилегии:", reply_markup=get_privilege_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_support")
async def cb_support(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.nick)
    await call.message.edit_text("💝 Поддержка сервера\n\nТвой игровой ник?")
    await call.answer()

@dp.message(SupportState.nick)
async def support_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(SupportState.amount)
    await msg.answer("💰 Сумма (от 10 до 100000 руб.):", reply_markup=cancel_kb)

@dp.message(SupportState.amount)
async def support_amount(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if not msg.text.isdigit():
        await msg.answer("Введи число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("Сумма от 10 до 100000")
        return
    data = await state.get_data()
    await msg.answer(f"💝 Пожертвование\n👤 {data['nick']}\n💰 {amount}₽\n\n🏦 Карта: {SBER_CARD}\n\nПосле перевода напиши @vanilka_support", reply_markup=main_kb)
    await bot.send_message(CHANNEL_ID, f"💝 Пожертвование\n👤 {data['nick']}\n💰 {amount}₽")
    await state.clear()

@dp.callback_query(F.data.startswith("vanilla_"))
async def cb_vanilla_amount(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    if action == "custom":
        await state.set_state(DonateState.amount)
        await call.message.edit_text("🍦 Введи сумму (от 10 до 100000):")
        await call.answer()
        return
    amount = int(action)
    await state.update_data(amount=amount)
    await state.set_state(DonateState.nick)
    await call.message.edit_text(f"🍦 Сумма: {amount}₽\n\nТвой игровой ник?")
    await call.answer()

@dp.message(DonateState.amount)
async def donate_amount(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("Введи число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("Сумма от 10 до 100000")
        return
    await state.update_data(amount=amount)
    await state.set_state(DonateState.nick)
    await msg.answer(f"🍦 Сумма: {amount}₽\n\nТвой игровой ник?", reply_markup=cancel_kb)

@dp.message(DonateState.nick)
async def donate_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    await msg.answer(f"🍦 Ванильки\n💰 {data['amount']}₽\n🍦 {data['amount']} Ванилек\n👤 {msg.text}\n\n🏦 Карта: {SBER_CARD}\n\nПосле перевода напиши @vanilka_support", reply_markup=main_kb)
    await bot.send_message(CHANNEL_ID, f"🍦 Пополнение\n👤 {msg.text}\n💰 {data['amount']}₽")
    await state.clear()

@dp.callback_query(F.data.startswith("priv_"))
async def cb_privilege_buy(call: types.CallbackQuery, state: FSMContext):
    name = call.data.split("_")[1]
    priv = next((p for p in PRIVILEGES if p['name'] == name), None)
    if not priv:
        await call.answer("Ошибка")
        return
    await state.update_data(priv_name=priv['name'], priv_price=priv['price'])
    await state.set_state(PrivilegeState.nick)
    await call.message.edit_text(f"🎁 {priv['emoji']} {priv['name']}\n💰 {priv['price']}₽\n\nТвой игровой ник?")
    await call.answer()

@dp.message(PrivilegeState.nick)
async def privilege_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    await msg.answer(f"🎁 {data['priv_name']}\n💰 {data['priv_price']}₽\n👤 {msg.text}\n\n🏦 Карта: {SBER_CARD}\n\nПосле перевода напиши @vanilka_support", reply_markup=main_kb)
    await bot.send_message(CHANNEL_ID, f"🎁 Покупка\n👤 {msg.text}\n🎁 {data['priv_name']}\n💰 {data['priv_price']}₽")
    await state.clear()

# ========== ЗАПУСК ==========
async def main():
    logging.info("🚀 Бот запускается...")
    await bot.delete_webhook()
    logging.info("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
