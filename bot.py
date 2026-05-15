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

# ===================== БАЗА ДАННЫХ =====================
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

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 Добро пожаловать в <b>Антипереплата</b>!\n\n"
        "Помогаем находить самые выгодные цены на Wildberries, Ozon и других маркетплейсах.",
        reply_markup=main_menu, parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Поиск товара")
async def search_request(message: types.Message):
    await message.answer("Напиши, что хочешь купить:\nПример: айфон 15, пуховик женский, зимние сапоги, power bank 20000")

@dp.message()
async def handle_search(message: types.Message):
    if len(message.text) < 3:
        return
    
    await message.answer("🔍 Ищу лучшие предложения...")

    # Пока улучшенная заглушка (реальный парсинг добавим позже)
    text = f"<b>🔍 Результаты по запросу:</b> {message.text}\n\n"
    text += "1️⃣ Хороший вариант на Wildberries — от 2340 ₽\n\n"
    text += "2️⃣ |||||||||||||||||| (заблюрено)\n"
    text += "3️⃣ |||||||||||||||||| (заблюрено)\n\n"
    text += "🔒 Полные результаты и лучшие цены доступны только по подписке 0.99$/мес"

    await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "🔥 Выгодные покупки сегодня")
async def hot_deals(message: types.Message):
    await message.answer("🔥 Сейчас ищу самые горячие акции...\n\n(Раздел в разработке)")

# ===================== ПОДПИСКА =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Антипереплата»",
        description="Неограниченный поиск + все цены без цензуры",
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
    async with aiosqlite.connect('users.db') as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, subscribed_until) VALUES (?, ?)", 
                        (message.from_user.id, until))
        await db.commit()
    await message.answer("🎉 Подписка успешно активирована на 30 дней!")

@dp.message(F.text == "👤 Моя подписка")
async def my_sub(message: types.Message):
    async with aiosqlite.connect('users.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                days = (datetime.fromisoformat(row[0]) - datetime.now()).days
                await message.answer(f"✅ Подписка активна!\nОсталось: <b>{days} дней</b>", parse_mode="HTML")
            else:
                await message.answer("❌ У тебя нет активной подписки.")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот «Антипереплата» успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
