from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from datetime import datetime
import aiosqlite

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== НАСТРОЙКИ =====================
ADMIN_ID = None  # можешь поставить свой ID позже

# Каналы по странам
RUSSIA_CHANNELS = [
    -1001234567890,   # ← Замени на реальные ID каналов
    -1000987654321,
    # Добавь сюда 8-10 российских каналов про акции еды
]

BELARUS_CHANNELS = [
    -1001122334455,   # ← Замени на реальные ID белорусских каналов
    -1009988776655,
    # Добавь 5-7 каналов по Беларуси
]

# ===================== БАЗА ДАННЫХ =====================
async def init_db():
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, 
                            country TEXT DEFAULT "Россия",
                            subscribed_until TEXT,
                            last_free_posts INTEGER DEFAULT 0)''')
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔥 Акции на сегодня")],
    [KeyboardButton(text="🌍 Выбрать страну")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

# ===================== ПОДПИСКА =====================
@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Полный доступ ко всем акциям России/Беларуси",
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
    await message.answer("🎉 Подписка активирована!\nТеперь ты получаешь **все** посты из каналов.")

# ===================== ПЕРЕСЫЛКА ПОСТОВ =====================
@dp.channel_post()
async def forward_post(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None

    # Определяем страну канала
    if chat_id in RUSSIA_CHANNELS:
        country = "Россия"
    elif chat_id in BELARUS_CHANNELS:
        country = "Беларусь"
    else:
        return

    # Получаем всех пользователей этой страны
    async with aiosqlite.connect('food_bot.db') as db:
        async with db.execute("SELECT user_id, subscribed_until FROM users WHERE country = ?", 
                            (country,)) as cursor:
            async for row in cursor:
                user_id_db, until = row
                try:
                    is_premium = until and datetime.fromisoformat(until) > datetime.now()
                    
                    if is_premium:
                        await bot.forward_message(user_id_db, message.chat.id, message.message_id)
                    else:
                        # Бесплатным — каждый 5-й пост
                        async with db.execute("SELECT last_free_posts FROM users WHERE user_id = ?", 
                                            (user_id_db,)) as c:
                            last = await c.fetchone()
                            count = (last[0] if last else 0) + 1
                            if count % 5 == 0:
                                await bot.forward_message(user_id_db, message.chat.id, message.message_id)
                            await db.execute("UPDATE users SET last_free_posts = ? WHERE user_id = ?", 
                                           (count % 5, user_id_db))
                            await db.commit()
                except:
                    pass

# ===================== ОСНОВНЫЕ КОМАНДЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer("👋 Добро пожаловать в <b>Бесплатная Еда</b> — агрегатор акций!\n", 
                        reply_markup=main_menu, parse_mode="HTML")

@dp.message(F.text == "🌍 Выбрать страну")
async def choose_country(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Россия", callback_data="country_Russia")],
        [InlineKeyboardButton(text="🇧🇾 Беларусь", callback_data="country_Belarus")],
    ])
    await message.answer("Выбери страну, акции которой хочешь получать:", reply_markup=kb)

@dp.callback_query(F.data.startswith("country_"))
async def set_country(callback: types.CallbackQuery):
    country = "Россия" if callback.data == "country_Russia" else "Беларусь"
    async with aiosqlite.connect('food_bot.db') as db:
        await db.execute("UPDATE users SET country = ? WHERE user_id = ?", 
                        (country, callback.from_user.id))
        await db.commit()
    await callback.message.edit_text(f"✅ Ты теперь получаешь акции по <b>{country}</b>", parse_mode="HTML")
    await callback.answer()

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

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот-агрегатор каналов запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
