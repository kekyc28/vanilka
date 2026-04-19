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

# ========== Состояния ==========
class Form(StatesGroup):
    complaint_nick = State()
    complaint_offender = State()
    complaint_desc = State()
    complaint_media = State()
    question_nick = State()
    question_text = State()
    access_type = State()
    access_nick = State()
    access_reason = State()
    vanilla_amount = State()
    vanilla_nick = State()
    privilege_nick = State()
    support_amount = State()
    support_nick = State()
    reply_text = State()

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

def get_access_decision_kb(user_id, typ):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять", callback_data=f"acc_accept_{user_id}_{typ}")
    builder.button(text="❌ Отказать", callback_data=f"acc_deny_{user_id}_{typ}")
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
    await msg.answer("📜 Правила сервера:\n\n1️⃣ Уважайте других.\n2️⃣ Запрещены читы.\n3️⃣ Не гриферите.\n4️⃣ Не спамите.\n5️⃣ Не рекламируйте.\n\n⚠️ За нарушение — бан.")

@dp.message(F.text == "ℹ️ Информация")
async def info(msg: types.Message):
    await msg.answer(f"🖥️ Сервер Vanilka\n\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}\n🎮 Тип: Ванильный Minecraft")

@dp.message(F.text == "🛒 Магазин")
async def shop(msg: types.Message):
    await msg.answer("🛒 Магазин\n\nВыбери категорию 👇", reply_markup=get_shop_kb())

# ========== ЖАЛОБА ==========
@dp.message(F.text == "⚠️ Жалоба")
async def complaint_start(msg: types.Message, state: FSMContext):
    await state.set_state(Form.complaint_nick)
    await msg.answer("📝 Подача жалобы\n\nШаг 1/4: Введите свой игровой ник.", reply_markup=cancel_kb)

@dp.message(Form.complaint_nick)
async def complaint_nick(msg: types.Message, state: FSMContext):
    await state.update_data(nick=msg.text)
    await state.set_state(Form.complaint_offender)
    await msg.answer(f"✅ Ник принят: {msg.text}\n\n🤬 Шаг 2/4: Введите ник нарушителя.", reply_markup=cancel_kb)

@dp.message(Form.complaint_offender)
async def complaint_offender(msg: types.Message, state: FSMContext):
    await state.update_data(offender=msg.text)
    await state.set_state(Form.complaint_desc)
    await msg.answer(f"✅ Нарушитель: {msg.text}\n\n📝 Шаг 3/4: Опишите, что произошло.", reply_markup=cancel_kb)

@dp.message(Form.complaint_desc)
async def complaint_desc(msg: types.Message, state: FSMContext):
    await state.update_data(desc=msg.text)
    await state.set_state(Form.complaint_media)
    await state.update_data(media=[])
    await msg.answer(
        f"✅ Описание: {msg.text}\n\n📎 Шаг 4/4: Отправьте доказательства (фото, видео).\n\n"
        "Можно отправить несколько файлов.\n"
        "Когда закончите — нажмите «✅ Отправить».",
        reply_markup=finish_kb
    )

@dp.message(Form.complaint_media)
async def complaint_media(msg: types.Message, state: FSMContext):
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
    elif msg.photo or msg.video:
        data = await state.get_data()
        media = data.get('media', [])
        if msg.photo:
            media.append({'type': 'photo', 'id': msg.photo[-1].file_id})
            await msg.answer(f"📸 Фото добавлено. Всего: {len(media)}.")
        elif msg.video:
            media.append({'type': 'video', 'id': msg.video.file_id})
            await msg.answer(f"🎥 Видео добавлено. Всего: {len(media)}.")
        await state.update_data(media=media)
    else:
        await msg.answer("❌ Отправьте фото/видео или нажмите «✅ Отправить».")

# ========== ВОПРОС ==========
@dp.message(F.text == "❓ Вопрос")
async def question_start(msg: types.Message, state: FSMContext):
    await state.set_state(Form.question_nick)
    await msg.answer("❓ Задать вопрос\n\nШаг 1/2: Введите свой игровой ник.", reply_markup=cancel_kb)

@dp.message(Form.question_nick)
async def question_nick(msg: types.Message, state: FSMContext):
    await state.update_data(nick=msg.text)
    await state.set_state(Form.question_text)
    await msg.answer(f"✅ Ник принят: {msg.text}\n\n💬 Шаг 2/2: Напишите ваш вопрос.", reply_markup=cancel_kb)

