from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== БАЗА ДАННЫХ =====================
async def init_db():
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, 
                            country TEXT DEFAULT "Россия",
                            subscribed_until TEXT)''')
        await db.commit()

# ===================== МЕНЮ =====================
main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔥 Акции на сегодня")],
    [KeyboardButton(text="🌍 Выбрать страну")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== АКЦИИ =====================
async def get_deals(country: str = "Россия", is_premium: bool = False):
    date = datetime.now().strftime('%d.%m.%Y')
    
    if country == "Россия":
        header = f"<b>🔥 Акции по России — {date}</b>\n\n"
        free = """
1️⃣ <b>Яндекс Еда</b> — до 400₽ на первый заказ (Москва, СПб, Екб и др.)
2️⃣ <b>Самокат</b> — скидки 30% на первый заказ
"""
        premium = """
3️⃣ <b>Додо Пицца</b> — комбо за 399₽
4️⃣ <b>Пятёрочка / Магнит</b> — акции недели по всей стране
5️⃣ <b>KFC, Burger King</b> — выгодные комбо
6️⃣ <b>ВкусВилл</b> — скидки на ЗОЖ
"""
    else:  # Беларусь
        header = f"<b>🔥 Акции по Беларуси — {date}</b>\n\n"
        free = """
1️⃣ <b>Яндекс Еда</b> — скидки в Минске, Гомеле, Бресте
2️⃣ <b>Евроопт</b> — акции недели по всей стране
"""
        premium = """
3️⃣ <b>Самокат</b> — скидки в Минске
4️⃣ <b>KFC</b> — комбо в крупных городах
5️⃣ <b>Виталюр, Гиппо</b> — свежие предложения
"""

    if is_premium:
        return header + free + premium
    else:
        return header + free + "\n\n🔒 <i>Полный список акций доступен только по подписке 0.99$/мес</i>"

# ===================== ПОДПИСКА (ИСПРАВЛЕНО) =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Ежедневные акции по России и Беларуси",
        payload="monthly_sub",
        provider_token="",
        currency="XTR",
        prices=prices
        # is_subscription=True — убрано, чтобы не было ошибки
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
    await message.answer("🎉 Подписка активирована!\nТеперь ты получаешь полный список акций каждый день.")

# ===================== ОСНОВНЫЕ ФУНКЦИИ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Добро пожаловать в <b>Бесплатная Еда</b>!\nАкции России и Беларуси.", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🔥 Акции на сегодня")
async def today_deals(message: types.Message):
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT subscribed_until, country FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            
            is_premium = row and row[0] and datetime.fromisoformat(row[0]) > datetime.now()
            country = row[1] if row else "Россия"
            
            deals = await get_deals(country, is_premium)
            await message.answer(deals, parse_mode="HTML")

@dp.message(F.text == "👤 Моя подписка")
async def my_sub(message: types.Message):
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                until = datetime.fromisoformat(row[0])
                if until > datetime.now():
                    days = (until - datetime.now()).days
                    await message.answer(f"✅ Подписка активна!\nОсталось: <b>{days} дней</b>", parse_mode="HTML")
                else:
                    await message.answer("❌ Подписка истекла.")
            else:
                await message.answer("❌ У тебя нет активной подписки.")

@dp.message(F.text == "🌍 Выбрать страну")
async def choose_country(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_Russia")],
        [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data="country_Belarus")],
    ])
    await message.answer("Выбери страну для акций:", reply_markup=kb)

@dp.callback_query(F.data.startswith("country_"))
async def set_country(callback: types.CallbackQuery):
    country = "Россия" if callback.data == "country_Russia" else "Беларусь"
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute("UPDATE users SET country = ? WHERE user_id = ?", 
                        (country, callback.from_user.id))
        await db.commit()
    await callback.message.edit_text(f"✅ Страна изменена на <b>{country}</b>", parse_mode="HTML")
    await callback.answer()

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
