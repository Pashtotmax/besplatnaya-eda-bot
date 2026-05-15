from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os
import aiohttp
from bs4 import BeautifulSoup
import re

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Новый поиск")],
        [KeyboardButton(text="👤 Моя подписка")],
        [KeyboardButton(text="💎 Купить подписку 0.99$")],
    ],
    resize_keyboard=True
)

# ===================== УПРОЩЁННЫЙ ПАРСЕР =====================
async def get_product_name(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=20) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Пытаемся вытащить нормальное название
                title = None
                
                # og:title — часто содержит нормальное название
                meta = soup.find("meta", property="og:title")
                if meta and meta.get("content"):
                    full = meta["content"]
                    title = full.split(" — ")[0].split(" | ")[0].strip()
                
                # Если не получилось — берём h1
                if not title or len(title) < 15:
                    h1 = soup.find("h1")
                    if h1:
                        title = h1.get_text(strip=True)
                
                if title and ("wildberries" in title.lower() or len(title) < 10):
                    title = None
                
                return title.strip() if title else None
                
        except:
            return None


# ===================== ПОИСК НА ЯНДЕКС.МАРКЕТЕ =====================
async def search_alternatives(query: str):
    if not query:
        return []
    
    url = f"https://market.yandex.ru/search?text={query.replace(' ', '+')}&how=aprice"
    
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=25) as resp:
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                
                results = []
                cards = soup.find_all(['div', 'article'], {'data-auto': lambda x: x and 'offer' in str(x).lower()})[:8]
                
                for card in cards:
                    title_tag = card.find('a', {'data-auto': 'title'})
                    price_tag = card.find('span', {'data-auto': 'price-value'})
                    
                    if title_tag and price_tag:
                        title = title_tag.get_text(strip=True)[:80]
                        price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                        price = int(price_text) if price_text.isdigit() else None
                        
                        if price and price > 300:
                            link = "https://market.yandex.ru" + title_tag.get('href', '')
                            results.append({"title": title, "price": price, "link": link})
                
                results.sort(key=lambda x: x["price"])
                return results[:5]
        except:
            return []


# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 <b>CheapFinder</b>\n\n"
        "Отправь ссылку на товар с Wildberries или Ozon — найду где дешевле.",
        reply_markup=main_menu, 
        parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: types.Message):
    await message.answer("Отправь ссылку на товар:")

@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    await message.answer("🔍 Получаю данные о товаре...")
    
    name = await get_product_name(message.text)
    
    if not name:
        return await message.answer("❌ Не удалось получить название товара.\nПопробуй другую ссылку.")

    await message.answer(f"✅ Товар:\n<b>{name}</b>\n\n🔎 Ищу лучшие цены...", parse_mode="HTML")
    
    alternatives = await search_alternatives(name)
    
    if not alternatives:
        return await message.answer("😕 Не нашёл подходящих вариантов.\nПопробуй другой товар.")

    text = f"💰 Лучшие предложения на «{name}»:\n\n"
    for i, item in enumerate(alternatives, 1):
        text += f"{i}️⃣ <b>{item['price']} ₽</b> — <a href='{item['link']}'>{item['title']}</a>\n\n"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# Подписка
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="CheapFinder Premium",
        description="Безлимит + лучшие результаты",
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
    await message.answer("🎉 Подписка активирована! Теперь без ограничений.")

async def main():
    print("🚀 CheapFinder Bot запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
