from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite
import aiohttp
from bs4 import BeautifulSoup

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== БАЗА ДАННЫХ =====================
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

# ===================== ПРОСТОЙ ПАРСИНГ =====================
async def search_products(query: str):
    results = []
    urls = [
        f"https://www.wildberries.ru/catalog/0/search.aspx?search={query}",
        f"https://www.ozon.ru/search/?text={query}"
    ]

    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        items = soup.find_all(['div', 'a'], class_=lambda x: x and any(word in str(x).lower() for word in ['product', 'card', 'tile']))[:6]
                        for item in items:
                            title = item.find(['span', 'div', 'h3'], class_=lambda x: x and any(word in str(x).lower() for word in ['title', 'name', 'text']))
                            price = item.find(['span', 'div'], class_=lambda x: x and 'price' in str(x).lower())
                            if title and price:
                                title_text = title.get_text(strip=True)[:80]
                                price_text = price.get_text(strip=True)
                                results.append(f"{title_text}\n💰 {price_text}")
            except:
                continue
    return results[:6] or ["Ничего не найдено по запросу. Попробуй уточнить."]

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Добро пожаловать в <b>Антипереплата</b>!\n\nЗдесь ты экономишь на покупках с WB, Ozon и других маркетплейсов.", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🔥 Выгодные покупки сегодня")
async def hot_deals(message: types.Message):
    await message.answer("🔄 Ищу лучшие акции на WB и Ozon...\n\n(Пока раздел в разработке — скоро будет автоматический дайджест)")

@dp.message(F.text == "🔍 Поиск товара")
async def search_request(message: types.Message):
    await message.answer("Напиши, что хочешь найти (например: «айфон 15», «зимние сапоги 38 размер», «кофемашина»):")

@dp.message()
async def handle_search(message: types.Message):
    if len(message.text) < 3:
        return
    await message.answer("🔍 Ищу лучшие предложения...")
    
    results = await search_products(message.text)
    
    async with aiosqlite.connect('market.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
    
    is_premium = row and row[0] and datetime.fromisoformat(row[0]) > datetime.now()
    
    text = f"<b>🔍 Результаты по запросу:</b> {message.text}\n\n"
    count = len(results) if is_premium else 1
    
    for i, item in enumerate(results[:3], 1):
        if is_premium or i == 1:
            text += f"{i}️⃣ {item}\n\n"
        else:
            text += f"{i}️⃣ |||||||||||||||||| (заблюрено)\n\n"
    
    if not is_premium:
        text += "🔒 Полные результаты и лучшие цены доступны только по подписке 0.99$/мес"
    
    await message.answer(text, parse_mode="HTML")

# ===================== ПОДПИСКА =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Антипереплата»",
        description="Неограниченный поиск + все варианты цен",
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
    await message.answer("🎉 Подписка активирована!\nТеперь ты видишь все варианты цен.")

@dp.message(F.text == "👤 Моя подписка")
async def my_sub(message: types.Message):
    async with aiosqlite.connect('market.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                days = (datetime.fromisoformat(row[0]) - datetime.now()).days
                await message.answer(f"✅ Подписка активна!\nОсталось: <b>{days} дней</b>", parse_mode="HTML")
            else:
                await message.answer("❌ Подписки нет.")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот «Антипереплата» запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
