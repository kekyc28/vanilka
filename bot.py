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
RULES = "📜 Правила сервера:\n\n1️⃣ Уважайте других игроков\n2️⃣ Запрещены читы\n3️⃣ Не гриферите\n4️⃣ Не спамите\n5️⃣ Не рекламируйте\n\n⚠️ За нарушение — бан!"

# Хранилища
pending_payments = {}
pending_access_requests = {}
pending_replies = {}
users_db = set()

# ========== ID ТЕМ (топиков) ==========
TOPIC_COMPLAINTS = 2   # 📝 Жалобы
TOPIC_QUESTIONS = 5    # ❓ Вопросы
TOPIC_ACCESS = 7       # 🚪 Проходка
TOPIC_PAYMENTS = 9     # 💰 Оплаты
TOPIC_REPLIES = 12      # 📨 Ответы администратора
TOPIC_ANNOUNCEMENTS = NONE   # 📢 Объявления

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

class ScreenshotStates(StatesGroup):
    waiting = State()

class AnnouncementStates(StatesGroup):
    waiting_text = State()

# ========== ПРИВИЛЕГИИ ==========
PRIVILEGES = [
    {"name": "VIP", "price": 150, "desc": "/kit vip, цвет в чате, 3 дома", "emoji": "🍃"},
    {"name": "Premium", "price": 300, "desc": "Все привилегии VIP, /fly, 5 домов", "emoji": "⭐"},
    {"name": "Deluxe", "price": 500, "desc": "Все привилегии Premium, /ec, 10 домов", "emoji": "👑"},
    {"name": "Legend", "price": 1000, "desc": "Все привилегии Deluxe, эффект легенды", "emoji": "💎"},
    {"name": "Ultra", "price": 2000, "desc": "Все привилегии Legend, /nick, /speed", "emoji": "⚡"},
    {"name": "Titan", "price": 3500, "desc": "Все привилегии Ultra, команды Титана", "emoji": "🔱"},
    {"name": "God", "price": 5000, "desc": "Все привилегии Titan, свой цвет в чате", "emoji": "👾"}
]

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard(user_id: int = None):
    buttons = [
        [KeyboardButton(text="📋 Правила")],
        [KeyboardButton(text="🛒 Магазин"), KeyboardButton(text="🚪 Проходка")],
        [KeyboardButton(text="⚠️ Жалоба"), KeyboardButton(text="❓ Вопрос")],
        [KeyboardButton(text="ℹ️ Информация")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([KeyboardButton(text="📢 Объявление")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)
finish_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="✅ Отправить")], [KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

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

def get_reply_kb(user_id, ticket_type):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ответить", callback_data=f"reply_{ticket_type}_{user_id}")
    builder.button(text="❌ Закрыть", callback_data=f"close_{ticket_type}_{user_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_access_decision_kb(user_id, access_type):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Принять", callback_data=f"access_accept_{access_type}_{user_id}")
    builder.button(text="❌ Отказать", callback_data=f"access_deny_{access_type}_{user_id}")
    builder.adjust(2)
    return builder.as_markup()

def get_payment_kb(op_id):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data=f"pay_{op_id}")
    builder.button(text="❌ Отменить", callback_data=f"cancel_{op_id}")
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

async def send_to_channel(chat_id: int, text: str = None, topic_id: int = None, media_group=None, photo=None, video=None, caption: str = None, reply_markup=None):
    if media_group:
        return await bot.send_media_group(chat_id, media_group, message_thread_id=topic_id)
    elif photo:
        return await bot.send_photo(chat_id, photo, caption=caption or text, message_thread_id=topic_id, reply_markup=reply_markup)
    elif video:
        return await bot.send_video(chat_id, video, caption=caption or text, message_thread_id=topic_id, reply_markup=reply_markup)
    else:
        return await bot.send_message(chat_id, text, message_thread_id=topic_id, reply_markup=reply_markup)

# ========== ИНИЦИАЛИЗАЦИЯ ==========
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(Command("start"))
async def start(msg: types.Message):
    users_db.add(msg.from_user.id)
    await msg.answer("🎮 Добро пожаловать на сервер Vanilka!", reply_markup=get_main_keyboard(msg.from_user.id))

@dp.message(F.text == "❌ Отмена")
async def cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    if msg.from_user.id in pending_payments:
        del pending_payments[msg.from_user.id]
    if msg.from_user.id in pending_access_requests:
        del pending_access_requests[msg.from_user.id]
    await msg.answer("❌ Действие отменено.", reply_markup=get_main_keyboard(msg.from_user.id))

@dp.message(F.text == "📋 Правила")
async def rules(msg: types.Message):
    await msg.answer(RULES)

@dp.message(F.text == "ℹ️ Информация")
async def info(msg: types.Message):
    await msg.answer(f"🖥️ Сервер Vanilka\n\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}\n🎮 Тип: Vanilla+")

@dp.message(F.text == "🛒 Магазин")
async def shop(msg: types.Message):
    await msg.answer("🛒 Магазин\n\nВыберите категорию 👇", reply_markup=get_shop_kb())

# ========== ОБЪЯВЛЕНИЕ ==========
@dp.message(F.text == "📢 Объявление")
async def announcement_start(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("⛔ У вас нет прав для этой команды.")
        return
    await state.set_state(AnnouncementStates.waiting_text)
    await msg.answer("📢 Введите текст объявления для всех игроков:\n\n(нажмите ❌ Отмена для отмены)", reply_markup=cancel_kb)

@dp.message(AnnouncementStates.waiting_text)
async def announcement_send(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    
    if not users_db:
        await msg.answer("❌ Нет пользователей для рассылки.", reply_markup=get_main_keyboard(msg.from_user.id))
        await state.clear()
        return
    
    announcement_text = f"📢 ОБЪЯВЛЕНИЕ ОТ АДМИНИСТРАЦИИ\n\n{msg.text}"
    
    sent = 0
    failed = 0
    
    for user_id in users_db:
        if user_id == ADMIN_ID:
            continue
        try:
            await bot.send_message(user_id, announcement_text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    
    await msg.answer(f"✅ Объявление отправлено!\n\n📤 Отправлено: {sent}\n❌ Не доставлено: {failed}\n👥 Всего пользователей: {len(users_db)}", reply_markup=get_main_keyboard(msg.from_user.id))
    await state.clear()

# ========== ЖАЛОБА ==========
@dp.message(F.text == "⚠️ Жалоба")
async def complaint_start(msg: types.Message, state: FSMContext):
    await state.set_state(ComplaintStates.nick)
    await msg.answer("📝 Подача жалобы\n\nШаг 1/4: Введите свой игровой ник.", reply_markup=cancel_kb)

@dp.message(ComplaintStates.nick)
async def complaint_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(ComplaintStates.offender)
    await msg.answer(f"✅ Ник принят: {msg.text}\n\n🤬 Шаг 2/4: Введите ник нарушителя.", reply_markup=cancel_kb)

@dp.message(ComplaintStates.offender)
async def complaint_offender(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(offender=msg.text)
    await state.set_state(ComplaintStates.desc)
    await msg.answer(f"✅ Нарушитель: {msg.text}\n\n📝 Шаг 3/4: Опишите, что произошло.", reply_markup=cancel_kb)

@dp.message(ComplaintStates.desc)
async def complaint_desc(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(desc=msg.text)
    await state.set_state(ComplaintStates.media)
    await state.update_data(media=[])
    await msg.answer(
        f"✅ Описание: {msg.text}\n\n📎 Шаг 4/4: Отправьте доказательства (фото, видео).\n\n"
        "Можно отправить несколько файлов.\n"
        "Когда закончите — нажмите «✅ Отправить».",
        reply_markup=finish_kb
    )

@dp.message(ComplaintStates.media)
async def complaint_media(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if msg.text == "✅ Отправить":
        data = await state.get_data()
        media = data.get('media', [])
        text = f"⚠️ Новая жалоба\n\n👤 Заявитель: {data['nick']}\n🤬 Нарушитель: {data['offender']}\n📝 Описание: {data['desc']}\n📎 Файлов: {len(media)}"
        await send_to_channel(CHANNEL_ID, text, topic_id=TOPIC_COMPLAINTS)
        
        # Отправляем все доказательства одной группой (если есть несколько)
        if len(media) > 1:
            media_group = []
            for m in media:
                if m['type'] == 'photo':
                    media_group.append(types.InputMediaPhoto(media=m['id'], caption=f"📸 Доказательства от {data['nick']}" if len(media_group) == 0 else ""))
                elif m['type'] == 'video':
                    media_group.append(types.InputMediaVideo(media=m['id'], caption=f"🎥 Доказательства от {data['nick']}" if len(media_group) == 0 else ""))
            if media_group:
                await send_to_channel(CHANNEL_ID, media_group=media_group, topic_id=TOPIC_COMPLAINTS)
        else:
            # Отправляем по одному
            for m in media:
                if m['type'] == 'photo':
                    await send_to_channel(CHANNEL_ID, photo=m['id'], caption=f"📸 Доказательство от {data['nick']}", topic_id=TOPIC_COMPLAINTS)
                elif m['type'] == 'video':
                    await send_to_channel(CHANNEL_ID, video=m['id'], caption=f"🎥 Доказательство от {data['nick']}", topic_id=TOPIC_COMPLAINTS)
        
        # Админу
        admin_text = f"📨 Новая жалоба\n\n👤 Заявитель: {data['nick']}\n🤬 Нарушитель: {data['offender']}\n📝 Описание: {data['desc']}\n👤 Отправитель: {get_user(msg.from_user)}"
        admin_msg = await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_kb(msg.from_user.id, "complaint"))
        
        # Отправляем админу все доказательства одной группой
        if len(media) > 1:
            admin_media_group = []
            for m in media:
                if m['type'] == 'photo':
                    admin_media_group.append(types.InputMediaPhoto(media=m['id'], caption=f"📸 Доказательства от {data['nick']}" if len(admin_media_group) == 0 else ""))
                elif m['type'] == 'video':
                    admin_media_group.append(types.InputMediaVideo(media=m['id'], caption=f"🎥 Доказательства от {data['nick']}" if len(admin_media_group) == 0 else ""))
            if admin_media_group:
                await bot.send_media_group(ADMIN_ID, admin_media_group)
        else:
            for m in media:
                if m['type'] == 'photo':
                    await bot.send_photo(ADMIN_ID, m['id'], caption=f"📸 Доказательство от {data['nick']}")
                elif m['type'] == 'video':
                    await bot.send_video(ADMIN_ID, m['id'], caption=f"🎥 Доказательство от {data['nick']}")
        
        pending_replies[msg.from_user.id] = {
            "ticket_type": "complaint",
            "message_id": admin_msg.message_id,
            "chat_id": ADMIN_ID,
            "user_nick": data['nick']
        }
        await msg.answer("✅ Жалоба отправлена! Администрация рассмотрит её в ближайшее время.", reply_markup=get_main_keyboard(msg.from_user.id))
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
        await msg.answer("❌ Отправьте фото или видео, или нажмите «✅ Отправить».")

# ========== ВОПРОС ==========
@dp.message(F.text == "❓ Вопрос")
async def question_start(msg: types.Message, state: FSMContext):
    await state.set_state(QuestionStates.nick)
    await msg.answer("❓ Задать вопрос\n\nШаг 1/2: Введите свой игровой ник.", reply_markup=cancel_kb)

@dp.message(QuestionStates.nick)
async def question_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(QuestionStates.text)
    await msg.answer(f"✅ Ник принят: {msg.text}\n\n💬 Шаг 2/2: Напишите ваш вопрос.", reply_markup=cancel_kb)

@dp.message(QuestionStates.text)
async def question_text(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    await send_to_channel(CHANNEL_ID, f"❓ Новый вопрос\n\n👤 Игрок: {data['nick']}\n💬 Вопрос: {msg.text}", topic_id=TOPIC_QUESTIONS)
    
    admin_text = f"📨 Новый вопрос\n\n👤 Игрок: {data['nick']}\n💬 Вопрос: {msg.text}\n👤 Отправитель: {get_user(msg.from_user)}"
    admin_msg = await bot.send_message(ADMIN_ID, admin_text, reply_markup=get_reply_kb(msg.from_user.id, "question"))
    pending_replies[msg.from_user.id] = {
        "ticket_type": "question",
        "message_id": admin_msg.message_id,
        "chat_id": ADMIN_ID,
        "user_nick": data['nick']
    }
    await msg.answer("✅ Вопрос отправлен! Администрация ответит в ближайшее время.", reply_markup=get_main_keyboard(msg.from_user.id))
    await state.clear()

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

@dp.message(AccessStates.nick)
async def access_nick(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(nick=msg.text)
    await state.set_state(AccessStates.about)
    await msg.answer("📝 Расскажите немного о себе:", reply_markup=cancel_kb)

@dp.message(AccessStates.about)
async def access_about(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    await state.update_data(about=msg.text)
    await state.set_state(AccessStates.reason)
    await msg.answer("💭 Почему вы хотите играть именно на нашем сервере?", reply_markup=cancel_kb)

@dp.message(AccessStates.reason)
async def access_reason(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    data = await state.get_data()
    access_type = data.get('access_type')
    nick = data.get('nick')
    about = data.get('about')
    reason = msg.text
    
    if access_type == "paid":
        pending_access_requests[msg.from_user.id] = {
            "nick": nick,
            "about": about,
            "reason": reason,
            "amount": 300
        }
        op_id = f"paid_{int(time.time())}_{msg.from_user.id}"
        pending_payments[msg.from_user.id] = {
            "type": "paid_access",
            "product": "Платная проходка",
            "amount": 300,
            "nick": nick,
            "about": about,
            "reason": reason,
            "op_id": op_id
        }
        await msg.answer(
            f"💎 Платная проходка (300₽)\n\n"
            f"🏦 Карта: {SBER_CARD}\n\n"
            f"📌 После оплаты нажмите кнопку ниже и пришлите скриншот чека.",
            reply_markup=get_payment_kb(op_id)
        )
    else:
        await send_to_channel(CHANNEL_ID, f"🚪 Новая заявка на проходку\n\n👤 Ник: {nick}\n📝 О себе: {about}\n💭 Причина: {reason}\n🎟️ Бесплатная", topic_id=TOPIC_ACCESS)
        await msg.answer("✅ Заявка отправлена! Администрация рассмотрит её в ближайшее время.", reply_markup=get_main_keyboard(msg.from_user.id))
        await bot.send_message(ADMIN_ID, f"📨 Заявка на проходку\n👤 Ник: {nick}\n📝 О себе: {about}\n💭 Причина: {reason}\n🎟️ Бесплатная\n👤 Отправитель: {get_user(msg.from_user)}", reply_markup=get_access_decision_kb(msg.from_user.id, "free"))
    
    await state.clear()

# ========== ВАНИЛЬКИ ==========
@dp.callback_query(F.data == "shop_vanilla")
async def shop_vanilla(call: types.CallbackQuery):
    await call.message.edit_text("🍦 Ванильки\n1₽ = 1 Ванилька\n\nВыберите сумму:", reply_markup=get_vanilla_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("vanilla_"))
async def vanilla_buy(call: types.CallbackQuery, state: FSMContext):
    action = call.data.split("_")[1]
    if action == "custom":
        await state.set_state(VanillaStates.amount)
        await call.message.edit_text("🍦 Введите сумму (от 10 до 100000 ₽):")
        await call.answer()
        return
    amount = int(action)
    await state.update_data(amount=amount)
    await state.set_state(VanillaStates.nick)
    await call.message.delete()
    await call.message.answer(f"🍦 Сумма: {amount} ₽\n\nВведите свой игровой ник:", reply_markup=cancel_kb)

@dp.message(VanillaStates.amount)
async def vanilla_amount(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if not msg.text.isdigit():
        await msg.answer("❌ Введите число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("❌ Сумма должна быть от 10 до 100000 рублей.")
        return
    await state.update_data(amount=amount)
    await state.set_state(VanillaStates.nick)
    await msg.answer(f"🍦 Сумма: {amount} ₽\n\nВведите игровой ник:", reply_markup=cancel_kb)

@dp.message(VanillaStates.nick)
async def vanilla_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get('amount')
    nick = msg.text
    op_id = f"vanilla_{int(time.time())}_{msg.from_user.id}"
    
    pending_payments[msg.from_user.id] = {
        "type": "vanilla",
        "product": "Ванильки",
        "amount": amount,
        "nick": nick,
        "op_id": op_id
    }
    
    await msg.answer(
        f"🍦 Пополнение Ванилек\n\n"
        f"💰 Сумма: {amount} ₽\n"
        f"👤 Ник: {nick}\n\n"
        f"🏦 Карта: {SBER_CARD}\n\n"
        f"📌 После оплаты нажмите кнопку ниже и пришлите скриншот чека.",
        reply_markup=get_payment_kb(op_id)
    )
    await state.clear()

# ========== ПРИВИЛЕГИИ ==========
@dp.callback_query(F.data == "shop_privilege")
async def shop_privilege(call: types.CallbackQuery):
    text = "🎁 Привилегии:\n\n"
    for p in PRIVILEGES:
        text += f"{p['emoji']} {p['name']} — {p['price']} ₽\n   {p['desc']}\n\n"
    await call.message.edit_text(text, reply_markup=get_privilege_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("priv_"))
async def privilege_buy(call: types.CallbackQuery, state: FSMContext):
    name = call.data.split("_")[1]
    priv = next((p for p in PRIVILEGES if p['name'] == name), None)
    if not priv:
        await call.answer("❌ Ошибка.")
        return
    await state.update_data(priv_name=priv['name'], priv_price=priv['price'])
    await state.set_state(PrivilegeStates.nick)
    await call.message.delete()
    await call.message.answer(f"{priv['emoji']} {priv['name']}\n💰 Цена: {priv['price']} ₽\n\n{priv['desc']}\n\nВведите свой игровой ник:", reply_markup=cancel_kb)

@dp.message(PrivilegeStates.nick)
async def privilege_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data.get('priv_name')
    price = data.get('priv_price')
    nick = msg.text
    op_id = f"priv_{int(time.time())}_{msg.from_user.id}"
    
    pending_payments[msg.from_user.id] = {
        "type": "privilege",
        "product": f"Привилегия {name}",
        "amount": price,
        "nick": nick,
        "op_id": op_id
    }
    
    await msg.answer(
        f"🎁 Покупка привилегии {name}\n\n"
        f"💰 Цена: {price} ₽\n"
        f"👤 Ник: {nick}\n\n"
        f"🏦 Карта: {SBER_CARD}\n\n"
        f"📌 После оплаты нажмите кнопку ниже и пришлите скриншот чека.",
        reply_markup=get_payment_kb(op_id)
    )
    await state.clear()

# ========== ПОДДЕРЖКА ==========
@dp.callback_query(F.data == "shop_support")
async def shop_support(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(SupportStates.amount)
    await call.message.delete()
    await call.message.answer("💝 Поддержка сервера\n\nВведите сумму (от 10 до 100000 ₽):", reply_markup=cancel_kb)

@dp.message(SupportStates.amount)
async def support_amount(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    if not msg.text.isdigit():
        await msg.answer("❌ Введите число!")
        return
    amount = int(msg.text)
    if amount < 10 or amount > 100000:
        await msg.answer("❌ Сумма должна быть от 10 до 100000 рублей.")
        return
    await state.update_data(amount=amount)
    await state.set_state(SupportStates.nick)
    await msg.answer(f"💝 Сумма: {amount} ₽\n\nВведите игровой ник:", reply_markup=cancel_kb)

@dp.message(SupportStates.nick)
async def support_nick(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get('amount')
    nick = msg.text
    op_id = f"support_{int(time.time())}_{msg.from_user.id}"
    
    pending_payments[msg.from_user.id] = {
        "type": "support",
        "product": "Пожертвование",
        "amount": amount,
        "nick": nick,
        "op_id": op_id
    }
    
    await msg.answer(
        f"💝 Пожертвование\n\n"
        f"💰 Сумма: {amount} ₽\n"
        f"👤 Ник: {nick}\n\n"
        f"🏦 Карта: {SBER_CARD}\n\n"
        f"📌 После оплаты нажмите кнопку ниже и пришлите скриншот чека.",
        reply_markup=get_payment_kb(op_id)
    )
    await state.clear()

# ========== ОБРАБОТКА ОПЛАТЫ ==========
@dp.callback_query(F.data.startswith("pay_"))
async def payment_start(call: types.CallbackQuery, state: FSMContext):
    op_id = call.data.split("pay_")[1]
    payment_data = pending_payments.get(call.from_user.id)
    
    if not payment_data or payment_data.get("op_id") != op_id:
        await call.answer("❌ Операция не найдена")
        await call.message.delete()
        return
    
    await state.set_state(ScreenshotStates.waiting)
    await call.message.delete()
    await call.message.answer(
        "📸 Пожалуйста, отправьте скриншот чека об оплате.\n\n"
        "На скриншоте должны быть видны:\n"
        "• Сумма перевода\n"
        "• Дата перевода\n\n"
        "Или нажмите «❌ Отмена»",
        reply_markup=cancel_kb
    )
    await call.answer()

@dp.message(ScreenshotStates.waiting)
async def process_screenshot(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Отмена":
        await cancel(msg, state)
        return
    
    if not msg.photo:
        await msg.answer("❌ Пожалуйста, отправьте скриншот (фото) чека об оплате.\n\nИли нажмите «❌ Отмена»")
        return
    
    payment_data = pending_payments.get(msg.from_user.id)
    if not payment_data:
        await msg.answer("❌ Операция не найдена. Начните заново.")
        await state.clear()
        return
    
    product_name = payment_data["product"]
    amount = payment_data["amount"]
    nick = payment_data["nick"]
    payment_type = payment_data["type"]
    
    # Отправляем в тему оплат
    channel_text = f"✅ Новая оплата\n📦 {product_name}\n👤 {nick}\n💰 {amount} ₽\n📸 Скриншот чека прилагается"
    await send_to_channel(CHANNEL_ID, photo=msg.photo[-1].file_id, caption=channel_text, topic_id=TOPIC_PAYMENTS)
    
    if payment_type == "paid_access":
        access_data = pending_access_requests.get(msg.from_user.id, {})
        # В тему проходки отправляем ТОЛЬКО информацию
        access_info = (
            f"💎 ПЛАТНАЯ ПРОХОДКА (ОПЛАЧЕНО)\n\n"
            f"👤 Ник: {nick}\n"
            f"📝 О себе: {access_data.get('about', 'не указано')}\n"
            f"💭 Причина: {access_data.get('reason', 'не указана')}\n"
            f"💰 Сумма: 300 ₽"
        )
        await send_to_channel(CHANNEL_ID, access_info, topic_id=TOPIC_ACCESS)
        
        # Сохраняем ник для последующего одобрения/отказа
        pending_payments[msg.from_user.id]["nick"] = nick
        
        admin_info = (
            f"💎 ПЛАТНАЯ ПРОХОДКА (ОПЛАЧЕНО, ожидает подтверждения)\n\n"
            f"👤 Ник: {nick}\n"
            f"📝 О себе: {access_data.get('about', 'не указано')}\n"
            f"💭 Причина: {access_data.get('reason', 'не указана')}\n"
            f"💰 Сумма: 300 ₽\n"
            f"👤 Отправитель: {get_user(msg.from_user)}\n\n"
            f"📸 Скриншот чека прилагается"
        )
        await bot.send_photo(ADMIN_ID, msg.photo[-1].file_id, caption=admin_info, reply_markup=get_access_decision_kb(msg.from_user.id, "paid"))
        
        if msg.from_user.id in pending_access_requests:
            del pending_access_requests[msg.from_user.id]
    else:
        admin_text = (
            f"✅ НОВАЯ ОПЛАТА (требует проверки)\n\n"
            f"📦 Товар: {product_name}\n"
            f"💰 Сумма: {amount} ₽\n"
            f"👤 Ник в игре: {nick}\n"
            f"👤 Отправитель: {get_user(msg.from_user)}\n\n"
            f"📸 Скриншот чека прилагается:"
        )
        await bot.send_photo(ADMIN_ID, msg.photo[-1].file_id, caption=admin_text)
    
    await msg.answer(
        f"✅ Ваш платёж зарегистрирован!\n\n"
        f"Администратор проверит скриншот и начислит покупку в ближайшее время.",
        reply_markup=get_main_keyboard(msg.from_user.id)
    )
    
    await state.clear()
    # НЕ удаляем pending_payments, так как ник нужен для одобрения/отказа

# ========== ОТМЕНА ОПЛАТЫ ==========
@dp.callback_query(F.data.startswith("cancel_"))
async def payment_cancel(call: types.CallbackQuery):
    payment_data = pending_payments.get(call.from_user.id)
    product_name = payment_data["product"] if payment_data else "Операция"
    
    await call.message.delete()
    await call.message.answer(f"❌ {product_name} отменена.\n\nВы можете начать заново в любой момент.", reply_markup=get_main_keyboard(call.from_user.id))
    await call.answer()
    
    if call.from_user.id in pending_payments:
        del pending_payments[call.from_user.id]
    if call.from_user.id in pending_access_requests:
        del pending_access_requests[call.from_user.id]

# ========== РЕШЕНИЯ ПО ПРОХОДКЕ ==========
@dp.callback_query(F.data.startswith("access_accept_free_"))
async def access_accept_free(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[3])
    await call.message.edit_reply_markup(reply_markup=None)
    
    nick_match = re.search(r"👤 Ник: ([^\n]+)", call.message.caption if call.message.caption else call.message.text)
    nick = nick_match.group(1) if nick_match else "неизвестен"
    
    await bot.send_message(user_id, f"✅ Ваша заявка на проходку одобрена!\n\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}\n\n{RULES}\n\n🎮 Приятной игры!")
    await send_to_channel(CHANNEL_ID, f"✅ Бесплатная проходка одобрена для игрока {nick}", topic_id=TOPIC_ACCESS)
    await call.answer("Заявка одобрена")

@dp.callback_query(F.data.startswith("access_deny_free_"))
async def access_deny_free(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[3])
    await call.message.edit_reply_markup(reply_markup=None)
    
    nick_match = re.search(r"👤 Ник: ([^\n]+)", call.message.caption if call.message.caption else call.message.text)
    nick = nick_match.group(1) if nick_match else "неизвестен"
    
    await bot.send_message(user_id, f"❌ К сожалению, ваша заявка на проходку отклонена.\n\nВы можете попробовать снова позже.")
    await send_to_channel(CHANNEL_ID, f"❌ Бесплатная проходка отклонена для игрока {nick}", topic_id=TOPIC_ACCESS)
    await call.answer("Заявка отклонена")

@dp.callback_query(F.data.startswith("access_accept_paid_"))
async def access_accept_paid(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[3])
    await call.message.edit_reply_markup(reply_markup=None)
    
    # Получаем ник игрока из pending_payments
    nick = "неизвестен"
    # Ищем в pending_payments по user_id
    for uid, data in pending_payments.items():
        if uid == user_id and data.get("type") == "paid_access":
            nick = data.get("nick", "неизвестен")
            break
    
    await bot.send_message(user_id, f"✅ Ваша платная заявка на проходку одобрена!\n\n🌐 IP: {SERVER_IP}\n📦 Версия: {SERVER_VERSION}\n\n{RULES}\n\n🎮 Приятной игры!")
    await send_to_channel(CHANNEL_ID, f"✅ Платная проходка одобрена для игрока {nick}", topic_id=TOPIC_ACCESS)
    
    # Очищаем данные после обработки
    if user_id in pending_payments:
        del pending_payments[user_id]
    
    await call.answer("Заявка одобрена")

@dp.callback_query(F.data.startswith("access_deny_paid_"))
async def access_deny_paid(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[3])
    await call.message.edit_reply_markup(reply_markup=None)
    
    # Получаем ник игрока из pending_payments
    nick = "неизвестен"
    for uid, data in pending_payments.items():
        if uid == user_id and data.get("type") == "paid_access":
            nick = data.get("nick", "неизвестен")
            break
    
    await bot.send_message(user_id, f"❌ К сожалению, ваша платная заявка на проходку отклонена.\n\nВы можете попробовать снова позже.")
    await send_to_channel(CHANNEL_ID, f"❌ Платная проходка отклонена для игрока {nick}", topic_id=TOPIC_ACCESS)
    
    # Очищаем данные после обработки
    if user_id in pending_payments:
        del pending_payments[user_id]
    
    await call.answer("Заявка отклонена")

# ========== ОТВЕТЫ АДМИНА ==========
@dp.callback_query(F.data.startswith("reply_"))
async def reply_start(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    ticket_type = parts[1]
    user_id = int(parts[2])
    
    await call.message.edit_reply_markup(reply_markup=None)
    
    user_nick = "неизвестен"
    if user_id in pending_replies:
        user_nick = pending_replies[user_id].get("user_nick", "неизвестен")
    
    await state.update_data(reply_user=user_id, reply_ticket_type=ticket_type, reply_user_nick=user_nick)
    await state.set_state(ReplyStates.text)
    
    if ticket_type == "complaint":
        await call.message.answer("✏️ Введите ответ на жалобу:")
    else:
        await call.message.answer("✏️ Введите ответ на вопрос:")
    await call.answer()

@dp.message(ReplyStates.text)
async def reply_send(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_user')
    ticket_type = data.get('reply_ticket_type')
    user_nick = data.get('reply_user_nick', 'неизвестен')
    
    if not user_id:
        await msg.answer("❌ Ошибка: не найден пользователь для ответа.")
        await state.clear()
        return
    
    if ticket_type == "complaint":
        reply_text = f"📨 Ответ администратора на вашу жалобу\n\n{msg.text}\n\nС уважением, администрация сервера."
        success_msg = "✅ Ответ на жалобу отправлен игроку!"
        channel_msg = f"📨 Администратор ответил на жалобу игрока {user_nick}"
    else:
        reply_text = f"📨 Ответ администратора на ваш вопрос\n\n{msg.text}\n\n💡 Если остались вопросы — напишите снова."
        success_msg = "✅ Ответ на вопрос отправлен игроку!"
        channel_msg = f"📨 Администратор ответил на вопрос игрока {user_nick}"
    
    try:
        await bot.send_message(user_id, reply_text)
        await msg.answer(success_msg)
        await send_to_channel(CHANNEL_ID, channel_msg, topic_id=TOPIC_REPLIES)
        
        if user_id in pending_replies:
            del pending_replies[user_id]
    except Exception as e:
        error_msg = str(e)
        if "chat not found" in error_msg:
            await msg.answer(f"❌ Не удалось отправить ответ. Пользователь не начал диалог с ботом.\n\nПопросите пользователя написать боту команду /start")
        else:
            await msg.answer(f"❌ Ошибка при отправке: {e}")
    
    await state.clear()

# ========== РУЧНОЕ ЗАКРЫТИЕ ОБРАЩЕНИЯ ==========
@dp.callback_query(F.data.startswith("close_"))
async def reply_close(call: types.CallbackQuery):
    parts = call.data.split("_")
    ticket_type = parts[1]
    user_id = int(parts[2])
    
    await call.message.edit_reply_markup(reply_markup=None)
    
    user_nick = "неизвестен"
    if user_id in pending_replies:
        user_nick = pending_replies[user_id].get("user_nick", "неизвестен")
    
    if ticket_type == "complaint":
        channel_msg = f"✅ Жалоба игрока {user_nick} закрыта администратором"
        user_msg = "✅ Ваша жалоба закрыта администратором.\n\nСпасибо за обращение!"
    else:
        channel_msg = f"✅ Вопрос игрока {user_nick} закрыт администратором"
        user_msg = "✅ Ваш вопрос закрыт администратором.\n\nСпасибо за обращение!"
    
    await send_to_channel(CHANNEL_ID, channel_msg, topic_id=TOPIC_REPLIES)
    
    try:
        await bot.send_message(user_id, user_msg)
    except Exception:
        pass
    
    if user_id in pending_replies:
        del pending_replies[user_id]
    
    await call.answer("Закрыто")

# ========== КОЛБЭКИ МЕНЮ ==========
@dp.callback_query(F.data == "main_menu")
async def back_main(call: types.CallbackQuery):
    await call.message.delete()
    await call.message.answer("🏠 Главное меню:", reply_markup=get_main_keyboard(call.from_user.id))
    await call.answer()

@dp.callback_query(F.data == "back_shop")
async def back_shop(call: types.CallbackQuery):
    await call.message.edit_text("🛒 Магазин\n\nВыберите категорию:", reply_markup=get_shop_kb())
    await call.answer()

# ========== НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ==========
@dp.message()
async def unknown(msg: types.Message):
    if msg.chat.type in ["group", "supergroup", "channel"]:
        return
    if msg.text not in ["📋 Правила", "🛒 Магазин", "🚪 Проходка", "⚠️ Жалоба", "❓ Вопрос", "ℹ️ Информация", "❌ Отмена", "✅ Отправить", "📢 Объявление"]:
        await msg.answer("🤔 Используйте кнопки меню 👇", reply_markup=get_main_keyboard(msg.from_user.id))

# ========== ЗАПУСК ==========
async def main():
    logging.info("🚀 Запуск бота...")
    await bot.delete_webhook()
    me = await bot.get_me()
    logging.info(f"✅ Бот успешно запущен! @{me.username}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
