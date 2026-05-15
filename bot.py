from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import os
from datetime import datetime
import aiosqlite
import random

TOKEN = os.getenv("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# ===================== БАЗА ДАННЫХ =====================
async def init_db():
    async with aiosqlite.connect('horoscope.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users 
                           (user_id INTEGER PRIMARY KEY, 
                            zodiac TEXT,
                            subscribed_until TEXT)''')
        await db.commit()

main_menu = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🌟 Мой гороскоп на сегодня")],
    [KeyboardButton(text="♈ Выбрать знак зодиака")],
    [KeyboardButton(text="👤 Моя подписка")],
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
], resize_keyboard=True)

zodiac_list = {
    "♈ Овен": "Овен", "♉ Телец": "Телец", "♊ Близнецы": "Близнецы",
    "♋ Рак": "Рак", "♌ Лев": "Лев", "♍ Дева": "Дева",
    "♎ Весы": "Весы", "♏ Скорпион": "Скорпион", "♐ Стрелец": "Стрелец",
    "♑ Козерог": "Козерог", "♒ Водолей": "Водолей", "♓ Рыбы": "Рыбы"
}

# ===================== ГЕНЕРАЦИЯ ГОРОСКОПА =====================
def generate_horoscope(zodiac: str, is_premium: bool = False):
    date = datetime.now().strftime('%d.%m.%Y')
    base = f"<b>🌟 Гороскоп на {date} — {zodiac}</b>\n\n"
    
    common = [
        "Сегодня звёзды благоприятствуют новым начинаниям.",
        "Будьте внимательны к своему окружению.",
        "Финансовая сфера требует осторожности.",
        "В любви возможны приятные сюрпризы.",
        "Здоровье на высоте, но не забывайте про отдых."
    ]
    
    premium = [
        "Сегодня отличный день для важных решений и крупных покупок.",
        "Вам откроются скрытые возможности, которых не видели раньше.",
        "В личной жизни возможен серьёзный прорыв.",
        "Финансовый поток усиливается — действуйте смело."
    ]
    
    text = base
    for phrase in common:
        text += f"• {phrase}\n"
    
    if is_premium:
        text += "\n" + "\n".join([f"✨ {p}" for p in premium])
        text += "\n\n🌟 Полный персональный прогноз доступен только по подписке."
    
    return text

# ===================== ХЭНДЛЕРЫ =====================
@dp.message(Command("start"))
async def start(message: types.Message):
    await init_db()
    await message.answer(
        "👋 Добро пожаловать в <b>Твой Личный Гороскоп</b>!\n\n"
        "Каждый день — персональный прогноз от звёзд.", 
        reply_markup=main_menu, parse_mode="HTML"
    )

@dp.message(F.text == "🌟 Мой гороскоп на сегодня")
async def my_horoscope(message: types.Message):
    async with aiosqlite.connect('horoscope.db') as db:
        async with db.execute("SELECT zodiac, subscribed_until FROM users WHERE user_id = ?", 
                            (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            
            if not row or not row[0]:
                await message.answer("Сначала выбери свой знак зодиака 👇", reply_markup=main_menu)
                return
                
            zodiac = row[0]
            is_premium = row[1] and datetime.fromisoformat(row[1]) > datetime.now()
            
            horoscope = generate_horoscope(zodiac, is_premium)
            await message.answer(horoscope, parse_mode="HTML")

@dp.message(F.text == "♈ Выбрать знак зодиака")
async def choose_zodiac(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="♈ Овен", callback_data="zodiac_Овен")],
        [InlineKeyboardButton(text="♉ Телец", callback_data="zodiac_Телец")],
        [InlineKeyboardButton(text="♊ Близнецы", callback_data="zodiac_Близнецы")],
        [InlineKeyboardButton(text="♋ Рак", callback_data="zodiac_Рак")],
        [InlineKeyboardButton(text="♌ Лев", callback_data="zodiac_Лев")],
        [InlineKeyboardButton(text="♍ Дева", callback_data="zodiac_Дева")],
        [InlineKeyboardButton(text="♎ Весы", callback_data="zodiac_Весы")],
        [InlineKeyboardButton(text="♏ Скорпион", callback_data="zodiac_Скорпион")],
        [InlineKeyboardButton(text="♐ Стрелец", callback_data="zodiac_Стрелец")],
        [InlineKeyboardButton(text="♑ Козерог", callback_data="zodiac_Козерог")],
        [InlineKeyboardButton(text="♒ Водолей", callback_data="zodiac_Водолей")],
        [InlineKeyboardButton(text="♓ Рыбы", callback_data="zodiac_Рыбы")],
    ])
    await message.answer("Выбери свой знак зодиака:", reply_markup=kb)

@dp.callback_query(F.data.startswith("zodiac_"))
async def set_zodiac(callback: types.CallbackQuery):
    zodiac = callback.data.split("_")[1]
    async with aiosqlite.connect('horoscope.db') as db:
        await db.execute("INSERT OR REPLACE INTO users (user_id, zodiac) VALUES (?, ?)", 
                        (callback.from_user.id, zodiac))
        await db.commit()
    
    await callback.message.edit_text(f"✅ Твой знак зодиака: <b>{zodiac}</b>", parse_mode="HTML")
    await callback.answer()
    
    # Сразу показываем гороскоп
    horoscope = generate_horoscope(zodiac, False)
    await callback.message.answer(horoscope, parse_mode="HTML")

@dp.message(F.text == "👤 Моя подписка")
async def my_sub(message: types.Message):
    async with aiosqlite.connect('horoscope.db') as db:
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

@dp.message(F.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Твой Личный Гороскоп»",
        description="Персональные прогнозы + расширенный анализ каждый день",
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
    async with aiosqlite.connect('horoscope.db') as db:
        await db.execute("UPDATE users SET subscribed_until = ? WHERE user_id = ?", 
                        (until, message.from_user.id))
        await db.commit()
    await message.answer("🎉 Подписка активирована!\nТеперь ты получаешь полный персональный гороскоп каждый день.")

# ===================== ЗАПУСК =====================
async def main():
    await init_db()
    print("🚀 Бот «Твой Личный Гороскоп» запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
