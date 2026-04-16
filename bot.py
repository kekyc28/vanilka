import asyncio
import logging
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise ValueError("BOT_TOKEN не найден!")

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003965525902"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "2113717290"))  # 👈 НОВОЕ: твой Telegram ID
SERVER_IP = os.getenv("SERVER_IP", "vanilka.minecraft.surf")
SERVER_VERSION = os.getenv("SERVER_VERSION", "1.21.11")
SBER_CARD = os.getenv("SBER_CARD", "2202205046722309")

# ========== НОВОЕ: состояния для ответов ==========
class ReplyStates(StatesGroup):
    waiting_for_reply = State()  # для ответа на жалобу/вопрос

PRIVILEGES = [
    {"name": "🍃 VIP", "price": 150, "description": "🎁 /kit vip, 🎨 цвет в чате, 📦 3 дома"},
    {"name": "⭐ PREMIUM", "price": 300, "description": "✨ все привилегии VIP, 🏠 5 домов, 🔄 /fly"},
    {"name": "👑 DELUXE", "price": 500, "description": "👑 все привилегии PREMIUM, 🏠 10 домов, 💎 /ec"},
    {"name": "💎 LEGEND", "price": 1000, "description": "💎 все привилегии DELUXE, 🌟 эффект легенды"},
    {"name": "⚡ ULTRA", "price": 2000, "description": "⚡ все привилегии LEGEND, 🔥 /nick, 🚀 /speed"},
    {"name": "🔱 TITAN", "price": 3500, "description": "🔱 все привилегии ULTRA, 👑 доступ к командам Титана"},
    {"name": "👾 GOD", "price": 5000, "description": "👾 все привилегии TITAN, 🎨 свой цвет в чате"}
]

PRESET_DONATE_AMOUNTS = [100, 250, 500, 1000]

# ========== КОД БОТА ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# Состояния для форм
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

# Клавиатуры
def get_cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def get_finish_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Завершить и отправить жалобу")], [KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def get_main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📋 Правила")], [KeyboardButton(text="🛒 Магазин")], [KeyboardButton(text="⚠️ Подать жалобу"), KeyboardButton(text="❓ Задать вопрос")], [KeyboardButton(text="ℹ️ Информация о сервере")]], resize_keyboard=True)

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

