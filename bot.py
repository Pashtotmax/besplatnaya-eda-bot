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
                           (user_id INTEGER PRIMARY KEY,
                            subscribed_until TEXT)''')
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔍 Новый поиск")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== УЛУЧШЕННЫЙ ПАРСЕР =====================
async def parse_product_info(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=25) as resp:
                if resp.status != 200:
                    return None, None
                
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                title = None
                price = None

                # === Wildberries (ru + by) ===
                if "wildberries" in url:
                    # Поиск в JSON внутри скриптов (самый надёжный способ)
                    scripts = soup.find_all('script')
                    for script in scripts:
                        if script.string and len(script.string) > 500:
                            # Ищем название товара
                            match = re.search(r'"name"\s*:\s*"([^"]+)"', script.string)
                            if not match:
                                match = re.search(r'"title"\s*:\s*"([^"]+)"', script.string)
                            if match:
                                candidate = match.group(1).strip()
                                if len(candidate) > 10 and "wildberries" not in candidate.lower():
                                    title = candidate
                                    break
                    
                    # Fallback
                    if not title:
                        meta = soup.find("meta", property="og:title")
                        if meta and meta.get("content"):
                            title = meta["content"].split(" — ")[0].split(" | ")[0].strip()

                    if not title:
                        h1 = soup.find("h1")
                        if h1:
                            title = h1.get_text(strip=True)

                # === Ozon ===
                elif "ozon.ru" in url:
                    title_tag = soup.find("h1")
                    if title_tag:
                        title = title_tag.get_text(strip=True)[:140]

                # Цена
                if not price:
                    price_match = re.search(r'(\d{4,})\s*[₽rub]', html)
                    if price_match:
                        price = int(price_match.group(1))

                if title:
                    title = re.sub(r'\s+', ' ', title).strip()[:140]
                
                return title, price
                
        except Exception as e:
            print(f"Parse error: {e}")
            return None, None


# ===================== ПОИСК ДЕШЁВЫХ АЛЬТЕРНАТИВ =====================
async def search_cheapest_alternatives(query: str):
    if not query or len(query) < 5:
        return []
    
    results = []
    search_url = f"https://market.yandex.ru/search?text={query.replace(' ', '+')}&how=aprice"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url, timeout=25) as resp:
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                
                cards = soup.find_all('div', {'data-auto': lambda x: x and 'offer' in str(x).lower()})[:8]
                
                for card in cards:
                    title_tag = card.find('a', {'data-auto': 'title'})
                    price_tag = card.find('span', {'data-auto': 'price-value'})
                    
                    if title_tag and price_tag:
                        title = title_tag.get_text(strip=True)[:90]
                        price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                        price = int(price_text) if price_text.isdigit() else None
                        link = "https://market.yandex.ru" + title_tag.get('href', '')
                        
                        if price and price > 100:
                            results.append({"title": title, "price": price, "link": link})
        except Exception as e:
            print(f"Yandex search error: {e}")
    
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
    
    if not title or len(title) < 10 or "wildberries" in title.lower():
        return await message.answer(
            "❌ Не удалось извлечь название товара.\n\n"
            "Попробуй другую ссылку (лучше на конкретный товар)."
        )

    await message.answer(f"✅ Нашёл товар:\n<b>{title}</b>\n\n🔎 Ищу самые низкие цены...", parse_mode="HTML")
    
    alternatives = await search_cheapest_alternatives(title)
    
    if not alternatives:
        return await message.answer("Не удалось найти варианты. Попробуй другой товар или позже.")

    text = f"💰 Лучшие цены на «<b>{title}</b>»:\n\n"
    
    for i, alt in enumerate(alternatives, 1):
        savings = ""
        if current_price and alt['price'] < current_price * 0.95:
            savings = f" (экономия ~{current_price - alt['price']} ₽)"
        
        text += f"{i}️⃣ <b>{alt['price']} ₽</b>{savings} — <a href='{alt['link']}'>{alt['title']}</a>\n\n"

    if current_price:
        text += f"\nПо твоей ссылке: <b>{current_price} ₽</b>"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# ===================== ПОДПИСКА =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="CheapFinder Premium",
        description="Безлимитные поиски + больше результатов",
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
    async with aiosqlite.connect('price_bot.db') as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, subscribed_until) VALUES (?, ?)",
                        (message.from_user.id, until))
        await db.commit()
    await message.answer("🎉 Подписка активирована! Теперь без ограничений.")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 CheapFinder Bot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
