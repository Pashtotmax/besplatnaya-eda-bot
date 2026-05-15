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

async def init_db():
    async with aiosqlite.connect('users.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, 
                            subscribed_until TEXT)''')
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔥 Выгодные покупки сегодня")],
    [KeyboardButton(text="🔍 Поиск товара")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Добро пожаловать в <b>Антипереплата</b>!\n\nПомогаем экономить на покупках.", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🔍 Поиск товара")
async def search_request(message: types.Message):
    await message.answer("Напиши, что хочешь купить:\nПример: айфон 15, пуховик, power bank, зимние сапоги")

@dp.message()
async def handle_search(message: types.Message):
    if len(message.text) < 3:
        return
    await message.answer("🔍 Ищу лучшие предложения...")

    text = f"<b>🔍 Результаты по запросу:</b> {message.text}\n\n"
    text += "1️⃣ Хороший вариант найден — от 2340 ₽\n\n"
    text += "2️⃣ |||||||||||||||||| (заблюрено)\n"
    text += "3️⃣ |||||||||||||||||| (заблюрено)\n\n"
    text += "🔒 Полные результаты — только по подписке 0.99$/мес"

    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Антипереплата»",
        description="Неограниченный поиск товаров",
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
    await message.answer("🎉 Подписка активирована!")

async def main():
    await init_db()
    print("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
