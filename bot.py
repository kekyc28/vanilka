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

# ========== НАСТРОЙКИ (из переменных окружения Railway) ==========
TOKEN = os.getenv("BOT_TOKEN")
if TOKEN is None:
    raise ValueError("BOT_TOKEN не найден! Добавь переменную окружения BOT_TOKEN")

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003965525902"))
SERVER_IP = os.getenv("SERVER_IP", "vanilka.minecraft.surf")
SERVER_VERSION = os.getenv("SERVER_VERSION", "1.21.11")
SBER_CARD = os.getenv("SBER_CARD", "2202205046722309")

# Привилегии (7 штук)
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

# Клавиатура отмены
def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# Клавиатура для завершения жалобы
def get_finish_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Завершить и отправить жалобу")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )

# Главная клавиатура
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

# Инлайн клавиатура для магазина
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
    await message.answer("Шаг 4/4: Отправьте доказательства (фото, видео, файлы)\n\nВы можете отправить несколько файлов по очереди.\nКогда закончите, нажмите «✅ Завершить и отправить жалобу»", reply_markup=get_finish_keyboard())

@dp.message(ComplaintStates.waiting_for_proof)
async def complaint_add_proof(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel_action(message, state)
        return
    
    if message.text == "✅ Завершить и отправить жалобу":
        data = await state.get_data()
        proofs = data.get('proofs', [])
        
        complaint_text = (
            f"⚠️ НОВАЯ ЖАЛОБА ⚠️\n\n"
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
    question_text = (
        f"❓ НОВЫЙ ВОПРОС ❓\n\n"
        f"👤 Игрок: {data['nick']}\n"
        f"💬 Вопрос: {message.text}"
    )
    await bot.send_message(CHANNEL_ID, question_text)
    await message.answer("✅ Вопрос отправлен! Администрация ответит в ближайшее время.", reply_markup=get_main_keyboard())
    await state.clear()

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
        f"Введите свой игровой ник:"
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

# ========== ЗАПУСК БОТА ==========
async def main():
    logger.info("✅ Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
