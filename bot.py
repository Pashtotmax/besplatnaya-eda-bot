from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite
import aiohttp
from bs4 import BeautifulSoup

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== БАЗА ДАННЫХ =====================
async def init_db():
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, 
                            country TEXT DEFAULT "Россия",
                            subscribed_until TEXT,
                            last_free_count INTEGER DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS deals 
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            country TEXT,
                            text TEXT,
                            timestamp TEXT)''')
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔥 Акции на сегодня")],
    [KeyboardButton(text="🌍 Выбрать страну")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== ПАРСИНГ =====================
async def parse_new_deals():
    today = datetime.now().strftime('%Y-%m-%d')
    sources = ["https://pepper.ru/"]

    async with aiohttp.ClientSession() as session:
        for url in sources:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), 'html.parser')
                        items = soup.find_all('div', class_='thread')[:15]
                        async with aiosqlite.connect('food_bot.db') as db:
                            for item in items:
                                title = item.find('a', class_='cept-tt')
                                if title:
                                    text = title.get_text(strip=True)
                                    if len(text) > 20:
                                        await db.execute(
                                            "INSERT OR IGNORE INTO deals (country, text, timestamp) VALUES (?, ?, ?)",
                                            ("Россия", text[:220], today)
                                        )
            except:
                continue

# ===================== ОТПРАВКА АКЦИЙ =====================
async def send_deals(user_id: int, country: str, is_premium: bool):
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT text FROM deals WHERE country = ? ORDER BY id DESC LIMIT 15", 
                            (country,)) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await bot.send_message(user_id, "Пока нет акций. Бот ищет...")
        return

    text = f"<b>🔥 Актуальные акции — {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
    count = len(rows) if is_premium else 4

    for i, (deal,) in enumerate(rows[:count], 1):
        if is_premium or i % 4 == 0:
            text += f"{i}️⃣ {deal}\n"
        else:
            text += f"{i}️⃣ |||||||||||||||||| (заблюрено)\n"

    if not is_premium:
        text += "\n\n🔒 Остальные 11 акций доступны только по подписке 0.99$/мес"

    await bot.send_message(user_id, text, parse_mode="HTML")

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Добро пожаловать в <b>Бесплатная Еда</b>!\nРеальные акции каждый день.", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🔥 Акции на сегодня")
async def today_deals(message: types.Message):
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT subscribed_until, country FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            
            is_premium = row and row[0] and datetime.fromisoformat(row[0]) > datetime.now()
            country = row[1] if row else "Россия"
            
            await send_deals(message.from_user.id, country, is_premium)

@dp.message(F.text == "🌍 Выбрать страну")
async def choose_country(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_Russia")],
        [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data="country_Belarus")],
    ])
    await message.answer("Выбери страну:", reply_markup=kb)

@dp.callback_query(F.data.startswith("country_"))
async def set_country(callback: types.CallbackQuery):
    country = "Россия" if callback.data == "country_Russia" else "Беларусь"
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute("UPDATE users SET country = ? WHERE user_id = ?", 
                        (country, callback.from_user.id))
        await db.commit()
    await callback.message.edit_text(f"✅ Страна изменена на <b>{country}</b>", parse_mode="HTML")
    await send_deals(callback.from_user.id, country, False)  # сразу показываем
    await callback.answer()

# ===================== ПОДПИСКА =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Полный доступ ко всем акциям без цензуры",
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
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, subscribed_until) VALUES (?, ?)", 
                        (message.from_user.id, until))
        await db.commit()
    await message.answer("🎉 Подписка активирована!\nТеперь ты видишь **все** акции без цензуры.")

# ===================== ФОНОВЫЙ ПОИСК =====================
async def background_search():
    while True:
        await parse_new_deals()
        await asyncio.sleep(1200)  # каждые 20 минут

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    asyncio.create_task(background_search())
    print("🚀 Бот запущен! Ищет новые акции каждые 20 минут.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
