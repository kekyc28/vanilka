import asyncio
import logging
import os
import time
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ========== Переменные ==========
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
RULES = "📜 Правила сервера:\n\n1️⃣ Уважайте других игроков\n2️⃣ Запрещены читы\n3️⃣ Не гриферите\n4️⃣ Не спамите\n5️⃣ Не рекламируйте\n\n⚠️ За нарушение — бан!"

# ========== Состояния ==========
class ComplaintStates(StatesGroup):
    nick = State()
    offender = State()
    desc = State()
    media = State()

class QuestionStates(StatesGroup):
    nick = State()
    text = State()

class AccessStates(StatesGroup):
    nick = State()
    about = State()
    reason = State()

class VanillaStates(StatesGroup):
    amount = State()
    nick = State()

class PrivilegeStates(StatesGroup):
    nick = State()

class SupportStates(StatesGroup):
    amount = State()
    nick = State()

class ReplyStates(StatesGroup):
    text = State()

# ========== Привилегии ==========
PRIVILEGES = [
    {"name": "VIP", "price": 150, "desc": "/kit vip, цвет в чате, 3 дома", "emoji": "🍃"},
    {"name": "Premium", "price": 300, "desc": "Все привилегии VIP, /fly, 5 домов", "emoji": "⭐"},
    {"name": "Deluxe", "price": 500, "desc": "Все привилегии Premium, /ec, 10 домов", "emoji": "👑"},
    {"name": "Legend", "price": 1000, "desc": "Все привилегии Deluxe, эффект легенды", "emoji": "💎"},
    {"name": "Ultra", "price": 2000, "desc": "Все привилегии Legend, /nick, /speed", "emoji": "⚡"},
    {"name": "Titan", "price": 3500, "desc": "Все привилегии Ultra, команды Титана", "emoji": "🔱"},
    {"name": "God", "price": 5000, "desc": "Все привилегии Titan, свой цвет в чате", "emoji": "👾"}
]

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

finish_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Отправить")],
        [KeyboardButton(text="❌ Отмена")]
    ],
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
    for p in PRIVILEGES:
        builder.button(text=f"{p['emoji']} {p['name']} - {p['price']}₽", callback_data=f"priv_{p['name']}")
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

def get_access_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎟️ Бесплатная", callback_data="access_free")
    builder.button(text="💎 Платная (300₽)", callback_data="access_paid")
    builder.button(text="⬅️ Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_reply_kb(ticket_id, user_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ответить", callback_data=f"reply_{ticket_id}_{user_id}")
    builder.button(text="❌ Закрыть", callback_data=f"close_{ticket_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_access_decision_kb(user_id, access_type):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять", callback_data=f"acc_accept_{user_id}_{access_type}")
    builder.button(text="❌ Отказать", callback_data=f"acc_deny_{user_id}_{access_type}")
    builder.adjust(2)
    return builder.as_markup()

def get_payment_kb(operation_id, operation_type, details):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data=f"pay_{operation_type}_{operation_id}_{details}")
    builder.button(text="❌ Отменить", callback_data=f"pay_cancel_{operation_type}_{operation_id}")
    builder.adjust(1)
    return builder.as_markup()

def get_user(user):
    if user.username:
        clean = user.username.split('|')[0].strip()
        return f"@{clean}"
    return f"ID: {user.id}"

def split_long_message(text, max_length=4000):
    if len(text) <= max_length:
        return [text]
    parts = []
    while len(text) > max_length:
        split_point = text.rfind('\n', 0, max_length)
        if split_point == -1:
            split_point = text.rfind(' ', 0, max_length)
        if split_point == -1:
            split_point = max_length
        parts.append(text[:split_point])
        text = text[split_point:].lstrip()
    if text:
        parts.append(text)
    return parts

# ========== Инициализация ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("🎮 Добро пожаловать на сервер Vanilka!", reply_markup=main_kb)

@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer("❌ Действие отменено.", reply_markup=main_kb)

@dp.message(F.text == "📋 Правила")
async def rules(msg: types.Message):
    await msg.answer(RULES)

