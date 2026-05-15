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
    url = f"https://market.yandex.ru/search?text={query.replace(' ', '+')}&how=aprice"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(url, timeout=25) as resp:
                soup = BeautifulSoup(await resp.text(), 'html.parser')
                results = []
                
                for card in soup.find_all('div', {'data-auto': lambda x: x and 'offer' in str(x).lower()})[:7]:
                    try:
                        title_tag = card.find('a', {'data-auto': 'title'})
                        price_tag = card.find('span', {'data-auto': 'price-value'})
                        if title_tag and price_tag:
                            title = title_tag.get_text(strip=True)[:85]
                            price_text = re.sub(r'\D', '', price_tag.get_text(strip=True))
                            price = int(price_text)
                            link = "https://market.yandex.ru" + title_tag.get('href', '')
                            if price > 300:
                                results.append({"title": title, "price": price, "link": link})
                    except:
                        continue
                results.sort(key=lambda x: x["price"])
                return results[:6]
        except:
            return []


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 <b>CheapFinder</b>\n\n"
        "Напиши, что хочешь купить — найду самые низкие цены.",
        reply_markup=main_menu, 
        parse_mode="HTML"
    )

@dp.message(F.text == "🔍 Новый поиск")
async def new_search(message: types.Message):
    await message.answer("Напиши название товара:\nПример: красное платье zara, наушники airpods, кроссовки nike")

@dp.message()
async def handle_message(message: types.Message):
    if len(message.text) < 3:
        return
    
    await message.answer(f"🔍 Ищу лучшие цены на:\n<b>{message.text}</b>", parse_mode="HTML")
    
    results = await search_cheapest(message.text)
    
    if not results:
        return await message.answer("😕 Ничего не нашёл. Попробуй изменить запрос.")

    text = f"💰 Лучшие предложения по запросу «{message.text}»:\n\n"
    for i, item in enumerate(results, 1):
        text += f"{i}️⃣ <b>{item['price']} ₽</b> — <a href='{item['link']}'>{item['title']}</a>\n\n"

    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# Подписка
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="CheapFinder Premium",
        description="Больше результатов в поиске",
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
    await message.answer("🎉 Подписка активирована!")

async def main():
    print("🚀 CheapFinder Bot запущен — поиск по названию")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
