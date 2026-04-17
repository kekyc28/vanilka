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

# Привилегии
PRIVILEGES = [
    {"name": "🍃 VIP", "price": 150, "description": "🎁 /kit vip, 🎨 цвет в чате, 📦 3 дома"},
    {"name": "⭐ PREMIUM", "price": 300, "description": "✨ все привилегии VIP, 🏠 5 домов, 🔄 /fly"},
    {"name": "👑 DELUXE", "price": 500, "description": "👑 все привилегии PREMIUM, 🏠 10 домов, 💎 /ec"},
    {"name": "💎 LEGEND", "price": 1000, "description": "💎 все привилегии DELUXE, 🌟 эффект легенды, 📛 золотая табличка"},
    {"name": "⚡ ULTRA", "price": 2000, "description": "⚡ все привилегии LEGEND, 🔥 /nick, 🚀 /speed"},
    {"name": "🔱 TITAN", "price": 3500, "description": "🔱 все привилегии ULTRA, 👑 доступ к командам Титана, 💫 уникальный эффект"},
    {"name": "👾 GOD", "price": 5000, "description": "👾 все привилегии TITAN, 🎨 создание своего цвета в чате, 🛡️ защита от киков"}
]

PRESET_DONATE_AMOUNTS = [100, 250, 500, 1000]

# ========== СОСТОЯНИЯ ==========
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
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Правила")],
            [KeyboardButton(text="🛒 Магазин")],
            [KeyboardButton(text="⚠️ Подать жалобу"), KeyboardButton(text="❓ Задать вопрос")],
            [KeyboardButton(text="ℹ️ Информация о сервере")]
        ],
        resize_keyboard=True
    )

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
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ответить", callback_data=f"reply_{ticket_id}_{user_id}")
    builder.button(text="❌ Закрыть", callback_data=f"close_{ticket_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_user_identifier(user) -> str:
    if user.username:
        # Очищаем username от лишних символов
        clean_username = user.username.split('|')[0].strip()
        return f"@{clean_username}"
    else:
        return f"ID: {user.id}"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# ========== ОСНОВНЫЕ ОБРАБОТЧИКИ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "🎮 Добро пожаловать на сервер Vanilka!\n\n"
        "Используй кнопки ниже для навигации 👇"
    )
    await message.answer(welcome_text, reply_markup=get_main_keyboard())

@dp.message(F.text == "❌ Отмена")
async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=get_main_keyboard())

@dp.message(F.text == "📋 Правила")
async def show_rules(message: types.Message):
    rules_text = (
        "📜 Правила сервера Vanilka\n\n"
        "1️⃣ Уважайте других игроков — никаких оскорблений и буллинга.\n"
        "2️⃣ Запрещены читы — любые модификации, дающие преимущество.\n"
        "3️⃣ Не гриферить — разрушать чужие постройки без разрешения.\n"
        "4️⃣ Не спамить — в чат, ЛС, голосовые каналы.\n"
        "5️⃣ Не рекламировать — другие серверы и сторонние ресурсы.\n\n"
        "⚠️ За нарушение — бан."
    )
    await message.answer(rules_text)

@dp.message(F.text == "ℹ️ Информация о сервере")
async def show_server_info(message: types.Message):
    info_text = (
        "🖥️ Информация о сервере Vanilka\n\n"
        f"🌐 IP-адрес: {SERVER_IP}\n"
        f"📦 Версия: {SERVER_VERSION}\n"
        "🎮 Тип: Ванильный Minecraft\n\n"
        "Скопируй IP и вставь в Minecraft для подключения!"
    )
    await message.answer(info_text)

