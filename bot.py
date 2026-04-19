import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ========== Переменные ==========
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не найден!")

# ========== Состояние ==========
class Form(StatesGroup):
    waiting_for_text = State()

# ========== Клавиатура ==========
main_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="📝 Тест")]],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True
)

# ========== Инициализация ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== Команда /start ==========
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🎮 Тестовый бот. Нажми «Тест»", reply_markup=main_kb)

# ========== Кнопка "Тест" ==========
@dp.message(F.text == "📝 Тест")
async def test_button(msg: types.Message, state: FSMContext):
    await state.set_state(Form.waiting_for_text)
    await msg.answer("Введите ЛЮБОЙ текст (хоть 1000 символов):", reply_markup=cancel_kb)

# ========== Отмена ==========
@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("Отменено", reply_markup=main_kb)

# ========== Обработчик текста (принимает ЛЮБОЙ текст) ==========
@dp.message(Form.waiting_for_text)
async def get_text(msg: types.Message, state: FSMContext):
    # Этот обработчик сработает на ЛЮБОЕ сообщение в состоянии waiting_for_text
    text = msg.text
    length = len(text)
    await msg.answer(f"✅ Получено!\n\nТекст: {text}\n\nДлина: {length} символов.\n\nМожно писать любые длинные сообщения!", reply_markup=main_kb)
    await state.clear()

# ========== Остальные сообщения ==========
@dp.message()
async def unknown(msg: types.Message):
    await msg.answer("Я вас не понимаю. Используйте кнопки.", reply_markup=main_kb)

# ========== Запуск ==========
async def main():
    logging.info("🚀 Тестовый бот запускается...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"✅ Тестовый бот запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
