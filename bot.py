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

# ===================== УЛУЧШЕННЫЙ ПАРСЕР =====================
async def parse_product_info(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=20) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                title = None
                
                if "wildberries" in url:
                    # Самые рабочие способы 2026
                    title = (
                        soup.find("h1") or 
                        soup.find("meta", property="og:title") or 
                        soup.find("meta", {"name": "twitter:title"})
                    )
                    if title and hasattr(title, "get"):
                        title = title.get("content") or title.get_text(strip=True)
                    else:
                        title = title.get_text(strip=True) if title else None
                    
                    # Убираем мусор из заголовка
                    if title:
                        title = re.sub(r'\s*-\s*Wildberries.*$', '', title)
                        title = re.sub(r'\s*\|.*$', '', title)
                        title = title.strip()[:130]

                if not title or len(title) < 8:
                    # Запасной вариант
                    title = soup.title.string if soup.title else None
                    if title:
                        title = title.split(" — ")[0].strip()
                
                return title
                
        except Exception as e:
            print(f"Parse error: {e}")
            return None

# ===================== ПОИСК ПО НЕСКОЛЬКИМ ПЛОЩАДКАМ =====================
async def search_cheapest(query: str):
    if not query:
        return []
    
    results = []
    platforms = [
        f"https://market.yandex.ru/search?text={query.replace(' ', '+')}&how=aprice",
        f"https://www.ozon.ru/search/?text={query.replace(' ', '+')}&sorting=price_asc",
    ]
    
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for search_url in platforms:
            try:
                async with session.get(search_url, timeout=15) as resp:
                    soup = BeautifulSoup(await resp.text(), 'html.parser')
                    
                    # Yandex Market
                    if "yandex" in search_url:
                        cards = soup.find_all('div', {'data-auto': lambda x: x and 'offer' in str(x)})[:4]
                        for card in cards:
                            t = card.find('a', {'data-auto': 'title'})
                            p = card.find('span', {'data-auto': 'price-value'})
                            if t and p:
                                price_text = re.sub(r'\D', '', p.get_text())
                                price = int(price_text) if price_text.isdigit() else None
                                if price:
                                    results.append({
                                        "title": t.get_text(strip=True)[:80],
                                        "price": price,
                                        "link": "https://market.yandex.ru" + t.get('href', '')
                                    })
                    # Ozon
                    elif "ozon" in search_url:
                        # упрощённо
                        pass
            except:
                continue
    
    # Убираем дубли и сортируем
    seen = set()
    unique = []
    for r in results:
        if r["title"] not in seen:
            seen.add(r["title"])
            unique.append(r)
    
    unique.sort(key=lambda x: x["price"])
    return unique[:5]

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 <b>CheapFinder</b>\n\n"
        "Кидай ссылку на товар с Wildberries или Ozon — найду самые дешёвые варианты.",
        reply_markup=main_menu, 
        parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: types.Message):
    await message.answer("Отправь ссылку на товар:")

@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    url = message.text.strip()
    await message.answer("🔍 Извлекаю название товара...")
    
    title = await parse_product_info(url)
    
    if not title or len(title) < 10:
        return await message.answer("❌ Не получилось извлечь название товара.\n\nПопробуй другую ссылку.")

    await message.answer(f"✅ Нашёл: <b>{title}</b>\n\n🔎 Ищу самые низкие цены...", parse_mode="HTML")
    
    alternatives = await search_cheapest(title)
    
    if not alternatives:
        return await message.answer("Не удалось найти варианты. Попробуй другой товар.")

    text = f"💰 Самые дешёвые варианты на «{title}»:\n\n"
    for i, item in enumerate(alternatives, 1):
        text += f"{i}️⃣ <b>{item['price']} ₽</b> — <a href='{item['link']}'>{item['title']}</a>\n\n"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# Подписка (оставляем как было)
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="CheapFinder Premium",
        description="Безлимитные поиски",
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
    await message.answer("✅ Подписка активирована!")

async def main():
    await init_db()
    print("🚀 CheapFinder запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
