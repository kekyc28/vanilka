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

class VanillaStates(StatesGroup):
    waiting_nick = State()

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
    builder.button(text="🍦 100₽", callback_data="vanilla_100")
    builder.button(text="🍦 250₽", callback_data="vanilla_250")
    builder.button(text="🍦 500₽", callback_data="vanilla_500")
    builder.button(text="🍦 1000₽", callback_data="vanilla_1000")
    builder.adjust(2)
    return builder.as_markup()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🎮 Выбери действие:", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено", reply_markup=main_kb)

@dp.message(F.text == "🍦 Ванильки")
async def show_vanilla(msg: types.Message):
    await msg.answer("🍦 Выбери сумму:", reply_markup=get_vanilla_kb())

@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_choose(call: types.CallbackQuery, state: FSMContext):
    amount = call.data.split("_")[1]
    await state.update_data(amount=amount)
    await state.set_state(VanillaStates.waiting_nick)
    await call.message.edit_text(f"🍦 Сумма: {amount}₽\n\nВведите свой игровой ник:")
    await call.answer()

@dp.message(VanillaStates.waiting_nick)
async def vanilla_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get('amount')
    nick = msg.text
    await msg.answer(f"✅ Получено!\n\nСумма: {amount}₽\nНик: {nick}\n\n(тут будут реквизиты)")
    await state.clear()
    await msg.answer("🎮 Вернулись в меню", reply_markup=main_kb)

@dp.message()
async def unknown(msg: types.Message):
    await msg.answer("Используй кнопки", reply_markup=main_kb)

async def main():
    logging.info("🚀 Запуск...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"✅ Бот запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
