import os
import sys
import logging

from dotenv import load_dotenv

import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, BotCommand, FSInputFile, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender

import grpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import bot_backend_pb2, bot_backend_pb2_grpc
import bot_vectordb_pb2, bot_vectordb_pb2_grpc

###

logger = None

bot = None

router = Router()

channel = grpc.insecure_channel("localhost:50051")
stub = bot_backend_pb2_grpc.MessageServiceStub(channel)

bot_vectordb_channel = grpc.insecure_channel("localhost:50052")
vectordb_stub = bot_vectordb_pb2_grpc.BotVectorDBStub(bot_vectordb_channel)

custom_commands: dict[str, dict[str, str]] = {
	"en": {
		"subscribe": "subscribe to daily events mailing!"
	},
	"ru": {
		"subscribe": "подписаться на ежедневную рассылку!"
	}
}

###

class RateCallback(CallbackData, prefix="my"):
	rating: str


button_like = InlineKeyboardButton(text='👍', callback_data=RateCallback(rating='like').pack())
button_dislike = InlineKeyboardButton(text='👎', callback_data=RateCallback(rating='dislike').pack())
keyboard = InlineKeyboardMarkup(inline_keyboard=[[button_like, button_dislike]])

###

@router.message(CommandStart())
async def start_handler(message: Message) -> None:
	await message.answer(f"Hello, {message.from_user.full_name}!")


@router.message(Command(commands=["subscribe", "sub"]))
async def subscribe_handler(message) -> None:
	words: [str] = message.text.split()
	city: str = ' '.join(words[1:])

	user_id = str(message.from_user.id)

	grpc_request = bot_backend_pb2.SubscribeRequest(user_id=user_id, city=city)
	grpc_response = stub.Subscribe(grpc_request)

	await message.answer(grpc_response.text)


@router.message()
async def chat_handler(message: Message) -> None:
	async with ChatActionSender(bot=bot, chat_id=message.from_user.id, action="typing"):
		request = bot_vectordb_pb2.ChatRequest(text=message.text, user_id=message.from_user.id)
		response = vectordb_stub.Query(request)
		try:
			photo = FSInputFile("./"+response.image_path) if response.image_path else None
		except Exception as error:
			print(error)
			photo = None
		if len(response.text) < 1024:
			if not photo is None:
				await message.answer_photo(photo=photo,
				                           caption=response.text,
				                           parse_mode='Markdown',
				                           reply_markup=keyboard)
			else:
				await message.answer(text=response.text,
				                     parse_mode='Markdown',
				                     reply_markup=keyboard)
		else:
			if not photo is None:
				await message.answer_photo(photo)
			await message.answer(text=response.text,
			                     parse_mode='Markdown',
			                     reply_markup=keyboard)


@router.callback_query(RateCallback.filter(F.rating == 'like'))
async def like_button_handler(query: CallbackQuery):
	await bot.send_message(query.from_user.id, 'Спасибо!')


@router.callback_query(RateCallback.filter(F.rating == 'dislike'))
async def dislike_button_handler(query: CallbackQuery):
	async with ChatActionSender(bot=bot, chat_id=query.from_user.id, action="typing"):
		await query.message.answer('Хорошо, поищу ещё что-нибудь...')
		request = bot_vectordb_pb2.RateRequest(user_id=query.from_user.id)
		response = vectordb_stub.Dislike(request)
		if response.text:
			try:
				photo = FSInputFile("./"+response.image_path) if response.image_path else None
			except Exception as error:
				print(error)
				photo = None
			if len(response.text) < 1024:
				if not photo is None:
					await query.message.answer_photo(photo=photo,
					                                 caption=response.text,
					                                 parse_mode='Markdown',
					                                 reply_markup=keyboard)
				else:
					await query.message.answer(text=response.text,
					                           parse_mode='Markdown',
					                           reply_markup=keyboard)
			else:
				if not photo is None:
					await query.message.answer_photo(photo)
				await query.message.answer(text=response.text,
				                           parse_mode='Markdown',
				                           reply_markup=keyboard)
		else:
			await query.message.answer(text='К сожалению, больше предложений у меня нет...')


###

async def on_startup() -> None:
	logger.info("Bot is starting...")

	logger.info("Registering commands...")
	for code, commands in custom_commands.items():
		await bot.set_my_commands(
			[BotCommand(command=c, description=d) for c, d in commands.items()],
			language_code=code,
		)
	logger.info("Commands registered!")

	bot_info = await bot.get_me()
	logger.info(f"Name: {bot_info.full_name}")
	logger.info(f"User: {bot_info.username}")
	logger.info(f"ID: {bot_info.id}")

	logger.info("Bot started!")

async def on_shutdown() -> None:
	logger.info("Bot is stopping...")

async def main() -> None:
	dp.startup.register(on_startup)
	dp.shutdown.register(on_shutdown)
	await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	logger = logging.getLogger()

	load_dotenv()

	bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
	dp = Dispatcher()
	dp.include_routers(router)

	try:
		asyncio.run(main())
	finally:
		logger.info("Bot stopped!")