# ========== НОВОЕ: клавиатура для ответа админу ==========
def get_reply_keyboard(user_id: int, complaint_id: str):
    """Кнопки для ответа на жалобу/вопрос"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Ответить", callback_data=f"reply_{complaint_id}_{user_id}")
    builder.button(text="✅ Закрыть", callback_data=f"close_{complaint_id}")
    builder.adjust(1)
    return builder.as_markup()

# ========== ОБРАБОТЧИКИ ==========
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

# ========== ЖАЛОБЫ (с отправкой админу) ==========
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
    await message.answer("Шаг 4/4: Отправьте доказательства (фото, видео, файлы)\n\nВы можете отправить несколько файлов по очереди.\nКогда закончите, нажмите «✅ Завершить и отправить жалобу»", reply_markup=get_finish_keyboard())

@dp.message(ComplaintStates.waiting_for_proof)
async def complaint_add_proof(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    
    if message.text == "✅ Завершить и отправить жалобу":
        data = await state.get_data()
        proofs = data.get('proofs', [])
        
        import time
        complaint_id = f"comp_{int(time.time())}_{message.from_user.id}"
        
        complaint_text = (
            f"⚠️ НОВАЯ ЖАЛОБА ⚠️\n\n"
            f"🆔 ID: {complaint_id}\n"
            f"👤 Заявитель: {data['complainant_nick']}\n"
            f"🤬 Нарушитель: {data['offender_nick']}\n"
            f"📝 Описание: {data['description']}\n"
            f"📎 Доказательств: {len(proofs)}"
        )
        
        await bot.send_message(CHANNEL_ID, complaint_text)
        
        for proof in proofs:
            if proof['type'] == 'photo':
                await bot.send_photo(CHANNEL_ID, proof['file_id'], caption=f"📸 Доказательство от {data['complainant_nick']}")
            elif proof['type'] == 'video':
                await bot.send_video(CHANNEL_ID, proof['file_id'], caption=f"🎥 Доказательство от {data['complainant_nick']}")
            elif proof['type'] == 'document':
                await bot.send_document(CHANNEL_ID, proof['file_id'], caption=f"📎 Доказательство от {data['complainant_nick']}")
        
        # ========== НОВОЕ: отправляем жалобу админу с кнопкой ответа ==========
        admin_text = (
            f"📨 Новая жалоба!\n\n"
            f"👤 Заявитель: {data['complainant_nick']}\n"
            f"👤 Telegram: @{message.from_user.username or message.from_user.first_name}\n"
            f"🤬 Нарушитель: {data['offender_nick']}\n"
            f"📝 Описание: {data['description']}\n"
            f"🆔 ID: {complaint_id}"
        )
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_keyboard(message.from_user.id, complaint_id))
        
        await message.answer("✅ Жалоба отправлена! Администрация рассмотрит её в ближайшее время.", reply_markup=get_main_keyboard())
        await state.clear()
        return
    
    data = await state.get_data()
    proofs = data.get('proofs', [])
    
    if message.photo:
        proofs.append({'type': 'photo', 'file_id': message.photo[-1].file_id})
        await message.answer(f"📸 Фото добавлено! (всего: {len(proofs)})\nОтправьте ещё или нажмите «Завершить»")
    elif message.video:
        proofs.append({'type': 'video', 'file_id': message.video.file_id})
        await message.answer(f"🎥 Видео добавлено! (всего: {len(proofs)})\nОтправьте ещё или нажмите «Завершить»")
    elif message.document:
        proofs.append({'type': 'document', 'file_id': message.document.file_id})
        await message.answer(f"📎 Файл добавлен! (всего: {len(proofs)})\nОтправьте ещё или нажмите «Завершить»")
    else:
        await message.answer("❌ Пожалуйста, отправьте фото, видео или файл в качестве доказательства.\n\nИли нажмите «✅ Завершить и отправить жалобу»")
        return
    
    await state.update_data(proofs=proofs)

# ========== ВОПРОСЫ (с отправкой админу) ==========
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
    
    import time
    question_id = f"q_{int(time.time())}_{message.from_user.id}"
    
    question_text = (
        f"❓ НОВЫЙ ВОПРОС ❓\n\n"
        f"🆔 ID: {question_id}\n"
        f"👤 Игрок: {data['nick']}\n"
        f"💬 Вопрос: {message.text}"
    )
    await bot.send_message(CHANNEL_ID, question_text)
    
    # ========== НОВОЕ: отправляем вопрос админу с кнопкой ответа ==========
    admin_text = (
        f"📨 Новый вопрос!\n\n"
        f"👤 Игрок: {data['nick']}\n"
        f"👤 Telegram: @{message.from_user.username or message.from_user.first_name}\n"
        f"💬 Вопрос: {message.text}\n"
        f"🆔 ID: {question_id}"
    )
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_keyboard(message.from_user.id, question_id))
    
    await message.answer("✅ Вопрос отправлен! Администрация ответит в ближайшее время.", reply_markup=get_main_keyboard())
    await state.clear()

# ========== НОВОЕ: обработка ответов админа ==========
@dp.callback_query(lambda c: c.data.startswith("reply_"))
async def start_reply(callback: types.CallbackQuery, state: FSMContext):
    """Когда админ нажимает "Ответить" на жалобу/вопрос"""
    _, complaint_id, user_id = callback.data.split("_")
    await state.update_data(reply_user_id=int(user_id), reply_complaint_id=complaint_id)
    await state.set_state(ReplyStates.waiting_for_reply)
    await callback.message.answer("💬 Введите ваш ответ для игрока:")
    await callback.answer()

@dp.message(ReplyStates.waiting_for_reply)
async def send_reply(message: types.Message, state: FSMContext):
    """Отправка ответа игроку"""
    data = await state.get_data()
    user_id = data.get('reply_user_id')
    complaint_id = data.get('reply_complaint_id')
    
    if not user_id:
        await message.answer("❌ Ошибка: не найден пользователь для ответа.")
        await state.clear()
        return
    
    # Отправляем ответ игроку
    try:
        await bot.send_message(
            user_id,
            f"📨 **Ответ администратора**\n\n"
            f"По вашему обращению `{complaint_id}`:\n\n"
            f"{message.text}\n\n"
            f"💡 Если у вас остались вопросы — напишите снова."
        )
        await message.answer(f"✅ Ответ отправлен игроку (ID: {user_id})")
        
        # Дублируем в канал для истории
        await bot.send_message(
            CHANNEL_ID,
            f"📨 **Ответ администратора**\n"
            f"🆔 Обращение: {complaint_id}\n"
            f"💬 Ответ: {message.text}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: не удалось отправить ответ. Возможно, игрок заблокировал бота.\nОшибка: {e}")
    
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("close_"))
async def close_complaint(callback: types.CallbackQuery):
    """Закрыть обращение (без ответа)"""
    complaint_id = callback.data.split("_")[1]
    await callback.message.edit_text(f"{callback.message.text}\n\n✅ Обращение {complaint_id} закрыто.")
    await callback.answer("Обращение закрыто")

# ========== ИНЛАЙН КНОПКИ МАГАЗИНА ==========
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
    await callback.message.edit_text("💝 Поддержка сервера\n\nСпасибо, что хотите помочь проекту!\n\nВведите свой игровой ник:")
    await callback.answer()

@dp.message(SupportStates.waiting_for_nick)
async def support_get_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    await state.update_data(support_nick=message.text)
    await state.set_state(SupportStates.waiting_for_amount)
    await message.answer("💝 Введите сумму пожертвования в рублях (от 10 до 100000):\n\nПожертвования не дают игровых преимуществ, но помогают серверу развиваться!", reply_markup=get_cancel_keyboard())

@dp.message(SupportStates.waiting_for_amount)
async def support_get_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    
    if not re.match(r'^\d+$', message.text):
        await message.answer("❌ Пожалуйста, введите целое число (например: 500)")
        return
    
    amount = int(message.text)
    if amount < 10:
        await message.answer("❌ Минимальная сумма пожертвования — 10 рублей")
        return
    if amount > 100000:
        await message.answer("❌ Максимальная сумма — 100 000 рублей")
        return
    
    data = await state.get_data()
    nick = data.get('support_nick')
    
    support_text = (
        f"💝 Пожертвование в поддержку сервера\n\n"
        f"👤 Ваш игровой ник: {nick}\n"
        f"💰 Сумма: {amount} руб.\n\n"
        f"🏦 Сбербанк: {SBER_CARD}\n\n"
        f"❗ После перевода напишите администратору @vanilka_support с:\n"
        f"• Скриншотом перевода\n"
        f"• Своим игровым ником: {nick}\n"
        f"• Суммой перевода: {amount} руб.\n\n"
        f"Спасибо за поддержку сервера! 🙏"
    )
    
    await message.answer(support_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="back_to_shop")]
    ]))
    
    await bot.send_message(
        CHANNEL_ID,
        f"💝 НОВОЕ ПОЖЕРТВОВАНИЕ 💝\n\n"
        f"👤 Игровой ник: {nick}\n"
        f"💰 Сумма: {amount} руб."
    )
    
    await state.clear()

@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(callback: types.CallbackQuery):
    vanilla_text = "🍦 Пополнение Ванилек\n\nВыберите сумму или укажите свою:"
    await callback.message.edit_text(vanilla_text, reply_markup=get_vanilla_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def process_vanilla_donate(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]
    
    if action == "custom":
        await state.set_state(VanillaDonateStates.waiting_for_amount)
        await callback.message.edit_text(
            "🍦 Введите сумму пополнения в рублях (целое число от 10 до 100000):\n\n"
            "1 рубль = 1 Ванилька"
        )
        await callback.answer()
        return
    
    amount = int(action)
    await state.update_data(vanilla_amount=amount)
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await callback.message.edit_text(f"🍦 Вы выбрали сумму {amount} руб.\n\nТеперь введите свой игровой ник:")
    await callback.answer()

@dp.message(VanillaDonateStates.waiting_for_amount)
async def process_custom_vanilla_amount(message: types.Message, state: FSMContext):
    if not re.match(r'^\d+$', message.text):
        await message.answer("❌ Пожалуйста, введите целое число (например: 500)")
        return
    
    amount = int(message.text)
    if amount < 10:
        await message.answer("❌ Минимальная сумма пополнения — 10 рублей")
        return
    if amount > 100000:
        await message.answer("❌ Максимальная сумма пополнения — 100 000 рублей")
        return
    
    await state.update_data(vanilla_amount=amount)
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await message.answer(f"🍦 Сумма: {amount} руб.\n\nТеперь введите свой игровой ник:", reply_markup=get_cancel_keyboard())

@dp.message(VanillaDonateStates.waiting_for_nick)
async def process_vanilla_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    
    data = await state.get_data()
    amount = data.get('vanilla_amoun')