@dp.message(F.text == "ℹ️ Информация")
async def info(msg: types.Message):
    await msg.answer(f"🖥️ Сервер Vanilka\n\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}\n🎮 Тип: Ванильный Minecraft")

@dp.message(F.text == "🛒 Магазин")
async def shop(msg: types.Message):
    await msg.answer("🛒 Магазин\n\nВыбери категорию 👇", reply_markup=get_shop_kb())

# ========== ЖАЛОБА ==========
@dp.message(F.text == "⚠️ Жалоба")
async def complaint_start(msg: types.Message, state: FSMContext):
    await state.set_state(ComplaintStates.nick)
    await msg.answer("📝 Подача жалобы\n\nШаг 1/4: Введите свой игровой ник.", reply_markup=cancel_kb)

# ========== ВОПРОС ==========
@dp.message(F.text == "❓ Вопрос")
async def question_start(msg: types.Message, state: FSMContext):
    await state.set_state(QuestionStates.nick)
    await msg.answer("❓ Задать вопрос\n\nШаг 1/2: Введите свой игровой ник.", reply_markup=cancel_kb)

# ========== ПРОХОДКА ==========
@dp.message(F.text == "🚪 Проходка")
async def access_start(msg: types.Message):
    await msg.answer("🚪 Проходка на сервер\n\nВыберите тип проходки:", reply_markup=get_access_kb())

