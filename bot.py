from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from datetime import datetime, timedelta
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# ===================== БАЗА ДАННЫХ =====================
async def init_db():
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, 
                            city TEXT DEFAULT "Москва",
                            subscribed_until TEXT)''')
        await db.commit()

# ===================== КЛАВИАТУРЫ =====================
main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔥 Акции на сегодня")],
    [KeyboardButton(text="🌆 Выбрать город")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== ФУНКЦИЯ АКЦИЙ =====================
async def get_deals(city: str = "Москва"):
    text = f"<b>🔥 Актуальные акции в {city} — {datetime.now().strftime('%d.%m.%Y')}</b>\n\n"
    text += """
🍔 <b>Яндекс Еда</b> — до 500₽ на первый заказ
🚀 <b>Самокат</b> — скидки 30-50% сегодня
🥑 <b>ВкусВилл</b> — акции на здоровое питание
🛒 <b>Пятёрочка / Магнит</b> — каталог недели
🔥 <b>Додо Пицца, KFC, Burger King</b> — комбо дня

💡 Промокоды работают прямо в приложениях!
    """
    return text

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 Добро пожаловать в <b>Бесплатная Еда</b>!\n\n"
        "Каждый день — самые вкусные акции и купоны на еду по всей России.",
        reply_markup=main_menu, parse_mode="HTML"
    )

# Покупка подписки
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Ежедневная рассылка акций + выбор города + архив",
        payload="monthly_sub",
        provider_token="",
        currency="XTR",
        prices=prices,
        is_subscription=True
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
    await message.answer("🎉 Оплата прошла успешно!\nПодписка активна до " + 
                        (datetime.now() + timedelta(days=30)).strftime("%d.%m.%Y"))

# Акции на сегодня
@dp.message(F.text == "🔥 Акции на сегодня")
async def today_deals(message: types.Message):
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0] and datetime.fromisoformat(row[0]) > datetime.now():
                async with db.execute("SELECT city FROM users WHERE user_id = ?", 
                                    (message.from_user.id,)) as c:
                    city_row = await c.fetchone()
                    city = city_row[0] if city_row else "Москва"
                deals = await get_deals(city)
                await message.answer(deals, parse_mode="HTML")
            else:
                await message.answer("❌ Эта функция доступна только по подписке 0.99$/мес")

# Моя подписка
@dp.message(F.text == "👤 Моя подписка")
async def my_subscription(message: types.Message):
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row and row[0]:
                until = datetime.fromisoformat(row[0])
                if until > datetime.now():
                    days_left = (until - datetime.now()).days
                    await message.answer(f"✅ Подписка активна!\nОсталось: <b>{days_left} дней</b>\nДо: {until.strftime('%d.%m.%Y')}", parse_mode="HTML")
                else:
                    await message.answer("❌ Подписка истекла.")
            else:
                await message.answer("❌ У тебя нет активной подписки.")

# Выбор города
@dp.message(F.text == "🌆 Выбрать город")
async def choose_city(message: types.Message):
    cities = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Москва", callback_data="city_Moscow")],
        [InlineKeyboardButton(text="Санкт-Петербург", callback_data="city_Spb")],
        [InlineKeyboardButton(text="Екатеринбург", callback_data="city_Ekb")],
        [InlineKeyboardButton(text="Новосибирск", callback_data="city_Nsk")],
        [InlineKeyboardButton(text="Краснодар", callback_data="city_Krd")],
    ])
    await message.answer("Выбери свой город:", reply_markup=cities)

@dp.callback_query(F.data.startswith("city_"))
async def set_city(callback: types.CallbackQuery):
    city_map = {
        "city_Moscow": "Москва",
        "city_Spb": "Санкт-Петербург",
        "city_Ekb": "Екатеринбург",
        "city_Nsk": "Новосибирск",
        "city_Krd": "Краснодар"
    }
    city = city_map.get(callback.data, "Москва")
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute("UPDATE users SET city = ? WHERE user_id = ?", (city, callback.from_user.id))
        await db.commit()
    await callback.message.edit_text(f"✅ Город изменён на <b>{city}</b>", parse_mode="HTML")
    await callback.answer()

# ==================== ЕЖЕДНЕВНАЯ РАССЫЛКА ====================
async def daily_broadcast():
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT user_id, city FROM users WHERE subscribed_until > ?", 
                            (datetime.now().isoformat(),)) as cursor:
            async for row in cursor:
                user_id, city = row
                try:
                    deals = await get_deals(city)
                    await bot.send_message(user_id, deals, parse_mode="HTML")
                except:
                    pass

# ==================== ЗАПУСК ====================
async def main():
    await init_db()
    scheduler.add_job(daily_broadcast, 'cron', hour=9, minute=0)
    scheduler.start()
    print("🚀 Бот запущен и работает 24/7")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
