from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="🔥 Акции на сегодня")],
], resize_keyboard=True)

async def init_db():
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, subscribed_until TEXT)''')
        await db.commit()

# ==================== ИСПРАВЛЕННАЯ КНОПКА ПОДПИСКИ ====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Ежедневные акции по России и Беларуси",
        payload="monthly_sub_99",
        provider_token="",
        currency="XTR",
        prices=prices,
        # is_subscription=True  ← убрали, чтобы не было ошибки
    )

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    until = (datetime.now() + timedelta(days=30)).isoformat()
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, subscribed_until) VALUES (?, ?)", 
                        (message.from_user.id, until))
        await db.commit()
    await message.answer("🎉 Оплата прошла успешно!\nПодписка активна 30 дней!")

# ==================== ОСТАЛЬНОЕ ====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Бот работает!\nНажми кнопку ниже:", reply_markup=main_menu)

@dp.message(F.text == "👤 Моя подписка")
async def my_sub(message: types.Message):
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] and datetime.fromisoformat(row[0]) > datetime.now():
                await message.answer("✅ Подписка активна")
            else:
                await message.answer("❌ Подписки нет")

async def main():
    await init_db()
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
