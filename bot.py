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

kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
    [KeyboardButton(text="👤 Моя подписка")],
], resize_keyboard=True)

# База данных
async def init_db():
    async with aiosqlite.connect('bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, subscribed_until TEXT)''')
        await db.commit()

@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 Добро пожаловать в <b>Бесплатная Еда</b>!\n\n"
        "Нажми кнопку ниже:", 
        reply_markup=kb, 
        parse_mode="HTML"
    )

# Покупка подписки
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Ежедневные лучшие акции на еду",
        payload="monthly_sub",
        provider_token="",
        currency="XTR",
        prices=prices,
        is_subscription=True
    )

# Успешная оплата
@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    until = (datetime.now() + timedelta(days=30)).isoformat()
    async with aiosqlite.connect('bot.db') as db:
        await db.execute("INSERT OR REPLACE INTO users VALUES (?, ?)", 
                        (message.from_user.id, until))
        await db.commit()
    await message.answer("🎉 Оплата прошла успешно!\nПодписка активна до " + 
                        (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y"))

# Кнопка "Моя подписка"
@dp.message(F.text == "👤 Моя подписка")
async def my_subscription(message: types.Message):
    async with aiosqlite.connect('bot.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            
            if row and row[0]:
                until = datetime.fromisoformat(row[0])
                if until > datetime.now():
                    days_left = (until - datetime.now()).days
                    await message.answer(f"✅ Подписка активна!\nОсталось: <b>{days_left} дней</b>\n"
                                       f"До: {until.strftime('%d.%m.%Y')}", parse_mode="HTML")
                else:
                    await message.answer("❌ Подписка истекла.")
            else:
                await message.answer("❌ У тебя нет активной подписки.\nНажми «Купить подписку 0.99$»")

@dp.pre_checkout_query()
async def pre_checkout(query: types.PreCheckoutQuery):
    await query.answer(ok=True)

async def main():
    await init_db()
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
