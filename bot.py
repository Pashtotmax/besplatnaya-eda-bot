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
    # Улучшенный поиск — несколько попыток
    queries = [
        query,
        query.replace("детский", "").replace("детская", "").strip(),
        query.replace("флисовый", "").replace("флис", "").strip(),
    ]
    
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        for q in queries:
            if not q or len(q) < 3:
                continue
                
            try:
                url = f"https://market.yandex.ru/search?text={q.replace(' ', '+')}&how=aprice&cvredirect=3"
                async with session.get(url, timeout=20) as resp:
                    soup = BeautifulSoup(await resp.text(), 'html.parser')
                    
                    cards = soup.find_all('div', {'data-auto': True})
                    
                    for card in cards[:8]:
                        try:
                            title_tag = card.find('a', {'data-auto': 'title'})
                            price_tag = card.find('span', {'data-auto': 'price-value'})
                            
                            if title_tag and price_tag:
                                title = title_tag.get_text(strip=True)[:95]
                                price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                                price = int(price_text) if price_text.isdigit() else None
                                
                                if price and price > 150:
                                    link = "https://market.yandex.ru" + title_tag.get('href', '')
                                    results.append({"title": title, "price": price, "link": link})
                        except:
                            continue
            except:
                continue
                
    # Убираем дубликаты
    seen = set()
    unique_results = []
    for item in results:
        if item['title'] not in seen:
            seen.add(item['title'])
            unique_results.append(item)
    
    unique_results.sort(key=lambda x: x["price"])
    return unique_results[:7]


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 <b>CheapFinder</b>\n\n"
        "Напиши название товара — найду самые низкие цены на Яндекс.Маркете.",
        reply_markup=main_menu, 
        parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: types.Message):
    await message.answer("Напиши название товара (можно с брендом):")

@dp.message()
async def handle_message(message: types.Message):
    text = message.text.strip()
    if len(text) < 3 or text in ["💎 Купить подписку 0.99$", "/start"]:
        return

    await message.answer(f"🔍 Ищу лучшие цены на:\n<b>{text}</b>", parse_mode="HTML")
    
    results = await search_cheapest(text)
    
    if not results:
        return await message.answer(
            "😕 Ничего не нашёл.\n\n"
            "Советы:\n"
            "• Добавь бренд (Zara, Nike, Ozon и т.д.)\n"
            "• Напиши короче\n"
            "• Убери слова «детский», «мужской»"
        )

    response = f"💰 Лучшие цены на «{text}»:\n\n"
    for i, item in enumerate(results, 1):
        response += f"{i}️⃣ <b>{item['price']} ₽</b> — <a href='{item['link']}'>{item['title']}</a>\n\n"

    await message.answer(response, parse_mode="HTML", disable_web_page_preview=True)


# Подписка
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="CheapFinder Premium",
        description="Больше результатов + приоритет",
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
    await message.answer("🎉 Подписка активирована! Теперь ищи без ограничений.")

async def main():
    print("🚀 CheapFinder Bot v2 (улучшенный поиск)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
