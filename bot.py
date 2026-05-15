from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite
import aiohttp
from bs4 import BeautifulSoup
import re

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== БАЗА ДАННЫХ =====================
async def init_db():
    async with aiosqlite.connect('price_bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users
                           (user_id INTEGER PRIMARY KEY, subscribed_until TEXT)''')
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔍 Новый поиск")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== САМЫЙ СИЛЬНЫЙ ПАРСЕР =====================
async def parse_product_info(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                if resp.status != 200:
                    return None, None
                
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                title = None

                # === Максимально агрессивный поиск названия ===
                if "wildberries" in url:
                    # 1. JSON в script (самый точный)
                    for script in soup.find_all('script'):
                        if not script.string or len(script.string) < 300:
                            continue
                        content = script.string
                        
                        # Основные варианты ключей
                        for pattern in [
                            r'"name"\s*:\s*"([^"]+)"',
                            r'"title"\s*:\s*"([^"]+)"',
                            r'"productName"\s*:\s*"([^"]+)"',
                            r'"shortName"\s*:\s*"([^"]+)"'
                        ]:
                            match = re.search(pattern, content)
                            if match:
                                candidate = match.group(1).strip()
                                if len(candidate) > 15 and not any(x in candidate.lower() for x in ["wildberries", "интернет-магазин", "скидки"]):
                                    title = candidate
                                    break
                        if title:
                            break

                    # 2. og:title
                    if not title:
                        meta = soup.find("meta", property="og:title")
                        if meta and meta.get("content"):
                            title = meta["content"].split(" — ")[0].split(" | ")[0].strip()

                    # 3. h1
                    if not title or len(title) < 20:
                        h1 = soup.find("h1")
                        if h1:
                            title = h1.get_text(strip=True)

                # Ozon
                elif "ozon.ru" in url:
                    h1 = soup.find("h1")
                    if h1:
                        title = h1.get_text(strip=True)

                if title:
                    title = re.sub(r'\s+', ' ', title).strip()[:160]
                
                # Цена (запасной)
                price = None
                price_match = re.search(r'(\d{4,6})\s*[₽]', html)
                if price_match:
                    price = int(price_match.group(1))
                
                return title, price
                
        except Exception as e:
            print(f"Parse error: {e}")
            return None, None


# ===================== ПОИСК АЛЬТЕРНАТИВ =====================
async def search_cheapest_alternatives(query: str):
    if not query or len(query) < 10:
        return []
    
    results = []
    search_url = f"https://market.yandex.ru/search?text={query.replace(' ', '+')}&how=aprice"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url, timeout=25) as resp:
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                cards = soup.find_all('div', {'data-auto': lambda x: x and 'offer' in str(x).lower()})[:7]
                
                for card in cards:
                    title_tag = card.find('a', {'data-auto': 'title'})
                    price_tag = card.find('span', {'data-auto': 'price-value'})
                    if title_tag and price_tag:
                        title = title_tag.get_text(strip=True)[:85]
                        price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                        price = int(price_text) if price_text.isdigit() else None
                        link = "https://market.yandex.ru" + title_tag.get('href', '')
                        if price and price > 200:
                            results.append({"title": title, "price": price, "link": link})
        except:
            pass
    
    results.sort(key=lambda x: x["price"])
    return results[:6]


# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 Добро пожаловать в <b>CheapFinder</b>!\n\n"
        "Отправь ссылку на товар с Wildberries или Ozon — найду где дешевле.",
        reply_markup=main_menu, 
        parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: types.Message):
    await message.answer("Отправь ссылку на товар:")

@dp.message(F.text.startswith("http"))
async def handle_product_link(message: types.Message):
    url = message.text.strip()
    await message.answer("🔍 Извлекаю название товара...")
    
    title, current_price = await parse_product_info(url)
    
    if not title or len(title) < 15 or "wildberries" in title.lower():
        return await message.answer(
            "❌ Не удалось извлечь название товара.\n\n"
            "Попробуй другую ссылку на **конкретный товар**."
        )

    await message.answer(f"✅ Нашёл:\n<b>{title}</b>\n\n🔎 Ищу лучшие цены...", parse_mode="HTML")
    
    alternatives = await search_cheapest_alternatives(title)
    
    if not alternatives:
        return await message.answer("Не удалось найти альтернативы. Попробуй другой товар.")

    text = f"💰 Лучшие цены на «<b>{title}</b>»:\n\n"
    
    for i, alt in enumerate(alternatives, 1):
        text += f"{i}️⃣ <b>{alt['price']} ₽</b> — <a href='{alt['link']}'>{alt['title']}</a>\n\n"

    if current_price:
        text += f"\nПо
