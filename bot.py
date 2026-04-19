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

# ========== Состояние для жалобы ==========
class ComplaintStates(StatesGroup):
    waiting_nick = State()
    waiting_offender = State()
    waiting_desc = State()
    waiting_media = State()

# ========== Клавиатура ==========
main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⚠️ Жалоба")],
        [KeyboardButton(text="❌ Отмена")]
    ],
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
    await msg.answer("🎮 Тестовый бот. Нажми «Жалоба»", reply_markup=main_kb)

# ========== Отмена ==========
@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Отменено", reply_markup=main_kb)

# ========== Начало жалобы ==========
@dp.message(F.text == "⚠️ Жалоба")
async def complaint_start(msg: types.Message, state: FSMContext):
    await state.set_state(ComplaintStates.waiting_nick)
    await msg.answer("📝 Шаг 1/4: Введите свой игровой ник (можно любой текст):", reply_markup=cancel_kb)

# ========== Получение ника (принимает ЛЮБОЙ текст) ==========
@dp.message(ComplaintStates.waiting_nick)
async def complaint_nick(msg: types.Message, state: FSMContext):
    # Этот обработчик сработает для ЛЮБОГО сообщения, когда мы в состоянии waiting_nick
    await state.update_data(nick=msg.text)
    await state.set_state(ComplaintStates.waiting_offender)
    await msg.answer(f"✅ Ник принят: {msg.text}\n\nШаг 2/4: Введите ник нарушителя:", reply_markup=cancel_kb)

# ========== Получение нарушителя ==========
@dp.message(ComplaintStates.waiting_offender)
async def complaint_offender(msg: types.Message, state: FSMContext):
    await state.update_data(offender=msg.text)
    await state.set_state(ComplaintStates.waiting_desc)
    await msg.answer(f"✅ Нарушитель: {msg.text}\n\nШаг 3/4: Опишите, что произошло:", reply_markup=cancel_kb)

# ========== Получение описания ==========
@dp.message(ComplaintStates.waiting_desc)
async def complaint_desc(msg: types.Message, state: FSMContext):
    await state.update_data(desc=msg.text)
    await state.set_state(ComplaintStates.waiting_media)
    await msg.answer(f"✅ Описание: {msg.text}\n\nШаг 4/4: Отправьте доказательства (фото/видео) или нажмите «✅ Готово»", 
                     reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Готово")], [KeyboardButton(text="❌ Отмена")]], resize_keyboard=True))

# ========== Завершение ==========
@dp.message(ComplaintStates.waiting_media)
async def complaint_media(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if msg.text == "✅ Готово":
        data = await state.get_data()
        await msg.answer(f"✅ Жалоба отправлена!\n\nДанные:\nНик: {data['nick']}\nНарушитель: {data['offender']}\nОписание: {data['desc']}", reply_markup=main_kb)
        await state.clear()
        return
    # Если отправили фото/видео
    if msg.photo or msg.video:
        await msg.answer("📎 Доказательства получены! Нажмите «✅ Готово» для отправки жалобы.")
    else:
        await msg.answer("❌ Отправьте фото/видео или нажмите «✅ Готово»")

# ========== Обработчик неизвестных сообщений (только когда нет состояния) ==========
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
