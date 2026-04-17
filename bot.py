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

# ========== ПРОВЕРКА ПЕРЕМЕННЫХ ==========
TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise ValueError("❌ BOT_TOKEN не найден! Добавь переменную окружения BOT_TOKEN")

CHANNEL_ID = os.getenv("CHANNEL_ID")
if CHANNEL_ID is None:
    raise ValueError("❌ CHANNEL_ID не найден!")
try:
    CHANNEL_ID = int(CHANNEL_ID)
except ValueError:
    raise ValueError(f"❌ CHANNEL_ID должен быть числом! Получено: {CHANNEL_ID}")

ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID is None:
    raise ValueError("❌ ADMIN_ID не найден!")
try:
    ADMIN_ID = int(ADMIN_ID)
except ValueError:
    raise ValueError(f"❌ ADMIN_ID должен быть числом! Получено: {ADMIN_ID}")

SERVER_IP = os.getenv("SERVER_IP", "vanilka.minecraft.surf")
SERVER_VERSION = os.getenv("SERVER_VERSION", "1.21.11")
SBER_CARD = os.getenv("SBER_CARD", "2202205046722309")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ========== ПРИВИЛЕГИИ ==========
PRIVILEGES = [
    {"name": "🍃 VIP", "price": 150, "description": "🎁 /kit vip, 🎨 цвет в чате, 📦 3 дома"},
    {"name": "⭐ PREMIUM", "price": 300, "description": "✨ всё из VIP, 🏠 5 домов, 🔄 /fly"},
    {"name": "👑 DELUXE", "price": 500, "description": "👑 всё из PREMIUM, 🏠 10 домов, 💎 /ec"},
    {"name": "💎 LEGEND", "price": 1000, "description": "💎 всё из DELUXE, 🌟 эффект легенды"},
    {"name": "⚡ ULTRA", "price": 2000, "description": "⚡ всё из LEGEND, 🔥 /nick, 🚀 /speed"},
    {"name": "🔱 TITAN", "price": 3500, "description": "🔱 всё из ULTRA, 👑 команды Титана"},
    {"name": "👾 GOD", "price": 5000, "description": "👾 всё из TITAN, 🎨 свой цвет в чате"}
]

PRESET_DONATE_AMOUNTS = [100, 250, 500, 1000]

# ========== СОСТОЯНИЯ FSM ==========
class ComplaintStates(StatesGroup):
    waiting_for_nick = State()
    waiting_for_offender = State()
    waiting_for_description = State()
    waiting_for_proof = State()

class QuestionStates(StatesGroup):
    waiting_for_nick = State()
    waiting_for_question = State()

class VanillaDonateStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_nick = State()

class SupportStates(StatesGroup):
    waiting_for_nick = State()
    waiting_for_amount = State()

class PrivilegeStates(StatesGroup):
    waiting_for_nick = State()

class ReplyStates(StatesGroup):
    waiting_for_reply = State()

# ========== КЛАВИАТУРЫ ==========
def get_cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def get_finish_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Завершить и отправить жалобу")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Правила")],
        [KeyboardButton(text="🛒 Магазин")],
        [KeyboardButton(text="⚠️ Подать жалобу"), KeyboardButton(text="❓ Задать вопрос")],
        [KeyboardButton(text="ℹ️ Информация о сервере")]
    ], resize_keyboard=True)

def get_shop_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🍦 Пополнить Ванильки", callback_data="shop_vanilla")
    builder.button(text="🎁 Купить привилегию", callback_data="shop_privilege")
    builder.button(text="💝 Поддержать сервер", callback_data="shop_support")
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_privileges_keyboard():
    builder = InlineKeyboardBuilder()
    for p in PRIVILEGES:
        builder.button(text=f"{p['name']} - {p['price']}₽", callback_data=f"priv_{p['name']}")
    builder.button(text="⬅️ Назад в магазин", callback_data="back_to_shop")
    builder.adjust(1)
    return builder.as_markup()

def get_vanilla_keyboard():
    builder = InlineKeyboardBuilder()
    for amount in PRESET_DONATE_AMOUNTS:
        builder.button(text=f"🍦 {amount} Ванилек - {amount}₽", callback_data=f"vanilla_{amount}")
    builder.button(text="✏️ Своя сумма", callback_data="vanilla_custom")
    builder.button(text="⬅️ Назад", callback_data="back_to_shop")
    builder.adjust(1)
    return builder.as_markup()

