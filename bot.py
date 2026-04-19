import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

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

SERVER_IP = os.getenv("SERVER_IP", "play.yourserver.com")
SERVER_VERSION = os.getenv("SERVER_VERSION", "1.21.11")
SBER_CARD = os.getenv("SBER_CARD", "1234567890123456")

# ========== Состояния ==========
class Form(StatesGroup):
    vanilla_nick = State()

# ========== Клавиатуры ==========
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Правила")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="🚪 Проходка")],
        [KeyboardButton(text="⚠️ Жалоба"), KeyboardButton(text="❓ Вопрос")],
        [KeyboardButton(text="ℹ️ Информация")]
    ],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
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

def get_vanilla_kb():
    builder = InlineKeyboardBuilder()
    for amount in [100, 250, 500, 1000]:
        builder.button(text=f"🍦 {amount}₽", callback_data=f"vanilla_{amount}")
    builder.button(text="✏️ Своя сумма", callback_data="vanilla_custom")
    builder.button(text="⬅️ Назад", callback_data="back_shop")
    builder.adjust(2)
    return builder.as_markup()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== ОСНОВНЫЕ КОМАНДЫ (заглушки) ==========
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🎮 Добро пожаловать на сервер Vanilka!", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено", reply_markup=main_kb)

@dp.message(F.text == "📋 Правила")
async def rules(msg: types.Message):
    await msg.answer("📜 Правила сервера (заглушка)")

@dp.message(F.text == "ℹ️ Информация")
async def info(msg: types.Message):
    await msg.answer(f"🖥️ Сервер Vanilka\nIP: {SERVER_IP}\nВерсия: {SERVER_VERSION}")

@dp.message(F.text == "🛒 Магазин")
async def shop(msg: types.Message):
    await msg.answer("🛒 Магазин\n\nВыбери категорию", reply_markup=get_shop_kb())

@dp.message(F.text == "🚪 Проходка")
async def access_start(msg: types.Message):
    await msg.answer("🚪 Проходка (заглушка)")

@dp.message(F.text == "⚠️ Жалоба")
async def complaint_start(msg: types.Message):
    await msg.answer("⚠️ Жалоба (заглушка)")

@dp.message(F.text == "❓ Вопрос")
async def question_start(msg: types.Message):
    await msg.answer("❓ Вопрос (заглушка)")

# ========== ВАНИЛЬКИ (РАБОТАЕТ) ==========
@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(call: types.CallbackQuery):
    await call.message.edit_text("🍦 Ванильки\n1₽ = 1 Ванилька\n\nВыбери сумму:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_buy(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    if action == "custom":
        await state.set_state(Form.vanilla_nick)
        await call.message.edit_text("🍦 Введите сумму (10-100000₽):")
        await call.answer()
        return
    amount = int(action)
    await state.update_data(amount=amount)
    await state.set_state(Form.vanilla_nick)
    await call.message.edit_text(f"🍦 Сумма: {amount}₽\n\nВведите игровой ник:")
    await call.answer()

@dp.message(Form.vanilla_nick)
async def vanilla_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get('amount')
    nick = msg.text
    await msg.answer(f"✅ ПОЛУЧЕНО!\n\nСумма: {amount}₽\nНик: {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты напишите @vanilka_support")
    await state.clear()
    await msg.answer("Вернулись в меню", reply_markup=main_kb)

# ========== КОЛБЭКИ ==========
@dp.callback_query(F.data == "main_menu")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("🏠 Главное меню:", reply_markup=main_kb)
    await call.answer()

@dp.callback_query(F.data == "back_shop")
async def back_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(call: types.CallbackQuery):
    await call.message.edit_text("🎁 Привилегии (заглушка)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_shop")]]))
    await call.answer()

@dp.callback_query(F.data == "shop_support")
async def shop_support(call: types.CallbackQuery):
    await call.message.edit_text("💝 Поддержка (заглушка)", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_shop")]]))
    await call.answer()

# ========== НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ==========
@dp.message()
async def unknown(msg: types.Message):
    if msg.text not in ["📋 Правила", "🛒 Магазин", "🚪 Проходка", "⚠️ Жалоба", "❓ Вопрос", "ℹ️ Информация", "❌ Отмена"]:
        await msg.answer("🤔 Используйте кнопки меню", reply_markup=main_kb)

# ========== ЗАПУСК ==========
async def main():
    logging.info("🚀 Запуск...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"✅ Бот запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