@dp.message(F.text == "🛒 Магазин")
async def show_shop(message: types.Message):
    shop_text = "🛒 Магазин сервера Vanilka\n\nВыбери категорию ниже 👇"
    await message.answer(shop_text, reply_markup=get_shop_keyboard())

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
        "Когда закончите, нажмите кнопку «✅ Завершить и отправить жалобу»",
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
        ticket_id = f"comp_{int(time.time())}_{message.from_user.id}"

        # Текст для канала
        complaint_text = (
            f"⚠️ НОВАЯ ЖАЛОБА ⚠️\n\n"
            f"🆔 ID: {ticket_id}\n"
            f"👤 Заявитель: {data['complainant_nick']}\n"
            f"🤬 Нарушитель: {data['offender_nick']}\n"
            f"📝 Описание: {data['description']}\n"
            f"📎 Количество доказательств: {len(proofs)}"
        )
        await bot.send_message(CHANNEL_ID, complaint_text)

        for proof in proofs:
            if proof['type'] == 'photo':
                await bot.send_photo(CHANNEL_ID, proof['file_id'], caption=f"📸 Доказательство от {data['complainant_nick']}")
            elif proof['type'] == 'video':
                await bot.send_video(CHANNEL_ID, proof['file_id'], caption=f"🎥 Доказательство от {data['complainant_nick']}")
            elif proof['type'] == 'document':
                await bot.send_document(CHANNEL_ID, proof['file_id'], caption=f"📎 Доказательство от {data['complainant_nick']}")

        # Отправляем админу в ЛС с кнопками для ответа
        user_info = get_user_identifier(message.from_user)
        admin_text = (
            f"📨 НОВАЯ ЖАЛОБА\n\n"
            f"🆔 ID: {ticket_id}\n"
            f"👤 Заявитель: {data['complainant_nick']}\n"
            f"🤬 Нарушитель: {data['offender_nick']}\n"
            f"📝 Описание: {data['description']}\n"
            f"👤 Отправитель: {user_info}"
        )
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_keyboard(ticket_id, message.from_user.id))

        await message.answer("✅ Жалоба отправлена! Администрация рассмотрит её в ближайшее время.", reply_markup=get_main_keyboard())
        await state.clear()
        return

    # Добавляем доказательства
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
    ticket_id = f"q_{int(time.time())}_{message.from_user.id}"

    # Текст для канала
    question_text = (
        f"❓ НОВЫЙ ВОПРОС ❓\n\n"
        f"🆔 ID: {ticket_id}\n"
        f"👤 Игрок: {data['nick']}\n"
        f"💬 Вопрос: {message.text}"
    )
    await bot.send_message(CHANNEL_ID, question_text)

    # Отправляем админу в ЛС с кнопками для ответа
    user_info = get_user_identifier(message.from_user)
    admin_text = (
        f"📨 НОВЫЙ ВОПРОС\n\n"
        f"🆔 ID: {ticket_id}\n"
        f"👤 Игрок: {data['nick']}\n"
        f"💬 Вопрос: {message.text}\n"
        f"👤 Отправитель: {user_info}"
    )
    await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_keyboard(ticket_id, message.from_user.id))

    await message.answer("✅ Вопрос отправлен! Администрация ответит в ближайшее время.", reply_markup=get_main_keyboard())
    await state.clear()

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(lambda c: c.data.startswith("reply_"))
async def start_reply(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        ticket_id = parts[1]
        user_id = int(parts[2])
        await state.update_data(reply_user_id=user_id, reply_ticket_id=ticket_id)
        await state.set_state(ReplyStates.waiting_for_reply)
        await callback.message.answer(f"✏️ Введите ваш ответ для обращения `{ticket_id}`:")
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в start_reply: {e}")
        await callback.message.answer("❌ Ошибка при обработке запроса.")
        await callback.answer()

@dp.message(ReplyStates.waiting_for_reply)
async def send_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_user_id')
    ticket_id = data.get('reply_ticket_id')

    if not user_id:
        await message.answer("❌ Ошибка: не найден пользователь для ответа.")
        await state.clear()
        return

    try:
        # Проверяем, может ли бот отправить сообщение пользователю
        try:
            await bot.send_chat_action(user_id, action="typing")
        except Exception:
            await message.answer(f"❌ Не удалось отправить ответ: пользователь (ID: {user_id}) не начал диалог с ботом или заблокировал бота.")
            await state.clear()
            return

        # Отправляем ответ игроку
        await bot.send_message(
            user_id,
            f"📨 **Ответ администратора**\n\n"
            f"По вашему обращению `{ticket_id}`:\n\n"
            f"{message.text}\n\n"
            f"💡 Если у вас остались вопросы — напишите снова."
        )
        await message.answer(f"✅ Ответ отправлен игроку (ID: {user_id})")

        # Дублируем в канал
        await bot.send_message(
            CHANNEL_ID,
            f"📨 **Ответ администратора**\n"
            f"🆔 Обращение: {ticket_id}\n"
            f"💬 Ответ: {message.text}"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("close_"))
async def close_ticket(callback: types.CallbackQuery):
    try:
        ticket_id = callback.data.split("_")[1]
        
        # Отправляем сообщение в канал о закрытии обращения
        await bot.send_message(
            CHANNEL_ID,
            f"✅ **Обращение закрыто**\n"
            f"🆔 ID: {ticket_id}\n"
            f"📅 {time.strftime('%d.%m.%Y %H:%M')}\n"
            f"👤 Закрыл: @{callback.from_user.username or callback.from_user.first_name}"
        )
        
        await callback.message.edit_text(f"{callback.message.text}\n\n✅ Обращение `{ticket_id}` закрыто.")
        await callback.answer("Обращение закрыто")
    except Exception as e:
        logger.error(f"Ошибка в close_ticket: {e}")
        await callback.answer("Ошибка при закрытии")

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
    await callback.message.edit_text(
        "💝 Поддержка сервера\n\n"
        "Спасибо, что хотите помочь проекту!\n\n"
        "Введите свой игровой ник (или нажмите ❌ Отмена):"
    )
    await callback.answer()

@dp.message(SupportStates.waiting_for_nick)
async def support_get_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    await state.update_data(support_nick=message.text)
    await state.set_state(SupportStates.waiting_for_amount)
    await message.answer(
        "💝 Введите сумму пожертвования в рублях (от 10 до 100000):\n\n"
        "Пожертвования не дают игровых преимуществ, но помогают серверу развиваться!\n\n"
        "Или нажмите ❌ Отмена",
        reply_markup=get_cancel_keyboard()
    )

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
    vanilla_text = "🍦 Пополнение Ванилек\n\nВыберите сумму или укажите свою:\n\n(нажмите ❌ Отмена в любой момент)"
    await callback.message.edit_text(vanilla_text, reply_markup=get_vanilla_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def process_vanilla_donate(callback: types.CallbackQuery, state: FSMContext):
    action = callback.data.split("_")[1]

    if action == "custom":
        await state.set_state(VanillaDonateStates.waiting_for_amount)
        await callback.message.edit_text(
            "🍦 Введите сумму пополнения в рублях (целое число от 10 до 100000):\n\n"
            "1 рубль = 1 Ванилька\n\n"
            "Или нажмите ❌ Отмена в чате"
        )
        await callback.answer()
        return

    amount = int(action)
    await state.update_data(vanilla_amount=amount)
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await callback.message.edit_text(f"🍦 Вы выбрали сумму {amount} руб.\n\nТеперь введите свой игровой ник (или нажмите ❌ Отмена):")
    await callback.answer()

@dp.message(VanillaDonateStates.waiting_for_amount)
async def process_custom_vanilla_amount(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return

    if not re.match(r'^\d+$', message.text):
        await message.answer("❌ Пожалуйста, введите целое число (например: 500)\n\nИли нажмите ❌ Отмена")
        return

    amount = int(message.text)
    if amount < 10:
        await message.answer("❌ Минимальная сумма пополнения — 10 рублей\n\nИли нажмите ❌ Отмена")
        return
    if amount > 100000:
        await message.answer("❌ Максимальная сумма пополнения — 100 000 рублей\n\nИли нажмите ❌ Отмена")
        return

    await state.update_data(vanilla_amount=amount)
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await message.answer(f"🍦 Сумма: {amount} руб.\n\nТеперь введите свой игровой ник (или нажмите ❌ Отмена):", reply_markup=get_cancel_keyboard())

@dp.message(VanillaDonateStates.waiting_for_nick)
async def process_vanilla_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return

    data = await state.get_data()
    amount = data.get('vanilla_amount')
    nick = message.text

    donate_text = (
        f"🍦 Пополнение Ванилек\n\n"
        f"💰 Сумма: {amount} руб.\n"
        f"🍦 Вы получите: {amount} Ванилек\n"
        f"👤 Ваш ник: {nick}\n\n"
        f"🏦 Сбербанк: {SBER_CARD}\n\n"
        f"❗ После перевода напишите администратору @vanilka_support с:\n"
        f"• Скриншотом перевода\n"
        f"• Своим игровым ником: {nick}\n"
        f"• Суммой перевода: {amount} руб.\n\n"
        f"Ванильки будут начислены в течение 15 минут после проверки!"
    )

    await message.answer(donate_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад в магазин", callback_data="back_to_shop")]
    ]))

    await bot.send_message(
        CHANNEL_ID,
        f"🍦 ЗАЯВКА НА ПОПОЛНЕНИЕ ВАНИЛЕК 🍦\n\n"
        f"👤 Игровой ник: {nick}\n"
        f"💰 Сумма: {amount} руб.\n"
        f"🍦 Ванилек: {amount}"
    )

    await state.clear()

@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(callback: types.CallbackQuery):
    priv_text = "🎁 Выберите привилегию:\n\n"
    for p in PRIVILEGES:
        priv_text += f"{p['name']} — {p['price']}₽\n   └ {p['description']}\n\n"
    await callback.message.edit_text(priv_text, reply_markup=get_privileges_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("priv_"))
async def process_privilege(callback: types.CallbackQuery, state: FSMContext):
    privilege_name = callback.data.split("priv_")[1]

    privilege = None
    for p in PRIVILEGES:
        if p['name'] == privilege_name:
            privilege = p
            break

    if not privilege:
        await callback.answer("Ошибка: привилегия не найдена")
        return

    await state.update_data(privilege_name=privilege['name'], privilege_price=privilege['price'])
    await state.set_state(PrivilegeStates.waiting_for_nick)
    await callback.message.edit_text(
        f"🎁 Покупка привилегии {privilege['name']}\n\n"
        f"💰 Цена: {privilege['price']}₽\n"
        f"📝 Описание: {privilege['description']}\n\n"
        f"Введите свой игровой ник (или нажмите ❌ Отмена):"
    )
    await callback.answer()

@dp.message(PrivilegeStates.waiting_for_nick)
async def process_privilege_nick(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return

    data = await state.get_data()
    privilege_name = data.get('privilege_name')
    privilege_price = data.get('privilege_price')
    nick = message.text

    purchase_text = (
        f"🎁 Покупка привилегии {privilege_name}\n\n"
        f"💰 Стоимость: {privilege_price}₽\n"
        f"👤 Ваш ник: {nick}\n\n"
        f"🏦 Сбербанк: {SBER_CARD}\n\n"
        f"❗ После перевода напишите администратору @vanilka_support с:\n"
        f"• Скриншотом перевода\n"
        f"• Своим игровым ником: {nick}\n"
        f"• Названием привилегии: {privilege_name}\n"
        f"• Суммой перевода: {privilege_price}₽\n\n"
        f"Привилегия будет выдана в течение 15 минут после проверки!"
    )

    await message.answer(purchase_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад к привилегиям", callback_data="shop_privilege")]
    ]))

    await bot.send_message(
        CHANNEL_ID,
        f"🎁 ЗАЯВКА НА ПРИВИЛЕГИЮ 🎁\n\n"
        f"👤 Игровой ник: {nick}\n"
        f"🎁 Привилегия: {privilege_name}\n"
        f"💰 Сумма: {privilege_price}₽"
    )

    await state.clear()

# ========== ЗАПУСК ==========
async def main():
    logger.info("🚀 Бот запускается...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logger.info(f"✅ Бот успешно запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
