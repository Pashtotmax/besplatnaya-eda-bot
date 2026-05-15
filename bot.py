from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite
import aiohttp
from bs4 import BeautifulSoup

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

# ===================== УЛУЧШЕННЫЙ ПОИСК =====================
async def search_products(query: str):
    results = []
    search_query = query.replace(" ", "+")
    
    urls = [
        f"https://www.wildberries.ru/catalog/0/search.aspx?search={search_query}",
        f"https://www.ozon.ru/search/?text={search_query}&from_global=true",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls:
            try:
                async with session.get(url, timeout=15) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        
                        # Более агрессивный поиск товаров
                        items = soup.find_all(['div', 'a'], attrs={"data-testid": True})[:8]
                        if not items:
                            items = soup.find_all(['article', 'div'], class_=lambda x: x and ('product' in str(x).lower() or 'card' in str(x).lower()))[:8]
                        
                        for item in items:
                            title_tag = item.find(['span', 'div', 'h3', 'a'], string=lambda t: t and len(str(t)) > 10)
                            price_tag = item.find(['span', 'div'], string=lambda t: t and any(c in str(t) for c in '₽₽$'))
                            
                            if title_tag:
                                title = title_tag.get_text(strip=True)[:90]
                                price = price_tag.get_text(strip=True) if price_tag else "Цена не найдена"
                                results.append(f"{title}\n💰 {price}")
            except:
                continue
                
    return results[:6] if results else ["По этому запросу пока ничего не найдено. Попробуй изменить формулировку."]

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Добро пожаловать в <b>Антипереплата</b>!\n\nЭкономим на покупках с WB, Ozon и других.", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🔍 Поиск товара")
async def search_request(message: types.Message):
    await message.answer("Напиши, что хочешь найти\n(пример: айфон 15, зимние сапоги 38, кофемашина):")

@dp.message()
async def handle_search(message: types.Message):
    if len(message.text) < 2 or message.text.startswith('/'):
        return
    
    await message.answer("🔍 Ищу лучшие предложения...")
    
    results = await search_products(message.text)
    
    async with aiosqlite.connect('market.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
    
    is_premium = row and row[0] and datetime.fromisoformat(row[0]) > datetime.now() if row else False
    
    text = f"<b>🔍 Результаты по запросу:</b> {message.text}\n\n"
    
    for i, item in enumerate(results[:3], 1):
        if is_premium or i == 1:
            text += f"{i}️⃣ {item}\n\n"
        else:
            text += f"{i}️⃣ |||||||||||||||||| (заблюрено)\n\n"
    
    if not is_premium:
        text += "🔒 Остальные варианты и лучшие цены — только по подписке 0.99$/мес"
    
    await message.answer(text, parse_mode="HTML")

# Подписка (оставляем как было)
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Антипереплата»",
        description="Неограниченный поиск товаров + все цены",
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
    await message.answer("🎉 Подписка активирована!\nТеперь ты видишь все варианты.")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот «Антипереплата» запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
