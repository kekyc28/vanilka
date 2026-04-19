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

SBER_CARD = os.getenv("SBER_CARD", "1234567890123456")

# ========== Состояние ==========
class Form(StatesGroup):
    vanilla_nick = State()

# ========== Клавиатуры ==========
main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🍦 Ванильки")]],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

def get_vanilla_kb():
    builder = InlineKeyboardBuilder()
    for amount in [100, 250, 500, 1000]:
        builder.button(text=f"🍦 {amount}₽", callback_data=f"vanilla_{amount}")
    builder.button(text="✏️ Своя сумма", callback_data="vanilla_custom")
    builder.adjust(2)
    return builder.as_markup()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🎮 Нажми «🍦 Ванильки»", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено", reply_markup=main_kb)

@dp.message(F.text == "🍦 Ванильки")
async def show_vanilla(msg: types.Message):
    await msg.answer("🍦 Выбери сумму:", reply_markup=get_vanilla_kb())

@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_choose(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    logging.info(f"Выбрано действие: {action}")
    
    if action == "custom":
        await state.set_state(Form.vanilla_nick)
        await call.message.edit_text("🍦 Введите сумму (10-100000₽):")
        await call.answer()
        return
    
    amount = int(action)
    await state.update_data(amount=amount)
    await state.set_state(Form.vanilla_nick)
    await call.message.edit_text(f"🍦 Сумма: {amount}₽\n\nВведите свой игровой ник (ЛЮБОЙ ТЕКСТ):")
    await call.answer()
    logging.info(f"Состояние установлено: {await state.get_state()}")

@dp.message(Form.vanilla_nick)
async def vanilla_nick(msg: types.Message, state: FSMContext):
    current_state = await state.get_state()
    logging.info(f"Сообщение получено в состоянии: {current_state}")
    logging.info(f"Текст сообщения: {msg.text}")
    
    data = await state.get_data()
    amount = data.get('amount')
    
    if amount is None:
        await msg.answer("❌ Ошибка: сумма не найдена. Начните заново.", reply_markup=main_kb)
        await state.clear()
        return
    
    nick = msg.text
    await msg.answer(
        f"✅ ПОЛУЧЕНО!\n\n"
        f"Сумма: {amount}₽\n"
        f"Ник: {nick}\n\n"
        f"🏦 Карта: {SBER_CARD}\n\n"
        f"📌 После оплаты напишите @vanilka_support",
        reply_markup=main_kb
    )
    await state.clear()

@dp.message()
async def unknown(msg: types.Message):
    logging.info(f"Неизвестное сообщение: {msg.text}")
    await msg.answer("Используй кнопки", reply_markup=main_kb)

async def main():
    logging.info("🚀 Запуск...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"✅ Бот запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