def get_reply_keyboard(ticket_id: str, user_id: int):
    """Клавиатура для админа в ЛС"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ответить", callback_data=f"reply_{ticket_id}_{user_id}")
    builder.button(text="❌ Закрыть", callback_data=f"close_{ticket_id}")
    builder.adjust(2)
    return builder.as_markup()

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🎮 Добро пожаловать на сервер Vanilka!\n\nИспользуй кнопки ниже 👇", reply_markup=get_main_keyboard())

@dp.message(F.text == "❌ Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=get_main_keyboard())

@dp.message(F.text == "📋 Правила")
async def show_rules(message: types.Message):
    await message.answer("📜 Правила сервера Vanilka\n\n1️⃣ Уважайте других\n2️⃣ Запрещены читы\n3️⃣ Не гриферить\n4️⃣ Не спамить\n5️⃣ Не рекламировать\n\n⚠️ За нарушение — бан.")

@dp.message(F.text == "ℹ️ Информация о сервере")
async def show_server_info(message: types.Message):
    await message.answer(f"🖥️ Сервер Vanilka\n\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}\n🎮 Тип: Ванильный Minecraft")

@dp.message(F.text == "🛒 Магазин")
async def show_shop(message: types.Message):
    await message.answer("🛒 Магазин сервера Vanilka\n\nВыбери категорию 👇", reply_markup=get_shop_keyboard())

# ========== ЖАЛОБЫ ==========
@dp.message(F.text == "⚠️ Подать жалобу")
async def start_complaint(message: types.Message, state: FSMContext):
    await state.set_state(ComplaintStates.waiting_for_nick)
    await message.answer("📝 Подача жалобы\n\nШаг 1/4: Введите свой игровой ник:", reply_markup=get_cancel_keyboard())

@dp.message(ComplaintStates.waiting_for_nick)
async def complaint_get_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    await state.update_data(complainant_nick=message.text)
    await state.set_state(ComplaintStates.waiting_for_offender)
    await message.answer("Шаг 2/4: Введите ник нарушителя:", reply_markup=get_cancel_keyboard())

@dp.message(ComplaintStates.waiting_for_offender)
async def complaint_get_offender(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    await state.update_data(offender_nick=message.text)
    await state.set_state(ComplaintStates.waiting_for_description)
    await message.answer("Шаг 3/4: Опишите что произошло:", reply_markup=get_cancel_keyboard())

@dp.message(ComplaintStates.waiting_for_description)
async def complaint_get_description(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    await state.update_data(description=message.text)
    await state.set_state(ComplaintStates.waiting_for_proof)
    await state.update_data(proofs=[])
    await message.answer(
        "Шаг 4/4: Отправьте доказательства (фото, видео, файлы)\n\n"
        "Вы можете отправить несколько файлов по очереди.\n"
        "Когда закончите, нажмите «✅ Завершить и отправить жалобу»",
        reply_markup=get_finish_keyboard()
    )

@dp.message(ComplaintStates.waiting_for_proof)
async def complaint_add_proof(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return

    if message.text == "✅ Завершить и отправить жалобу":
        data = await state.get_data()
        proofs = data.get('proofs', [])
        ticket_id = f"complaint_{int(time.time())}_{message.from_user.id}"

        # Текст для канала
        complaint_text = (
            f"⚠️ НОВАЯ ЖАЛОБА ⚠️\n\n"
            f"🆔 ID: {ticket_id}\n"
            f"👤 Заявитель: {data['complainant_nick']}\n"
            f"🤬 Нарушитель: {data['offender_nick']}\n"
            f"📝 Описание: {data['description']}\n"
            f"📎 Доказательств: {len(proofs)}"
        )
        await bot.send_message(CHANNEL_ID, complaint_text)
        for p in proofs:
            if p['type'] == 'photo':
                await bot.send_photo(CHANNEL_ID, p['file_id'], caption=f"📸 Доказательство от {data['complainant_nick']}")
            elif p['type'] == 'video':
                await bot.send_video(CHANNEL_ID, p['file_id'], caption=f"🎥 Доказательство от {data['complainant_nick']}")
            elif p['type'] == 'document':
                await bot.send_document(CHANNEL_ID, p['file_id'], caption=f"📎 Доказательство от {data['complainant_nick']}")

        # Отправляем админу в ЛС с кнопками
        admin_text = (
            f"📨 НОВАЯ ЖАЛОБА\n\n"
            f"🆔 {ticket_id}\n"
            f"👤 Заявитель: {data['complainant_nick']}\n"
            f"🤬 Нарушитель: {data['offender_nick']}\n"
            f"📝 {data['description']}\n"
            f"👤 Telegram: @{message.from_user.username or 'нет ника'}"
        )
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_keyboard(ticket_id, message.from_user.id))

        # Убираем кнопки у пользователя
        await message.answer("✅ Жалоба отправлена! Администрация рассмотрит её в ближайшее время.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    # Добавляем доказательства
    data = await state.get_data()
    proofs = data.get('proofs', [])
    if message.photo:
        proofs.append({'type': 'photo', 'file_id': message.photo[-1].file_id})
        await message.answer(f"📸 Фото добавлено! (всего: {len(proofs)})")
    elif message.video:
        proofs.append({'type': 'video', 'file_id': message.video.file_id})
        await message.answer(f"🎥 Видео добавлено! (всего: {len(proofs)})")
    elif message.document:
        proofs.append({'type': 'document', 'file_id': message.document.file_id})
        await message.answer(f"📎 Файл добавлен! (всего: {len(proofs)})")
    else:
        await message.answer("❌ Отправьте фото, видео или файл")
        return
    await state.update_data(proofs=proofs)

# ========== ВОПРОСЫ ==========
@dp.message(F.text == "❓ Задать вопрос")
async def start_question(message: types.Message, state: FSMContext):
    await state.set_state(QuestionStates.waiting_for_nick)
    await message.answer("❓ Задать вопрос\n\nШаг 1/2: Введите свой игровой ник:", reply_markup=get_cancel_keyboard())

@dp.message(QuestionStates.waiting_for_nick)
async def question_get_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    await state.update_data(nick=message.text)
    await state.set_state(QuestionStates.waiting_for_question)
    await message.answer("Шаг 2/2: Напишите ваш вопрос:", reply_markup=get_cancel_keyboard())

@dp.message(QuestionStates.waiting_for_question)
async def question_get_text(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    data = await state.get_data()
    ticket_id = f"question_{int(time.time())}_{message.from_user.id}"

    question_text = f"❓ НОВЫЙ ВОПРОС ❓\n\n🆔 ID: {ticket_id}\n👤 Игрок: {data['nick']}\n💬 Вопрос: {message.text}"
    await bot.send_message(CHANNEL_ID, question_text)

    admin_text = (
        f"📨 НОВЫЙ ВОПРОС\n\n"
        f"🆔 {ticket_id}\n"
        f"👤 Игрок: {data['nick']}\n"
        f"💬 {message.text}\n"
        f"👤 Telegram: @{message.from_user.username or 'нет ника'}"
    )
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_keyboard(ticket_id, message.from_user.id))

    await message.answer("✅ Вопрос отправлен! Администрация ответит в ближайшее время.", reply_markup=get_main_keyboard())
    await state.clear()

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(lambda c: c.data.startswith("reply_"))
async def start_reply(callback: types.CallbackQuery, state: FSMContext):
    _, ticket_id, user_id = callback.data.split("_")
    await state.update_data(reply_user_id=int(user_id), reply_ticket_id=ticket_id)
    await state.set_state(ReplyStates.waiting_for_reply)
    await callback.message.answer(f"✏️ Введите ответ для обращения `{ticket_id}`:")
    await callback.answer()

@dp.message(ReplyStates.waiting_for_reply)
async def send_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_user_id')
    ticket_id = data.get('reply_ticket_id')

    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден.")
        await state.clear()
        return

    try:
        await bot.send_message(user_id, f"📨 **Ответ администратора**\n\nПо обращению `{ticket_id}`:\n\n{message.text}\n\n💡 Если остались вопросы — напишите снова.")
        await message.answer(f"✅ Ответ отправлен игроку (ID: {user_id})")
        await bot.send_message(CHANNEL_ID, f"📨 **Ответ администратора**\n🆔 {ticket_id}\n💬 {message.text}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("close_"))
async def close_ticket(callback: types.CallbackQuery):
    ticket_id = callback.data.split("_")[1]
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ Обращение `{ticket_id}` закрыто.")
    await callback.answer("Закрыто")

# ========== МАГАЗИН ==========
@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.message.answer("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "back_to_shop")
async def back_to_shop(callback: types.CallbackQuery):
    await callback.message.edit_text("🛒 Магазин сервера Vanilka\n\nВыбери категорию:", reply_markup=get_shop_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "shop_support")
async def shop_support(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.waiting_for_nick)
    await callback.message.edit_text("💝 Поддержка сервера\n\nВведите свой игровой ник:")
    await callback.answer()

@dp.message(SupportStates.waiting_for_nick)
async def support_get_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    await state.update_data(support_nick=message.text)
    await state.set_state(SupportStates.waiting_for_amount)
    await message.answer("💝 Введите сумму (от 10 до 100000 руб.):", reply_markup=get_cancel_keyboard())

@dp.message(SupportStates.waiting_for_amount)
async def support_get_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    if not re.match(r'^\d+$', message.text):
        await message.answer("❌ Введите число")
        return
    amount = int(message.text)
    if amount < 10 or amount > 100000:
        await message.answer("❌ Сумма от 10 до 100000")
        return
    data = await state.get_data()
    nick = data.get('support_nick')
    await message.answer(f"💝 Пожертвование\n\n👤 Ник: {nick}\n💰 {amount} руб.\n\n🏦 Сбербанк: {SBER_CARD}\n\n❗ После перевода напишите @vanilka_support с скриншотом и ником")
    await bot.send_message(CHANNEL_ID, f"💝 ПОЖЕРТВОВАНИЕ\n👤 {nick}\n💰 {amount} руб.")
    await state.clear()

@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(callback: types.CallbackQuery):
    await callback.message.edit_text("🍦 Пополнение Ванилек\n\nВыбери сумму:", reply_markup=get_vanilla_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def process_vanilla(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    if action == "custom":
        await state.set_state(VanillaDonateStates.waiting_for_amount)
        await callback.message.edit_text("🍦 Введите сумму (от 10 до 100000 руб.):\n1 рубль = 1 Ванилька")
        await callback.answer()
        return
    amount = int(action)
    await state.update_data(vanilla_amount=amount)
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await callback.message.edit_text(f"🍦 Сумма: {amount} руб.\n\nВведите свой игровой ник:")
    await callback.answer()

@dp.message(VanillaDonateStates.waiting_for_amount)
async def custom_vanilla_amount(message: types.Message, state: FSMContext):
    if not re.match(r'^\d+$', message.text):
        await message.answer("❌ Введите число")
        return
    amount = int(message.text)
    if amount < 10 or amount > 100000:
        await message.answer("❌ Сумма от 10 до 100000")
        return
    await state.update_data(vanilla_amount=amount)
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await message.answer(f"🍦 Сумма: {amount} руб.\n\nВведите игровой ник:", reply_markup=get_cancel_keyboard())

@dp.message(VanillaDonateStates.waiting_for_nick)
async def vanilla_get_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    data = await state.get_data()
    amount = data.get('vanilla_amount')
    nick = message.text
    await message.answer(f"🍦 Пополнение Ванилек\n\n💰 {amount} руб.\n🍦 {amount} Ванилек\n👤 {nick}\n\n🏦 Сбербанк: {SBER_CARD}\n\n❗ После перевода напишите @vanilka_support с скриншотом, ником и суммой")
    await bot.send_message(CHANNEL_ID, f"🍦 ПОПОЛНЕНИЕ ВАНИЛЕК\n👤 {nick}\n💰 {amount} руб.\n🍦 Ванилек: {amount}")
    await state.clear()

@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(callback: types.CallbackQuery):
    text = "🎁 Выбери привилегию:\n\n"
    for p in PRIVILEGES:
        text += f"{p['name']} — {p['price']}₽\n   └ {p['description']}\n\n"
    await callback.message.edit_text(text, reply_markup=get_privileges_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("priv_"))
async def process_privilege(callback: types.CallbackQuery, state: FSMContext):
    privilege_name = callback.data.split("priv_")[1]
    privilege = next((p for p in PRIVILEGES if p['name'] == privilege_name), None)
    if not privilege:
        await callback.answer("Ошибка")
        return
    await state.update_data(privilege_name=privilege['name'], privilege_price=privilege['price'])
    await state.set_state(PrivilegeStates.waiting_for_nick)
    await callback.message.edit_text(f"🎁 {privilege['name']}\n\n💰 Цена: {privilege['price']}₽\n📝 {privilege['description']}\n\nВведите свой игровой ник:")
    await callback.answer()

@dp.message(PrivilegeStates.waiting_for_nick)
async def privilege_get_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    data = await state.get_data()
    await message.answer(f"🎁 Покупка {data['privilege_name']}\n\n💰 {data['privilege_price']}₽\n👤 {message.text}\n\n🏦 Сбербанк: {SBER_CARD}\n\n❗ После перевода напишите @vanilka_support с скриншотом, ником и названием привилегии")
    await bot.send_message(CHANNEL_ID, f"🎁 ПОКУПКА ПРИВИЛЕГИИ\n👤 {message.text}\n🎁 {data['privilege_name']}\n💰 {data['privilege_price']}₽")
    await state.clear()

# ========== ЗАПУСК БОТА ==========
async def main():
    logger.info("🚀 Бот запускается...")
    me = await bot.get_me()
    logger.info(f"✅ Бот успешно запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
