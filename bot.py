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
        [KeyboardButton(text="💎 Купить подписку 0.99$")],
    ],
    resize_keyboard=True
)

async def search_cheapest(query: str):
    url = f"https://market.yandex.ru/search?text={query.replace(' ', '+')}&how=aprice&cvredirect=3"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=30) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')
                results = []
                
                # Более широкий поиск карточек
                cards = soup.find_all(['div', 'article'], attrs={"data-auto": True})
                
                for card in cards[:10]:
                    try:
                        title_tag = card.find('a', {'data-auto': 'title'})
                        price_tag = card.find('span', {'data-auto': 'price-value'})
                        
                        if not title_tag or not price_tag:
                            continue
                            
                        title = title_tag.get_text(strip=True)[:90]
                        price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                        price = int(price_text) if price_text else None
                        
                        link = "https://market.yandex.ru" + title_tag.get('href', '')
                        
                        if price and price > 100 and title:
                            results.append({"title": title, "price": price, "link": link})
                    except:
                        continue
                        
                results.sort(key=lambda x: x["price"])
                return results[:6]
        except Exception as e:
            print("Search error:", e)
            return []


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 <b>CheapFinder</b>\n\n"
        "Напиши, что хочешь купить — найду самые низкие цены на Яндекс.Маркете.",
        reply_markup=main_menu, 
        parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: types.Message):
    await message.answer("Напиши название товара:")

@dp.message()
async def handle_message(message: types.Message):
    text = message.text.strip()
    if len(text) < 3:
        return
    
    await message.answer(f"🔍 Ищу лучшие цены на:\n<b>{text}</b>", parse_mode="HTML")
    
    results = await search_cheapest(text)
    
    if not results:
        return await message.answer("😕 К сожалению, ничего не нашёл по этому запросу.\n\nПопробуй:\n• Изменить запрос\n• Написать короче\n• Добавить бренд")

    text_msg = f"💰 Найдено {len(results)} вариантов по запросу «{text}»:\n\n"
    for i, item in enumerate(results, 1):
        text_msg += f"{i}️⃣ <b>{item['price']} ₽</b> — <a href='{item['link']}'>{item['title']}</a>\n\n"

    await message.answer(text_msg, parse_mode="HTML", disable_web_page_preview=True)


# ==================== ПОДПИСКА ====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="CheapFinder Premium",
        description="Больше результатов и приоритет",
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
    await message.answer("🎉 Подписка успешно активирована!")

async def main():
    print("🚀 CheapFinder Bot запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
