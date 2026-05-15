from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== БАЗА ДАННЫХ =====================
async def init_db():
    async with aiosqlite.connect('habits.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, 
                            subscribed_until TEXT)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS habits 
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER,
                            name TEXT,
                            streak INTEGER DEFAULT 0,
                            last_done TEXT)''')
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="✅ Отметить привычки")],
    [KeyboardButton(text="📊 Мои привычки")],
    [KeyboardButton(text="➕ Добавить привычку")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== ФУНКЦИИ =====================
async def get_user_habits(user_id: int):
    async with aiosqlite.connect('habits.db') as db:
        async with db.execute("SELECT id, name, streak FROM habits WHERE user_id = ? ORDER BY streak DESC", 
                            (user_id,)) as cursor:
            return await cursor.fetchall()

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 Добро пожаловать в <b>Привычки 2.0</b>!\n\n"
        "Здесь ты будешь формировать полезные привычки и видеть свой прогресс.\n\n"
        "Начни с добавления первой привычки 👇",
        reply_markup=main_menu, parse_mode="HTML"
    )

@dp.message(F.text == "➕ Добавить привычку")
async def add_habit(message: types.Message):
    await message.answer("Напиши название новой привычки (например: «Пить 2 литра воды», «Читать 20 страниц», «Спорт 30 минут»):")
    # В реальной версии здесь можно использовать FSM, но для простоты — следующий шаг вручную

@dp.message(F.text.startswith("Привычка:") or len(F.text) > 3)  # упрощённо
async def save_habit(message: types.Message):
    habit_name = message.text.strip()
    async with aiosqlite.connect('habits.db') as db:
        await db.execute("INSERT INTO habits (user_id, name) VALUES (?, ?)", 
                        (message.from_user.id, habit_name))
        await db.commit()
    await message.answer(f"✅ Привычка «{habit_name}» добавлена!\n\nОтмечай её каждый день.")

@dp.message(F.text == "✅ Отметить привычки")
async def mark_habits(message: types.Message):
    habits = await get_user_habits(message.from_user.id)
    if not habits:
        await message.answer("У тебя пока нет привычек. Добавь первую!")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {name} (+{streak})", callback_data=f"done_{id}")] 
        for id, name, streak in habits
    ])
    await message.answer("Какие привычки выполнил сегодня?", reply_markup=kb)

@dp.callback_query(F.data.startswith("done_"))
async def habit_done(callback: types.CallbackQuery):
    habit_id = int(callback.data.split("_")[1])
    async with aiosqlite.connect('habits.db') as db:
        await db.execute("UPDATE habits SET streak = streak + 1, last_done = ? WHERE id = ?", 
                        (datetime.now().isoformat(), habit_id))
        await db.commit()
    await callback.answer("✅ +1 к цепочке!")
    await callback.message.edit_text("Отлично! Продолжай в том же духе 🔥")

@dp.message(F.text == "📊 Мои привычки")
async def show_stats(message: types.Message):
    habits = await get_user_habits(message.from_user.id)
    if not habits:
        await message.answer("У тебя пока нет привычек.")
        return

    text = "<b>📊 Твой прогресс:</b>\n\n"
    for _, name, streak in habits:
        text += f"• {name} — <b>{streak} дней подряд</b>\n"
    
    await message.answer(text, parse_mode="HTML")

# ===================== ПОДПИСКА =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Привычки 2.0»",
        description="Неограниченное количество привычек + статистика + напоминания",
        payload="monthly_sub",
        provider_token="",
        currency="XTR",
        prices=prices
    )

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    until = (datetime.now() + timedelta(days=30)).isoformat()
    async with aiosqlite.connect('habits.db') as db:
        await db.execute("UPDATE users SET subscribed_until = ? WHERE user_id = ?", 
                        (until, message.from_user.id))
        await db.commit()
    await message.answer("🎉 Подписка активирована!\nТеперь ты можешь отслеживать сколько угодно привычек.")

@dp.message(F.text == "👤 Моя подписка")
async def my_sub(message: types.Message):
    async with aiosqlite.connect('habits.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                days = (datetime.fromisoformat(row[0]) - datetime.now()).days
                await message.answer(f"✅ Подписка активна!\nОсталось: <b>{days} дней</b>", parse_mode="HTML")
            else:
                await message.answer("❌ Подписки нет. Оформи за 0.99$")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот «Привычки 2.0» запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