@dp.message(Form.question_text)
async def question_text(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    ticket = f"q_{int(time.time())}"
    await bot.send_message(CHANNEL_ID, f"❓ Новый вопрос\n\n👤 {data['nick']}\n💬 {msg.text}")
    await bot.send_message(ADMIN_ID, f"📨 Новый вопрос\n\n👤 {data['nick']}\n💬 {msg.text}\n👤 {get_user(msg.from_user)}", reply_markup=get_reply_kb(ticket, msg.from_user.id))
    await msg.answer("✅ Вопрос отправлен!", reply_markup=main_kb)
    await state.clear()

# ========== ПРОХОДКА ==========
@dp.message(F.text == "🚪 Проходка")
async def access_start(msg: types.Message):
    await msg.answer("🚪 Проходка\n\nВыберите тип:", reply_markup=get_access_kb())

@dp.callback_query(F.data == "access_free")
async def access_free(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(typ="free")
    await state.set_state(Form.access_nick)
    await call.message.edit_text("🎟️ Бесплатная проходка\n\nВведите свой игровой ник:")
    await call.answer()

@dp.callback_query(F.data == "access_paid")
async def access_paid(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(typ="paid")
    await state.set_state(Form.access_nick)
    await call.message.edit_text("💎 Платная проходка (300₽)\n\nВведите свой игровой ник:")
    await call.answer()

@dp.message(Form.access_nick)
async def access_nick(msg: types.Message, state: FSMContext):
    await state.update_data(nick=msg.text)
    await state.set_state(Form.access_reason)
    await msg.answer(f"✅ Ник принят: {msg.text}\n\n💭 Почему хотите играть у нас?", reply_markup=cancel_kb)

@dp.message(Form.access_reason)
async def access_reason(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    typ = data.get('typ')
    nick = data.get('nick')
    reason = msg.text
    await bot.send_message(CHANNEL_ID, f"🚪 Заявка на проходку\n👤 {nick}\n💭 {reason}\n{'💎 Платная' if typ == 'paid' else '🎟️ Бесплатная'}")
    if typ == "paid":
        op_id = f"{msg.from_user.id}_{int(time.time())}"
        details = f"Платная проходка|300|{nick}"
        await msg.answer(f"💎 Платная проходка (300₽)\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку.", reply_markup=get_payment_kb(op_id, "paid_access", details))
        await bot.send_message(ADMIN_ID, f"📨 Заявка на проходку\n👤 {nick}\n💭 {reason}\n💎 Платная\n👤 {get_user(msg.from_user)}")
    else:
        await msg.answer("✅ Заявка отправлена!", reply_markup=main_kb)
        await bot.send_message(ADMIN_ID, f"📨 Заявка на проходку\n👤 {nick}\n💭 {reason}\n🎟️ Бесплатная\n👤 {get_user(msg.from_user)}", reply_markup=get_access_decision_kb(msg.from_user.id, "free"))
    await state.clear()

# ========== МАГАЗИН - ВАНИЛЬКИ ==========
@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(call: types.CallbackQuery):
    await call.message.edit_text("🍦 Ванильки\n1₽ = 1 Ванилька\n\nВыбери сумму:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_buy(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    if action == "custom":
        await state.set_state(Form.vanilla_amount)
        await call.message.edit_text("🍦 Введите сумму (10-100000₽):")
        await call.answer()
        return
    amount = int(action)
    await state.update_data(amount=amount)
    await state.set_state(Form.vanilla_nick)
    await call.message.edit_text(f"🍦 Сумма: {amount}₽\n\nВведите свой игровой ник:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.message(Form.vanilla_amount)
async def vanilla_amount(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ Введите число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("❌ Сумма от 10 до 100000")
        return
    await state.update_data(amount=amount)
    await state.set_state(Form.vanilla_nick)
    await msg.answer(f"🍦 Сумма: {amount}₽\n\nВведите игровой ник:", reply_markup=cancel_kb)

@dp.message(Form.vanilla_nick)
async def vanilla_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get('amount')
    if amount is None:
        amount = "неизвестно"
    nick = msg.text
    await msg.answer(
        f"🍦 ПОЛУЧЕНО!\n\n💰 Сумма: {amount}₽\n👤 Ник: {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты напишите @vanilka_support",
        reply_markup=main_kb
    )
    op_id = f"{msg.from_user.id}_{int(time.time())}"
    details = f"Ванильки|{amount}|{nick}"
    await msg.answer(
        f"✅ Для подтверждения оплаты нажмите кнопку ниже:",
        reply_markup=get_payment_kb(op_id, "vanilla", details)
    )
    await state.clear()

# ========== МАГАЗИН - ПРИВИЛЕГИИ ==========
@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(call: types.CallbackQuery):
    text = "🎁 Привилегии:\n\n"
    for p in PRIVILEGES:
        text += f"{p['emoji']} {p['name']} — {p['price']}₽\n   {p['desc']}\n\n"
    await call.message.edit_text(text, reply_markup=get_privilege_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("priv_"))
async def priv_buy(call: types.CallbackQuery, state: FSMContext):
    name = call.data.split("_")[1]
    priv = next((p for p in PRIVILEGES if p['name'] == name), None)
    if not priv:
        await call.answer("Ошибка")
        return
    await state.update_data(priv_name=priv['name'], priv_price=priv['price'])
    await state.set_state(Form.privilege_nick)
    await call.message.edit_text(f"{priv['emoji']} {priv['name']}\n💰 Цена: {priv['price']}₽\n\n{priv['desc']}\n\nВведите свой игровой ник:")
    await call.answer()

@dp.message(Form.privilege_nick)
async def privilege_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get('priv_name')
    price = data.get('priv_price')
    if name is None:
        name = "неизвестно"
    if price is None:
        price = "неизвестно"
    nick = msg.text
    
    # ПРИНУДИТЕЛЬНЫЙ ОТВЕТ
    await msg.answer(
        f"🎁 ПОЛУЧЕНО!\n\n💰 Цена: {price}₽\n🎁 Привилегия: {name}\n👤 Ник: {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты напишите @vanilka_support",
        reply_markup=main_kb
    )
    
    op_id = f"{msg.from_user.id}_{int(time.time())}"
    details = f"{name}|{price}|{nick}"
    await msg.answer(
        f"✅ Для подтверждения оплаты нажмите кнопку ниже:",
        reply_markup=get_payment_kb(op_id, "priv", details)
    )
    await state.clear()

# ========== МАГАЗИН - ПОДДЕРЖКА ==========
@dp.callback_query(F.data == "shop_support")
async def shop_support(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.support_amount)
    await call.message.edit_text("💝 Поддержка сервера\n\nВведите сумму (10-100000₽):")
    await call.answer()

@dp.message(Form.support_amount)
async def support_amount(msg: types.Message, state: FSMContext):
    if not msg.text.isdigit():
        await msg.answer("❌ Введите число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("❌ Сумма от 10 до 100000")
        return
    await state.update_data(amount=amount)
    await state.set_state(Form.support_nick)
    await msg.answer(f"💝 Сумма: {amount}₽\n\nВведите игровой ник:", reply_markup=cancel_kb)

@dp.message(Form.support_nick)
async def support_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get('amount')
    if amount is None:
        amount = "неизвестно"
    nick = msg.text
    await msg.answer(
        f"💝 ПОЛУЧЕНО!\n\n💰 Сумма: {amount}₽\n👤 Ник: {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты напишите @vanilka_support",
        reply_markup=main_kb
    )
    op_id = f"{msg.from_user.id}_{int(time.time())}"
    details = f"Пожертвование|{amount}|{nick}"
    await msg.answer(
        f"✅ Для подтверждения оплаты нажмите кнопку ниже:",
        reply_markup=get_payment_kb(op_id, "support", details)
    )
    await state.clear()

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
    await bot.send_message(user_id, f"✅ Заявка одобрена!\nIP: {SERVER_IP}\nВерсия: {SERVER_VERSION}")
    await call.message.edit_text(f"{call.message.text}\n\n✅ Одобрено")
    await bot.send_message(CHANNEL_ID, f"✅ Заявка одобрена\nID: {user_id}")
    await call.answer()

@dp.callback_query(F.data.startswith("acc_deny_"))
async def access_deny(call: types.CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[2])
    await bot.send_message(user_id, "❌ Заявка отклонена.")
    await call.message.edit_text(f"{call.message.text}\n\n❌ Отклонено")
    await bot.send_message(CHANNEL_ID, f"❌ Заявка отклонена\nID: {user_id}")
    await call.answer()

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    ticket = parts[1]
    user_id = int(parts[2])
    await state.update_data(reply_user=user_id, reply_ticket=ticket)
    await state.set_state(Form.reply_text)
    await call.message.answer("✏️ Введите ответ:")
    await call.answer()

@dp.message(Form.reply_text)
async def reply_send(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_user')
    ticket = data.get('reply_ticket')
    if not user_id:
        await msg.answer("❌ Ошибка")
        await state.clear()
        return
    try:
        reply_text = f"📨 Ответ администратора\n\n{msg.text}"
        for part in split_long_message(reply_text):
            await bot.send_message(user_id, part)
        await msg.answer("✅ Ответ отправлен!")
        await bot.send_message(CHANNEL_ID, f"📨 Ответ\nID: {ticket}\n💬 {msg.text}")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {e}")
    await state.clear()

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

# ========== НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ==========
@dp.message()
async def unknown(msg: types.Message):
    if msg.text not in ["📋 Правила", "🛒 Магазин", "🚪 Проходка", "⚠️ Жалоба", "❓ Вопрос", "ℹ️ Информация", "❌ Отмена", "✅ Отправить"]:
        await msg.answer("🤔 Используйте кнопки меню 👇", reply_markup=main_kb)

# ========== ЗАПУСК ==========
async def main():
    logging.info("🚀 Запуск...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"✅ Бот запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
