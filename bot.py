import asyncio
import logging
import os
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
    {"name": "VIP", "price": 150, "desc": "/kit vip, цвет в чате, 3 дома", "emoji": "🍃"},
    {"name": "PREMIUM", "price": 300, "desc": "все привилегии VIP, /fly, 5 домов", "emoji": "⭐"},
    {"name": "DELUXE", "price": 500, "desc": "все привилегии PREMIUM, /ec, 10 домов", "emoji": "👑"},
    {"name": "LEGEND", "price": 1000, "desc": "все привилегии DELUXE, эффект легенды", "emoji": "💎"},
    {"name": "ULTRA", "price": 2000, "desc": "все привилегии LEGEND, /nick, /speed", "emoji": "⚡"},
    {"name": "TITAN", "price": 3500, "desc": "все привилегии ULTRA, команды Титана", "emoji": "🔱"},
    {"name": "GOD", "price": 5000, "desc": "все привилегии TITAN, свой цвет в чате", "emoji": "👾"}
]

# ========== СОСТОЯНИЯ ==========
class ComplaintStates(StatesGroup):
    nick = State()
    offender = State()
    desc = State()
    media = State()

class QuestionStates(StatesGroup):
    nick = State()
    text = State()

class AccessStates(StatesGroup):
    typ = State()
    nick = State()
    reason = State()

class ReplyState(StatesGroup):
    text = State()

# ========== КЛАВИАТУРЫ ==========
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
        return f"@{user.username.split('|')[0].strip()}"
    return f"ID: {user.id}"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
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
    await msg.answer("❌ Отменено", reply_markup=main_kb)

@dp.message(F.text == "📋 Правила")
async def rules(msg: types.Message):
    await msg.answer("📜 Правила:\n1. Уважайте других\n2. Запрещены читы\n3. Не гриферите\n4. Не спамите\n5. Не рекламируйте")

@dp.message(F.text == "ℹ️ Информация")
async def info(msg: types.Message):
    await msg.answer(f"🖥️ Сервер Vanilka\nIP: {SERVER_IP}\nВерсия: {SERVER_VERSION}")

