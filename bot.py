from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os

TOKEN = os.getenv("TOKEN")   # ← берёт токен из Variables Railway

bot = Bot(token=TOKEN)
dp = Dispatcher()

kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
    [KeyboardButton(text="👤 Моя подписка")],
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "✅ Бот **Бесплатная Еда** успешно запущен!\n\n"
        "Нажми кнопку ниже:", 
        reply_markup=kb
    )

@dp.message(lambda m: m.text == "💎 Купить подписку 0.99$")
async def buy_subscription(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Ежедневные акции на доставку и продукты",
        payload="monthly_099",
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
    await message.answer("🎉 Оплата прошла успешно!\nПодписка активирована на 30 дней!")

async def main():
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
