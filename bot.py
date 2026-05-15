from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite
import aiohttp
import json

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

async def init_db():
    async with aiosqlite.connect('market.db') as db:
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

# ===================== ПРОДВИНУТЫЙ ПОИСК =====================
async def advanced_search(query: str):
    results = []
    q = query.replace(" ", "+")
    
    headers_list = [
        {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"},
        {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"}
    ]

    async with aiohttp.ClientSession() as session:
        # Wildberries search
        try:
            url = f"https://search.wb.ru/exactmatch/ru/common/v4/search?query={q}&limit=10"
            async with session.get(url, headers=headers_list[0], timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    products = data.get('data', {}).get('products', [])[:5]
                    for p in products:
                        name = p.get('name', 'Без названия')
                        price = p.get('salePriceU', 0) // 100 or p.get('priceU', 0) // 100
                        results.append(f"🛍️ {name}\n💰 {price} ₽ (WB)")
        except:
            pass

        # Ozon search (через публичный endpoint)
        try:
            url = f"https://www.ozon.ru/api/composer-api.v1/search?text={q}"
            async with session.get(url, headers=headers_list[1], timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.text()
                    # Простой парсинг
                    if "items" in data:
                        results.append("🔍 Найдено на Ozon — проверь вручную по ссылке")
        except:
            pass

    if not results:
        return ["🤖 К сожалению, по этому запросу сейчас ничего не удалось найти.\n\nПопробуй:\n• Более точный запрос\n• Без бренда сначала"]
    
    return results[:6]

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 <b>Антипереплата</b>\n\nИщем самые выгодные цены на WB, Ozon и других маркетплейсах.", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🔍 Поиск товара")
async def search_request(message: types.Message):
    await message.answer("Напиши, что хочешь купить:\nПример: `айфон 15 128gb`, `зимние сапоги женские 38`, `power bank 20000`")

@dp.message()
async def handle_search(message: types.Message):
    if len(message.text) < 3:
        return

    await message.answer("🔍 Ищу лучшие предложения...")

    results = await advanced_search(message.text)

    async with aiosqlite.connect('market.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
    
    is_premium = row and row[0] and datetime.fromisoformat(row[0]) > datetime.now() if row and row[0] else False

    text = f"<b>Результаты по запросу:</b> {message.text}\n\n"

    for i, item in enumerate(results[:3], 1):
        if is_premium or i == 1:
            text += f"{i}️⃣ {item}\n\n"
        else:
            text += f"{i}️⃣ |||||||||||||||||| (заблюрено)\n\n"

    if not is_premium:
        text += "🔒 Полные результаты и лучшие предложения — только по подписке 0.99$/мес"

    await message.answer(text, parse_mode="HTML")

# Подписка (оставляем)
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
    until = (datetime.now() + timedelta(days=30)).isoformat()
    async with aiosqlite.connect('market.db') as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, subscribed_until) VALUES (?, ?)", 
                        (message.from_user.id, until))
        await db.commit()
    await message.answer("🎉 Подписка активирована!")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот «Антипереплата» запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
