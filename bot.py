from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
from datetime import datetime, timedelta
import aiosqlite

TOKEN = "ТВОЙ_ТОКЕН_ЗДЕСЬ"   # ← убедись, что токен правильный

bot = Bot(token=TOKEN)
dp = Dispatcher()

kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
    [KeyboardButton(text="👤 Моя подписка")],
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать в <b>Бесплатная Еда</b>!\n\n"
        "Подписка 0.99$ в месяц — ежедневные акции.", 
        reply_markup=kb, 
        parse_mode="HTML"
    )

@dp.message(lambda m: m.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка на 30 дней", amount=99)]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Ежедневные лучшие акции на еду по России",
        payload="monthly_sub_99",
        provider_token="",           # важно оставить пустым
        currency="XTR",              # Telegram Stars
        prices=prices,
        is_subscription=True
    )

@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    await message.answer("✅ Оплата прошла успешно!\nПодписка активирована на 30 дней!")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
