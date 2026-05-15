from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncio

TOKEN = "ВСТАВЬ_СВОЙ_ТОКЕН_ЗДЕСЬ"

bot = Bot(token=TOKEN)
dp = Dispatcher()

kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="💎 Купить подписку 0.99$")],
    [KeyboardButton(text="👤 Моя подписка")],
], resize_keyboard=True)

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer("✅ Бот работает!\nНажми кнопку ниже 👇", reply_markup=kb)

@dp.message(lambda m: m.text == "💎 Купить подписку 0.99$")
async def buy(message: types.Message):
    prices = [types.LabeledPrice(label="Подписка 30 дней", amount=99)]
    await bot.send_invoice(
        message.chat.id,
        title="Подписка «Бесплатная Еда»",
        description="Ежедневные акции на еду",
        payload="sub",
        provider_token="",
        currency="XTR",
        prices=prices,
        is_subscription=True
    )

@dp.pre_checkout_query()
async def pre_checkout(query):
    await query.answer(ok=True)

@dp.message(F.successful_payment)
async def success_payment(message: types.Message):
    await message.answer("🎉 Оплата прошла успешно!\nПодписка активирована на 30 дней.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