@dp.message(F.text == "🛒 Магазин")
async def shop(msg: types.Message):
    await msg.answer("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())

# ========== МАГАЗИН (КОЛБЭКИ) ==========
@dp.callback_query(F.data == "main_menu")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("Главное меню:", reply_markup=main_kb)
    await call.answer()

@dp.callback_query(F.data == "back_shop")
async def back_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n\nВыбери категорию:", reply_markup=get_shop_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(call: types.CallbackQuery):
    await call.message.edit_text("🍦 Ванильки\n1₽ = 1 Ванилька\n\nВыбери сумму:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(call: types.CallbackQuery):
    text = "🎁 Привилегии:\n\n"
    for p in PRIVILEGES:
        text += f"{p['emoji']} {p['name']} — {p['price']}₽\n   {p['desc']}\n\n"
    await call.message.edit_text(text, reply_markup=get_privilege_kb())
    await call.answer()

@dp.callback_query(F.data == "shop_support")
async def shop_support(call: types.CallbackQuery):
    await call.message.edit_text("💝 Поддержка сервера\n\nСпасибо, что помогаете нам развиваться!\n\nНапишите сумму в чат (от 10 до 100000₽):")
    await call.answer()

# ========== ПОКУПКИ ==========
@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_buy(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    if action == "custom":
        await state.set_state(VanillaDonateStates.waiting_for_amount)
        await call.message.edit_text("🍦 Введите сумму (от 10 до 100000₽):")
        await call.answer()
        return
    amount = int(action)
    await state.update_data(amount=amount, operation="vanilla")
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await call.message.edit_text(f"🍦 Сумма: {amount}₽\n\nВведите свой игровой ник:")
    await call.answer()

@dp.callback_query(F.data.startswith("priv_"))
async def priv_buy(call: types.CallbackQuery, state: FSMContext):
    name = call.data.split("_")[1]
    priv = next((p for p in PRIVILEGES if p['name'] == name), None)
    if not priv:
        await call.answer("Ошибка")
        return
    await state.update_data(priv_name=priv['name'], priv_price=priv['price'], operation="priv")
    await state.set_state(PrivilegeStates.waiting_for_nick)
    await call.message.edit_text(f"{priv['emoji']} {priv['name']}\n💰 Цена: {priv['price']}₽\n\n{priv['desc']}\n\nВведите игровой ник:")
    await call.answer()

# ========== СОСТОЯНИЯ ДЛЯ ПОКУПОК ==========
class VanillaDonateStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_nick = State()

class PrivilegeStates(StatesGroup):
    waiting_for_nick = State()

@dp.message(VanillaDonateStates.waiting_for_amount)
async def vanilla_amount(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if not msg.text.isdigit():
        await msg.answer("Введите число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("Сумма от 10 до 100000")
        return
    await state.update_data(amount=amount)
    await state.set_state(VanillaDonateStates.waiting_for_nick)
    await msg.answer(f"🍦 Сумма: {amount}₽\n\nВведите игровой ник:", reply_markup=cancel_kb)

@dp.message(VanillaDonateStates.waiting_for_nick)
async def vanilla_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    amount = data.get('amount')
    nick = msg.text
    op_id = f"{msg.from_user.id}_{int(time.time())}"
    details = f"Ванильки|{amount}|{nick}"
    
    await msg.answer(
        f"🍦 Пополнение Ванилек\n\n💰 {amount}₽\n🍦 {amount} Ванилек\n👤 {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку ниже",
        reply_markup=get_payment_kb(op_id, "vanilla", details)
    )
    await bot.send_message(CHANNEL_ID, f"🍦 Заявка на пополнение\n👤 {nick}\n💰 {amount}₽")
    await bot.send_message(ADMIN_ID, f"📨 Заявка на пополнение\n👤 {nick}\n💰 {amount}₽\n👤 {get_user(msg.from_user)}")
    await state.clear()

@dp.message(PrivilegeStates.waiting_for_nick)
async def privilege_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    name = data.get('priv_name')
    price = data.get('priv_price')
    nick = msg.text
    op_id = f"{msg.from_user.id}_{int(time.time())}"
    details = f"Привилегия {name}|{price}|{nick}"
    
    await msg.answer(
        f"🎁 Покупка {name}\n\n💰 {price}₽\n👤 {nick}\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку ниже",
        reply_markup=get_payment_kb(op_id, "priv", details)
    )
    await bot.send_message(CHANNEL_ID, f"🎁 Заявка на покупку\n👤 {nick}\n🎁 {name}\n💰 {price}₽")
    await bot.send_message(ADMIN_ID, f"📨 Заявка на покупку\n👤 {nick}\n🎁 {name}\n💰 {price}₽\n👤 {get_user(msg.from_user)}")
    await state.clear()

@dp.message(SupportStates.waiting_for_amount)
async def support_amount(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if not msg.text.isdigit():
        await msg.answer("Введите число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("Сумма от 10 до 100000")
        return
    await state.update_data(amount=amount)
    await state.set_state(SupportStates.waiting_for_nick)
    await msg.answer(f"💝 Сумма: {amount}₽\n\nВведите игровой ник:", reply_markup=cancel_kb)

class SupportStates(StatesGroup):
    waiting_for_nick = State()
    waiting_for_amount = State()

@dp.message(SupportStates.waiting_for_nick)
async def support_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    amount = data.get('amount')
    nick = msg.text
    op_id = f"{msg.from_user.id}_{int(time.time())}"
    details = f"Пожертвование|{amount}|{nick}"
    
    await msg.answer(
        f"💝 Пожертвование\n\n👤 {nick}\n💰 {amount}₽\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку ниже",
        reply_markup=get_payment_kb(op_id, "support", details)
    )
    await bot.send_message(CHANNEL_ID, f"💝 Пожертвование\n👤 {nick}\n💰 {amount}₽")
    await bot.send_message(ADMIN_ID, f"📨 Пожертвование\n👤 {nick}\n💰 {amount}₽\n👤 {get_user(msg.from_user)}")
    await state.clear()

# ========== ПОДТВЕРЖДЕНИЕ ОПЛАТЫ ==========
@dp.callback_query(F.data.startswith("pay_"))
async def payment_confirm(call: types.CallbackQuery):
    try:
        parts = call.data.split("_")
        if parts[1] == "cancel":
            typ = parts[2]
            op_id = parts[3]
            type_names = {"vanilla": "Пополнение Ванилек", "priv": "Покупка привилегии", "support": "Пожертвование", "paid_access": "Платная проходка"}
            name = type_names.get(typ, "Операция")
            await bot.send_message(CHANNEL_ID, f"❌ {name} отменена\n👤 {get_user(call.from_user)}")
            await call.message.delete()
            await call.message.answer(f"❌ {name} отменена", reply_markup=main_kb)
            await bot.send_message(ADMIN_ID, f"❌ {name.upper()} ОТМЕНЕНА\n👤 {get_user(call.from_user)}")
            await call.answer("Отменено")
            return
        
        typ = parts[1]
        op_id = parts[2]
        details = "_".join(parts[3:])
        
        if "|" in details:
            name, amount, nick = details.split("|")
        else:
            name, amount, nick = "Операция", "?", "?"
        
        await bot.send_message(CHANNEL_ID, f"✅ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ\n\n📦 {name}\n💰 {amount}₽\n👤 {get_user(call.from_user)}\n👤 Ник: {nick}")
        await bot.send_message(ADMIN_ID, f"✅ ПОДТВЕРЖДЕНИЕ ОПЛАТЫ\n\n📦 {name}\n💰 {amount}₽\n👤 {get_user(call.from_user)}\n👤 Ник: {nick}\n🆔 {op_id}")
        await call.message.delete()
        await call.message.answer(f"✅ Спасибо за оплату!\n\nВаш платёж за {name} зарегистрирован.", reply_markup=main_kb)
        await call.answer("Подтверждено")
    except Exception as e:
        logging.error(f"Ошибка оплаты: {e}")
        await call.answer("Ошибка")

# ========== ПРОХОДКА ==========
@dp.message(F.text == "🚪 Проходка")
async def access_start(msg: types.Message):
    await msg.answer("🚪 Проходка\n\nВыберите тип:", reply_markup=get_access_kb())

@dp.callback_query(F.data == "access_free")
async def access_free(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(typ="free")
    await state.set_state(AccessStates.nick)
    await call.message.edit_text("🎟️ Бесплатная проходка\n\nВведите игровой ник:")
    await call.answer()

@dp.callback_query(F.data == "access_paid")
async def access_paid(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(typ="paid")
    await state.set_state(AccessStates.nick)
    await call.message.edit_text("💎 Платная проходка (300₽)\n\nВведите игровой ник:")
    await call.answer()

@dp.message(AccessStates.nick)
async def access_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(AccessStates.reason)
    await msg.answer("💭 Почему хотите играть у нас?", reply_markup=cancel_kb)

@dp.message(AccessStates.reason)
async def access_reason(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    typ = data.get('typ')
    nick = data.get('nick')
    reason = msg.text
    
    await bot.send_message(CHANNEL_ID, f"🚪 ЗАЯВКА НА ПРОХОДКУ\n👤 {nick}\n💭 {reason}\n{'💎 Платная' if typ == 'paid' else '🎟️ Бесплатная'}")
    
    if typ == "paid":
        op_id = f"{msg.from_user.id}_{int(time.time())}"
        details = f"Платная проходка|300|{nick}"
        await msg.answer(
            f"💎 Платная проходка (300₽)\n\n🏦 Карта: {SBER_CARD}\n\n📌 После оплаты нажмите кнопку ниже",
            reply_markup=get_payment_kb(op_id, "paid_access", details)
        )
        await bot.send_message(ADMIN_ID, f"📨 ЗАЯВКА НА ПРОХОДКУ\n👤 {nick}\n💭 {reason}\n💎 Платная (ожидает оплаты)\n👤 {get_user(msg.from_user)}")
    else:
        await msg.answer("✅ Заявка отправлена!", reply_markup=main_kb)
        await bot.send_message(ADMIN_ID, f"📨 ЗАЯВКА НА ПРОХОДКУ\n👤 {nick}\n💭 {reason}\n🎟️ Бесплатная\n👤 {get_user(msg.from_user)}", reply_markup=get_access_decision_kb(msg.from_user.id, "free"))
    
    await state.clear()

# ========== РЕШЕНИЯ ПО ПРОХОДКЕ ==========
@dp.callback_query(F.data.startswith("acc_accept_"))
async def access_accept(call: types.CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[2])
    await bot.send_message(user_id, f"✅ Ваша заявка одобрена!\nIP: {SERVER_IP}\nВерсия: {SERVER_VERSION}\n\nПриятной игры!")
    await call.message.edit_text(f"{call.message.text}\n\n✅ Одобрено {get_user(call.from_user)}")
    await bot.send_message(CHANNEL_ID, f"✅ Заявка одобрена\n👤 ID: {user_id}")
    await call.answer()

@dp.callback_query(F.data.startswith("acc_deny_"))
async def access_deny(call: types.CallbackQuery):
    parts = call.data.split("_")
    user_id = int(parts[2])
    await bot.send_message(user_id, "❌ Заявка отклонена. Попробуйте позже.")
    await call.message.edit_text(f"{call.message.text}\n\n❌ Отклонено {get_user(call.from_user)}")
    await bot.send_message(CHANNEL_ID, f"❌ Заявка отклонена\n👤 ID: {user_id}")
    await call.answer()

# ========== ЖАЛОБЫ ==========
@dp.message(F.text == "⚠️ Жалоба")
async def complaint_start(msg: types.Message, state: FSMContext):
    await state.set_state(ComplaintStates.nick)
    await msg.answer("📝 Жалоба\n\n1/4: Ваш ник?", reply_markup=cancel_kb)

@dp.message(ComplaintStates.nick)
async def complaint_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(ComplaintStates.offender)
    await msg.answer("2/4: Ник нарушителя?", reply_markup=cancel_kb)

@dp.message(ComplaintStates.offender)
async def complaint_offender(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(offender=msg.text)
    await state.set_state(ComplaintStates.desc)
    await msg.answer("3/4: Что произошло?", reply_markup=cancel_kb)

@dp.message(ComplaintStates.desc)
async def complaint_desc(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(desc=msg.text)
    await state.set_state(ComplaintStates.media)
    await state.update_data(media=[])
    await msg.answer("4/4: Отправьте доказательства (фото/видео)\n\nКогда закончите - нажмите Отправить", reply_markup=finish_kb)

@dp.message(ComplaintStates.media)
async def complaint_media(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if msg.text == "✅ Отправить":
        data = await state.get_data()
        media = data.get('media', [])
        ticket = f"comp_{int(time.time())}"
        text = f"⚠️ ЖАЛОБА\n👤 {data['nick']}\n🤬 {data['offender']}\n📝 {data['desc']}\n📎 Файлов: {len(media)}"
        await bot.send_message(CHANNEL_ID, text)
        for m in media:
            if m['type'] == 'photo':
                await bot.send_photo(CHANNEL_ID, m['id'], caption=f"📸 от {data['nick']}")
            elif m['type'] == 'video':
                await bot.send_video(CHANNEL_ID, m['id'], caption=f"🎥 от {data['nick']}")
        await bot.send_message(ADMIN_ID, f"📨 ЖАЛОБА\n👤 {data['nick']}\n🤬 {data['offender']}\n📝 {data['desc']}\n👤 {get_user(msg.from_user)}", reply_markup=get_reply_kb(ticket, msg.from_user.id))
        await msg.answer("✅ Жалоба отправлена!", reply_markup=main_kb)
        await state.clear()
        return
    data = await state.get_data()
    media = data.get('media', [])
    if msg.photo:
        media.append({'type': 'photo', 'id': msg.photo[-1].file_id})
        await msg.answer(f"📸 Добавлено ({len(media)})")
    elif msg.video:
        media.append({'type': 'video', 'id': msg.video.file_id})
        await msg.answer(f"🎥 Добавлено ({len(media)})")
    else:
        await msg.answer("Отправьте фото или видео")
        return
    await state.update_data(media=media)

# ========== ВОПРОСЫ ==========
@dp.message(F.text == "❓ Вопрос")
async def question_start(msg: types.Message, state: FSMContext):
    await state.set_state(QuestionStates.nick)
    await msg.answer("❓ Вопрос\n\n1/2: Ваш ник?", reply_markup=cancel_kb)

@dp.message(QuestionStates.nick)
async def question_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(QuestionStates.text)
    await msg.answer("2/2: Ваш вопрос?", reply_markup=cancel_kb)

@dp.message(QuestionStates.text)
async def question_text(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    ticket = f"q_{int(time.time())}"
    await bot.send_message(CHANNEL_ID, f"❓ ВОПРОС\n👤 {data['nick']}\n💬 {msg.text}")
    await bot.send_message(ADMIN_ID, f"📨 ВОПРОС\n👤 {data['nick']}\n💬 {msg.text}\n👤 {get_user(msg.from_user)}", reply_markup=get_reply_kb(ticket, msg.from_user.id))
    await msg.answer("✅ Вопрос отправлен!", reply_markup=main_kb)
    await state.clear()

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    ticket = parts[1]
    user_id = int(parts[2])
    await state.update_data(reply_user=user_id, reply_ticket=ticket)
    await state.set_state(ReplyState.text)
    await call.message.answer("✏️ Введите ответ:")
    await call.answer()

@dp.message(ReplyState.text)
async def reply_send(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_user')
    ticket = data.get('reply_ticket')
    if not user_id:
        await msg.answer("Ошибка")
        await state.clear()
        return
    try:
        await bot.send_message(user_id, f"📨 Ответ администратора\n\n{msg.text}")
        await msg.answer("✅ Ответ отправлен!")
        await bot.send_message(CHANNEL_ID, f"📨 Ответ\n🆔 {ticket}\n💬 {msg.text}")
    except Exception as e:
        await msg.answer(f"Ошибка: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("close_"))
async def reply_close(call: types.CallbackQuery):
    ticket = call.data.split("_")[1]
    await bot.send_message(CHANNEL_ID, f"✅ Обращение закрыто\n🆔 {ticket}\n👤 {get_user(call.from_user)}")
    await call.message.edit_text(f"{call.message.text}\n\n✅ Закрыто")
    await call.answer()

# ========== ЗАПУСК ==========
async def main():
    logging.info("Запуск...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"Бот запущен: @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
