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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    urls = [
        f"https://www.wildberries.ru/catalog/0/search.aspx?search={query.replace(' ', '+')}",
        f"https://www.ozon.ru/search/?text={query.replace(' ', '+')}",
    ]

    async with aiohttp.ClientSession(headers=headers) as session:
        for url in urls:
            try:
                async with session.get(url, timeout=12) as resp:
                    if resp.status != 200:
                        continue
                    soup = BeautifulSoup(await resp.text(), 'html.parser')
                    
                    # Разные способы поиска товаров
                    candidates = soup.find_all(['div', 'article', 'a'], limit=15)
                    for item in candidates:
                        title = item.find(string=lambda t: t and len(str(t).strip()) > 15)
                        if not title:
                            continue
                        title = str(title).strip()[:90]
                        
                        price = item.find(string=lambda t: t and any(c in str(t) for c in '₽$€'))
                        price = price.strip() if price else "Цена уточняется"
                        
                        if len(title) > 20 and title not in [r.split('\n')[0] for r in results]:
                            results.append(f"{title}\n💰 {price}")
            except:
                continue

    return results[:5] if results else ["По этому запросу сейчас ничего не найдено.\nПопробуй более точный запрос (например: «айфон 15 128gb черный»)"]

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Добро пожаловать в <b>Антипереплата</b>!\n\nЗдесь ищем самые выгодные предложения.", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🔍 Поиск товара")
async def search_request(message: types.Message):
    await message.answer("Напиши название товара:\nПример: айфон 15, пуховик женский, кофемашина, power bank 20000")

@dp.message()
async def handle_search(message: types.Message):
    if len(message.text) < 3 or message.text.startswith('/'):
        return

    await message.answer("🔍 Ищу лучшие предложения...")

    results = await search_products(message.text)

    async with aiosqlite.connect('market.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
    
    is_premium = row and row[0] and datetime.fromisoformat(row[0]) > datetime.now() if row and row[0] else False

    text = f"<b>🔍 Результаты по запросу:</b> {message.text}\n\n"

    for i, item in enumerate(results[:3], 1):
        if is_premium or i == 1:
            text += f"{i}️⃣ {item}\n\n"
        else:
            text += f"{i}️⃣ |||||||||||||||||| (заблюрено)\n\n"

    if not is_premium:
        text += "🔒 Полные результаты доступны только по подписке 0.99$/мес"

    await message.answer(text, parse_mode="HTML")

# Подписка (оставляем)
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Антипереплата»",
        description="Неограниченный поиск + все цены",
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
