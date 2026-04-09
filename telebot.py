import asyncio
from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram import F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from email_validator import validate_email, EmailNotValidError
import sqlite3
import os
from dotenv import load_dotenv
import time
import logging
logging.basicConfig(level=logging.INFO)
load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
users_last_request = {}
bot = Bot(token=TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("../.venv/applications.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    email TEXT,
    phone TEXT
)
""")

conn.commit()

keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Оставить заявку")],
        [KeyboardButton(text="❌ Отмена")]
    ],
    resize_keyboard=True
)
contact_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📱 Отправить номер", request_contact=True)]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Заявки")],
        [KeyboardButton(text="📊 Кол-во заявок")],
        [KeyboardButton(text="🗑 Очистить базу")]
    ],
    resize_keyboard=True
)
confirm_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить")],
        [KeyboardButton(text="❌ Заполнить заново")]
    ],
    resize_keyboard=True
)
class Form(StatesGroup):
    name = State()
    email = State()
    phone = State()
    confirm = State()
@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return

    await message.answer("👨‍💼 Админ-панель", reply_markup=admin_keyboard)

@dp.message(F.text == "📋 Заявки")
async def show_apps(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT name, email, phone FROM applications")
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Заявок пока нет")
        return

    for row in rows:
        await message.answer(
            f"Имя: {row[0]}\n"
            f"Почта: {row[1]}\n"
            f"Телефон: {row[2]}"
        )
@dp.message(F.text == "📊 Кол-во заявок")
async def count_apps(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM applications")
    count = cursor.fetchone()[0]

    await message.answer(f"Всего заявок: {count}")
@dp.message(F.text == "🗑 Очистить базу")
async def clear_db(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("DELETE FROM applications")
    conn.commit()

    await message.answer("✅ База очищена")
@dp.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Заявка отменена",
        reply_markup=keyboard
    )
@dp.message(F.text == "Оставить заявку")
async def application_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    now = time.time()

    if user_id in users_last_request:
        if now - users_last_request[user_id] < 60:
            await message.answer("⏳ Подождите немного перед новой заявкой")
            return

    users_last_request[user_id] = now
    await message.answer("Введите ваше имя:")
    await state.set_state(Form.name)

@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите почту:")
    await state.set_state(Form.email)

@dp.message(Form.email)
async def get_email(message: Message, state: FSMContext):
    try:
        valid = validate_email(message.text)
        email = valid.email
    except EmailNotValidError:
        await message.answer("❌ Неверный email, попробуйте снова:")
        return
    await state.update_data(email=message.text)
    await message.answer("Нажмите кнопку ниже, чтобы отправить номер",
    reply_markup=contact_keyboard)
    await state.set_state(Form.phone)

@dp.message(Form.phone, F.contact)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()

    name = data["name"]
    email = data["email"]
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await message.answer(
        f"Проверь данные:\n\n"
        f"👤 Имя: {name}\n"
        f"📧 Почта: {email}\n"
        f"📱 Телефон: {phone}\n\n"
        "Все верно?",
        reply_markup=confirm_keyboard
    )
    await state.set_state(Form.confirm)
@dp.message(Form.phone)
async def phone_not_contact(message: Message):
    await message.answer("Пожалуйста, используйте кнопку для отправки номера")
@dp.message(Form.confirm, F.text == "✅ Подтвердить")
async def confirm_yes(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]
    email = data["email"]
    phone = data["phone"]
    text = (
        "📩 <b>Новая заявка</b>\n\n"
        f"👤 Имя: {name}\n"
        f"📧 Почта: {email}\n"
        f"📱 Телефон: {phone}"
    )
    cursor.execute(
        "INSERT INTO applications (name, email, phone) VALUES (?, ?, ?)",
        (name, email, phone)
    )
    conn.commit()
    await bot.send_message(ADMIN_ID, text, parse_mode="HTML")
    await message.answer("✅ Заявка отправлена!", reply_markup=keyboard)
    await state.clear()
@dp.message(Form.confirm, F.text == "❌ Заполнить заново")
async def confirm_no(message: Message, state: FSMContext):
    await message.answer("Введите ваше имя:", reply_markup=keyboard)
    await state.set_state(Form.name)
@dp.message(Form.confirm)
async def wrong_confirm(message: Message):
    await message.answer("Пожалуйста, выберите вариант с кнопок 👇")
@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Привет! Нажми кнопку, чтобы оставить заявку",
        reply_markup=keyboard
    )
@dp.message(Command("applications"))
async def show_apps(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer('Введите корректную команду')
        return

    cursor.execute("SELECT name, email, phone FROM applications")
    rows = cursor.fetchall()

    for row in rows:
        await message.answer(
            f"Имя: {row[0]}\nПочта: {row[1]}\nТелефон: {row[2]}"
        )
@dp.message()
async def uncnown_message(message: Message):
    await message.answer('Пожалуйста, нажмите кнопку «Оставить заявку» 👇')

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())