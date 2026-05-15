from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
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
                            subscribed_until TEXT,
                            max_searches INTEGER DEFAULT 5)''')  # лимит поисков в день для бесплатных
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔍 Новый поиск")],
    [KeyboardButton(text="📊 Мои поиски")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== ПАРСИНГ ТОВАРА =====================
async def parse_product_info(url: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=15) as resp:
                if resp.status != 200:
                    return None, None
                
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                title = None
                price = None
                image = None

                if "wildberries.ru" in url:
                    title_tag = soup.find("h1") or soup.find("span", {"data-link": "text__title"})
                    price_tag = soup.find("span", class_=re.compile("price__wrap|final-price"))
                    if title_tag: title = title_tag.get_text(strip=True)[:120]
                    if price_tag:
                        price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                        price = int(price_text) if price_text.isdigit() else None

                elif "ozon.ru" in url:
                    title_tag = soup.find("h1")
                    if title_tag: title = title_tag.get_text(strip=True)[:120]

                return title, price
        except:
            return None, None

# ===================== ПОИСК ДЕШЕВЫХ АЛЬТЕРНАТИВ =====================
async def search_cheapest_alternatives(query: str):
    """Ищем на Yandex.Market + прямые ссылки"""
    results = []
    search_url = f"https://market.yandex.ru/search?text={query.replace(' ', '+')}"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(search_url, timeout=20) as resp:
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                
                # Ищем карточки товаров
                items = soup.find_all('div', {'data-auto': 'offer'})[:6]  # топ-6
                
                for item in items:
                    title_tag = item.find('a', {'data-auto': 'title'})
                    price_tag = item.find('span', {'data-auto': 'price-value'})
                    link_tag = title_tag
                    
                    if title_tag and price_tag:
                        title = title_tag.get_text(strip=True)[:100]
                        price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                        price = int(price_text) if price_text else None
                        link = "https://market.yandex.ru" + title_tag.get('href', '')
                        
                        if price:
                            results.append({
                                "title": title,
                                "price": price,
                                "link": link
                            })
        except Exception as e:
            print(f"Search error: {e}")
    
    # Сортируем по цене
    results.sort(key=lambda x: x["price"])
    return results[:5]

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 Добро пожаловать в <b>CheapFinder</b>!\n\n"
        "Кидай ссылку на товар с WB или Ozon — найду где дешевле!",
        reply_markup=main_menu, 
        parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: types.Message):
    await message.answer("Отправь ссылку на товар (Wildberries или Ozon):")

@dp.message(F.text.startswith("http"))
async def handle_product_link(message: types.Message):
    url = message.text.strip()
    
    title, current_price = await parse_product_info(url)
    if not title:
        return await message.answer("❌ Не удалось прочитать товар. Попробуй другую ссылку.")

    await message.answer(f"🔍 Ищу лучшие цены на:\n<b>{title}</b>", parse_mode="HTML")
    
    alternatives = await search_cheapest_alternatives(title)
    
    if not alternatives:
        return await message.answer("Не удалось найти альтернативы. Попробуй позже.")

    text = f"✅ Найдено {len(alternatives)} вариантов дешевле/лучше:\n\n"
    
    for i, alt in enumerate(alternatives, 1):
        text += f"{i}. <b>{alt['price']} ₽</b> — <a href='{alt['link']}'>{alt['title'][:70]}...</a>\n\n"
    
    if current_price:
        text += f"\nТекущая цена в источнике: {current_price} ₽"
    
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# ===================== ПОДПИСКА (оставляем) =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="CheapFinder Premium",
        description="Безлимитные поиски + больше площадок",
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
    print("🚀 CheapFinder Bot запущен! (поиск самых дешёвых аналогов)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