@dp.callback_query(F.data == "access_free")
async def access_free(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(access_type="free")
    await state.set_state(AccessStates.nick)
    await call.message.edit_text("🎟️ Бесплатная проходка\n\nВведите свой игровой ник:")
    await call.answer()

@dp.callback_query(F.data == "access_paid")
async def access_paid(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(access_type="paid")
    await state.set_state(AccessStates.nick)
    await call.message.edit_text("💎 Платная проходка (300₽)\n\nВведите свой игровой ник:")
    await call.answer()

# ========== ВАНИЛЬКИ ==========
@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(call: types.CallbackQuery):
    await call.message.edit_text("🍦 Ванильки\n1₽ = 1 Ванилька\n\nВыбери сумму:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_buy(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    if action == "custom":
        await state.set_state(VanillaStates.amount)
        await call.message.edit_text("🍦 Введите сумму (10-100000₽):")
        await call.answer()
        return
    amount = int(action)
    await state.update_data(amount=amount)
    await state.set_state(VanillaStates.nick)
    await call.message.delete()
    await call.message.answer(f"🍦 Сумма: {amount}₽\n\nВведите свой игровой ник:", reply_markup=cancel_kb)

# ========== ПРИВИЛЕГИИ ==========
@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(call: types.CallbackQuery):
    text = "🎁 Привилегии:\n\n"
    for p in PRIVILEGES:
        text += f"{p['emoji']} {p['name']} — {p['price']}₽\n   {p['desc']}\n\n"
    await call.message.edit_text(text, reply_markup=get_privilege_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("priv_"))
async def privilege_buy(call: types.CallbackQuery, state: FSMContext):
    name = call.data.split("_")[1]
    priv = next((p for p in PRIVILEGES if p['name'] == name), None)
    if not priv:
        await call.answer("Ошибка")
        return
    await state.update_data(priv_name=priv['name'], priv_price=priv['price'])
    await state.set_state(PrivilegeStates.nick)
    await call.message.delete()
    await call.message.answer(f"{priv['emoji']} {priv['name']}\n💰 Цена: {priv['price']}₽\n\n{priv['desc']}\n\nВведите свой игровой ник:", reply_markup=cancel_kb)

# ========== ПОДДЕРЖКА ==========
@dp.callback_query(F.data == "shop_support")
async def shop_support(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.amount)
    await call.message.delete()
    await call.message.answer("💝 Поддержка сервера\n\nВведите сумму (10-100000₽):", reply_markup=cancel_kb)

# ========== УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ==========
@dp.message(F.text)
async def handle_all_text_messages(msg: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    # Если нет активного состояния - показываем меню
    if current_state is None:
        if msg.text in ["📋 Правила", "🛒 Магазин", "🚪 Проходка", "⚠️ Жалоба", "❓ Вопрос", "ℹ️ Информация", "❌ Отмена", "✅ Отправить"]:
            return
        await msg.answer("🤔 Используйте кнопки меню 👇", reply_markup=main_kb)
        return
    
    # ========== ЖАЛОБА ==========
    if current_state == ComplaintStates.nick:
        await state.update_data(nick=msg.text)
        await state.set_state(ComplaintStates.offender)
        await msg.answer(f"✅ Ник принят: {msg.text}\n\n🤬 Шаг 2/4: Введите ник нарушителя.", reply_markup=cancel_kb)
    
    elif current_state == ComplaintStates.offender:
        await state.update_data(offender=msg.text)
        await state.set_state(ComplaintStates.desc)
        await msg.answer(f"✅ Нарушитель: {msg.text}\n\n📝 Шаг 3/4: Опишите, что произошло.", reply_markup=cancel_kb)
    
    elif current_state == ComplaintStates.desc:
        await state.update_data(desc=msg.text)
        await state.set_state(ComplaintStates.media)
        await state.update_data(media=[])
        await msg.answer(
            f"✅ Описание: {msg.text}\n\n📎 Шаг 4/4: Отправьте доказательства (фото, видео).\n\n"
            "Можно отправить несколько файлов.\n"
            "Когда закончите — нажмите «✅ Отправить».",
            reply_markup=finish_kb
        )
    
    elif current_state == ComplaintStates.media:
        if msg.text == "✅ Отправить":
            data = await state.get_data()
            media = data.get('media', [])
            ticket = f"comp_{int(time.time())}"
            text = f"⚠️ Новая жалоба\n\n👤 Заявитель: {data['nick']}\n🤬 Нарушитель: {data['offender']}\n📝 Описание: {data['desc']}\n📎 Файлов: {len(media)}"
            await bot.send_message(CHANNEL_ID, text)
            for m in media:
                if m['type'] == 'photo':
                    await bot.send_photo(CHANNEL_ID, m['id'], caption=f"📸 от {data['nick']}")
                elif m['type'] == 'video':
                    await bot.send_video(CHANNEL_ID, m['id'], caption=f"🎥 от {data['nick']}")
            await bot.send_message(ADMIN_ID, f"📨 Новая жалоба\n\n👤 {data['nick']}\n🤬 {data['offender']}\n📝 {data['desc']}\n👤 {get_user(msg.from_user)}", reply_markup=get_reply_kb(ticket, msg.from_user.id))
            await msg.answer("✅ Жалоба отправлена!", reply_markup=main_kb)
            await state.clear()
        else:
            await msg.answer("❌ Нажмите «✅ Отправить» для завершения жалобы.")
    
    # ========== ВОПРОС ==========
    elif current_state == QuestionStates.nick:
        await state.update_data(nick=msg.text)
        await state.set_state(QuestionStates.text)
        await msg.answer(f"✅ Ник принят: {msg.text}\n\n💬 Шаг 2/2: Напишите ваш вопрос.", reply_markup=cancel_kb)
    
    elif current_state == QuestionStates.text:
        data = await state.get_data()
        ticket = f"q_{int(time.time())}"
        await bot.send_message(CHANNEL_ID, f"❓ Новый вопрос\n\n👤 Игрок: {data['nick']}\n💬 Вопрос: {msg.text}")
        await bot.send_message(ADMIN_ID, f"📨 Новый вопрос\n\n👤 Игрок: {data['nick']}\n💬 Вопрос: {msg.text}\n👤 Отправитель: {get_user(msg.from_user)}", reply_markup=get_reply_kb(ticket, msg.from_user.id))
        await msg.answer("✅ Вопрос отправлен!", reply_markup=main_kb)
        await state.clear()
    
    # ========== ПРОХОДКА ==========
    elif current_state == AccessStates.nick:
        await state.update_data(nick=msg.text)
        await state.set_state(AccessStates.about)
        await msg.answer("📝 Расскажите немного о себе (чем занимаетесь, опыт игры в Minecraft и т.д.):", reply_markup=cancel_kb)
    
    elif current_state == AccessStates.about:
        await state.update_data(about=msg.text)
        await state.set_state(AccessStates.reason)
        await msg.answer("💭 Почему вы хотите играть именно на нашем сервере?", reply_markup=cancel_kb)
    
    elif current_state == AccessStates.reason:
        data = await state.get_data()
        access_type = data.get('access_type')
        nick = data.get('nick')
        about = data.get('about')
        reason = msg.text
        
        channel_text = (
            f"🚪 Новая заявка на проходку\n\n"
            f"👤 Ник: {nick}\n"
            f"📝 О себе: {about}\n"
            f"💭 Причина: {reason}\n"
            f"{'💎 Платная (300₽)' if access_type == 'paid' else '🎟️ Бесплатная'}"
        )
        await bot.send_message(CHANNEL_ID, channel_text)
        
        if access_type == "paid":
            op_id = f"{msg.from_user.id}_{int(time.time())}"
            details = f"Платная проходка|300|{nick}"
            # ОТДЕЛЬНЫЕ СООБЩЕНИЯ: сначала реквизиты
            await msg.answer(
                f"💎 Платная проходка (300₽)\n\n🏦 Карта: {SBER_CARD}\n\n📌 Для подтверждения оплаты нажмите кнопку ниже:",
                reply_markup=main_kb
            )
            # потом кнопки (с задержкой 1 секунда)
            await asyncio.sleep(1)
            await msg.answer(
                f"✅ Для подтверждения оплаты нажмите кнопку ниже:",
                reply_markup=get_payment_kb(op_id, "paid_access", details)
            )
            await bot.send_message(ADMIN_ID, f"📨 Заявка на проходку\n👤 Ник: {nick}\n💭 Причина: {reason}\n💎 Платная (ожидает оплаты)\n👤 Отправитель: {get_user(msg.from_user)}")
        else:
            await msg.answer("✅ Заявка отправлена! Администрация рассмотрит её в ближайшее время.", reply_markup=main_kb)
            await bot.send_message(ADMIN_ID, f"📨 Заявка на проходку\n👤 Ник: {nick}\n💭 Причина: {reason}\n🎟️ Бесплатная\n👤 Отправитель: {get_user(msg.from_user)}", reply_markup=get_access_decision_kb(msg.from_user.id, "free"))
        await state.clear()
    
    # ========== ВАНИЛЬКИ ==========
    elif current_state == VanillaStates.amount:
        if not msg.text.isdigit():
            await msg.answer("❌ Введите число!")
            return
        amount = int(msg.text)
        if amount < 10 or amount > 100000:
            await msg.answer("❌ Сумма от 10 до 100000")
            return
        await state.update_data(amount=amount)
        await state.set_state(VanillaStates.nick)
        await msg.answer(f"🍦 Сумма: {amount}₽\n\nВведите игровой ник:", reply_markup=cancel_kb)
    
    elif current_state == VanillaStates.nick:
        data = await state.get_data()
        amount = data.get('amount')
        if amount is None:
            amount = "неизвестно"
        nick = msg.text
        
        op_id = f"{msg.from_user.id}_{int(time.time())}"
        details = f"Ванильки|{amount}|{nick}"
        
        # ПРИНУДИТЕЛЬНАЯ ОТПРАВКА двух сообщений
        try:
            # Первое сообщение - реквизиты
            await msg.answer(
                f"🍦 Пополнение Ванилек\n\n💰 Сумма: {amount}₽\n👤 Ник: {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку подтверждения.",
                reply_markup=main_kb
            )
            # Небольшая задержка
            await asyncio.sleep(1)
            # Второе сообщение - кнопки
            await msg.answer(
                f"✅ Для подтверждения оплаты нажмите кнопку ниже:",
                reply_markup=get_payment_kb(op_id, "vanilla", details)
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке: {e}")
            await msg.answer("❌ Произошла ошибка при отправке кнопок. Попробуйте ещё раз.")
        
        await state.clear()
    
    # ========== ПРИВИЛЕГИИ ==========
    elif current_state == PrivilegeStates.nick:
        data = await state.get_data()
        name = data.get('priv_name')
        price = data.get('priv_price')
        if name is None:
            name = "неизвестно"
        if price is None:
            price = "неизвестно"
        nick = msg.text
        
        op_id = f"{msg.from_user.id}_{int(time.time())}"
        details = f"{name}|{price}|{nick}"
        
        # ПРИНУДИТЕЛЬНАЯ ОТПРАВКА двух сообщений
        try:
            await msg.answer(
                f"🎁 Покупка привилегии {name}\n\n💰 Цена: {price}₽\n👤 Ник: {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку подтверждения.",
                reply_markup=main_kb
            )
            await asyncio.sleep(1)
            await msg.answer(
                f"✅ Для подтверждения оплаты нажмите кнопку ниже:",
                reply_markup=get_payment_kb(op_id, "priv", details)
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке: {e}")
            await msg.answer("❌ Произошла ошибка при отправке кнопок. Попробуйте ещё раз.")
        
        await state.clear()
    
    # ========== ПОДДЕРЖКА ==========
    elif current_state == SupportStates.amount:
        if not msg.text.isdigit():
            await msg.answer("❌ Введите число!")
            return
        amount = int(msg.text)
        if amount < 10 or amount > 100000:
            await msg.answer("❌ Сумма от 10 до 100000")
            return
        await state.update_data(amount=amount)
        await state.set_state(SupportStates.nick)
        await msg.answer(f"💝 Сумма: {amount}₽\n\nВведите игровой ник:", reply_markup=cancel_kb)
    
    elif current_state == SupportStates.nick:
        data = await state.get_data()
        amount = data.get('amount')
        if amount is None:
            amount = "неизвестно"
        nick = msg.text
        
        op_id = f"{msg.from_user.id}_{int(time.time())}"
        details = f"Пожертвование|{amount}|{nick}"
        
        # ПРИНУДИТЕЛЬНАЯ ОТПРАВКА двух сообщений
        try:
            await msg.answer(
                f"💝 Пожертвование\n\n💰 Сумма: {amount}₽\n👤 Ник: {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку подтверждения.",
                reply_markup=main_kb
            )
            await asyncio.sleep(1)
            await msg.answer(
                f"✅ Для подтверждения оплаты нажмите кнопку ниже:",
                reply_markup=get_payment_kb(op_id, "support", details)
            )
        except Exception as e:
            logging.error(f"Ошибка при отправке: {e}")
            await msg.answer("❌ Произошла ошибка при отправке кнопок. Попробуйте ещё раз.")
        
        await state.clear()
    
    # ========== ОТВЕТЫ АДМИНА ==========
    elif current_state == ReplyStates.text:
        data = await state.get_data()
        user_id = data.get('reply_user')
        ticket = data.get('reply_ticket')
        if not user_id:
            await msg.answer("❌ Ошибка: не найден пользователь для ответа.")
            await state.clear()
            return
        
        try:
            await bot.send_chat_action(user_id, action="typing")
        except Exception:
            await msg.answer(f"❌ Не удалось отправить ответ. Пользователь не начал диалог с ботом.\n\nID: {user_id}")
            await state.clear()
            return
        
        try:
            reply_text = f"📨 Ответ администратора\n\n{msg.text}\n\n💡 Если остались вопросы — напишите снова."
            for part in split_long_message(reply_text):
                await bot.send_message(user_id, part)
            await msg.answer(f"✅ Ответ отправлен игроку!")
            channel_text = f"📨 Ответ администратора\n\n🆔 ID обращения: {ticket}\n💬 Ответ: {msg.text}"
            for part in split_long_message(channel_text):
                await bot.send_message(CHANNEL_ID, part)
        except Exception as e:
            await msg.answer(f"❌ Ошибка при отправке: {e}")
        await state.clear()

# ========== ОБРАБОТКА ФОТО/ВИДЕО ДЛЯ ЖАЛОБ ==========
@dp.message(ComplaintStates.media, F.photo | F.video)
async def complaint_media_file(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    media = data.get('media', [])
    if msg.photo:
        media.append({'type': 'photo', 'id': msg.photo[-1].file_id})
        await msg.answer(f"📸 Фото добавлено. Всего: {len(media)}.")
    elif msg.video:
        media.append({'type': 'video', 'id': msg.video.file_id})
        await msg.answer(f"🎥 Видео добавлено. Всего: {len(media)}.")
    await state.update_data(media=media)

# ========== ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ==========
@dp.callback_query(F.data.startswith("pay_"))
async def payment_confirm(call: types.CallbackQuery):
    try:
        parts = call.data.split("_")
        if parts[1] == "cancel":
            await call.message.delete()
            await call.message.answer("❌ Операция отменена.", reply_markup=main_kb)
            await call.answer()
            return
        typ = parts[1]
        op_id = parts[2]
        details = "_".join(parts[3:])
        if "|" in details:
            pd = details.split("|")
            product_name = pd[0]
            amount = pd[1] if len(pd) > 1 else "?"
            nick = pd[2] if len(pd) > 2 else "?"
        else:
            product_name, amount, nick = "Операция", "?", "?"
        confirm_text = f"✅ Подтверждение оплаты\n\n📦 {product_name}\n💰 {amount}₽\n👤 {get_user(call.from_user)}\n👤 Ник: {nick}"
        await bot.send_message(CHANNEL_ID, confirm_text)
        await bot.send_message(ADMIN_ID, confirm_text)
        await call.message.delete()
        await call.message.answer(f"✅ Спасибо за оплату!\n\nПлатёж за {product_name} зарегистрирован.", reply_markup=main_kb)
        await call.answer()
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await call.answer("❌ Ошибка")

# ========== РЕШЕНИЯ ПО ПРОХОДКЕ ==========
@dp.callback_query(F.data.startswith("acc_accept_"))
async def access_accept(call: types.CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[2])
    access_type = parts[3] if len(parts) > 3 else "free"
    type_text = "платная" if access_type == "paid" else "бесплатная"
    
    await bot.send_message(user_id, f"✅ Ваша {type_text} заявка на проходку одобрена!\n\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}\n\n{RULES}\n\n🎮 Приятной игры!")
    await call.message.edit_text(f"{call.message.text}\n\n✅ {type_text.capitalize()} заявка одобрена администратором {get_user(call.from_user)}")
    await bot.send_message(CHANNEL_ID, f"✅ {type_text.capitalize()} заявка на проходку одобрена\n👤 Игрок: ID {user_id}\n👤 Администратор: {get_user(call.from_user)}")
    await call.answer("Заявка одобрена")

@dp.callback_query(F.data.startswith("acc_deny_"))
async def access_deny(call: types.CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[2])
    access_type = parts[3] if len(parts) > 3 else "free"
    type_text = "платная" if access_type == "paid" else "бесплатная"
    
    await bot.send_message(user_id, f"❌ К сожалению, ваша {type_text} заявка на проходку отклонена.\n\nВы можете попробовать снова позже.")
    await call.message.edit_text(f"{call.message.text}\n\n❌ {type_text.capitalize()} заявка отклонена администратором {get_user(call.from_user)}")
    await bot.send_message(CHANNEL_ID, f"❌ {type_text.capitalize()} заявка на проходку отклонена\n👤 Игрок: ID {user_id}\n👤 Администратор: {get_user(call.from_user)}")
    await call.answer("Заявка отклонена")

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    ticket = parts[1]
    user_id = int(parts[2])
    await state.update_data(reply_user=user_id, reply_ticket=ticket)
    await state.set_state(ReplyStates.text)
    await call.message.answer("✏️ Введите ответ для игрока:")
    await call.answer()

@dp.callback_query(F.data.startswith("close_"))
async def reply_close(call: types.CallbackQuery):
    ticket = call.data.split("_")[1]
    await bot.send_message(CHANNEL_ID, f"✅ Обращение закрыто\n\n🆔 ID: {ticket}\n👤 Закрыл: {get_user(call.from_user)}")
    await call.message.edit_text(f"{call.message.text}\n\n✅ Обращение закрыто.")
    await call.answer("Обращение закрыто")

# ========== КОЛБЭКИ МЕНЮ ==========
@dp.callback_query(F.data == "main_menu")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("🏠 Главное меню:", reply_markup=main_kb)
    await call.answer()

@dp.callback_query(F.data == "back_shop")
async def back_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())
    await call.answer()

# ========== ЗАПУСК ==========
async def main():
    logging.info("🚀 Запуск бота...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"✅ Бот успешно запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
