import os
import sys
import logging

from dotenv import load_dotenv

import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, BotCommand

import grpc

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import bot_backend_pb2, bot_backend_pb2_grpc
import bot_vectordb_pb2, bot_vectordb_pb2_grpc

###

logger = None

bot = None
dp = Dispatcher()

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

@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
	await message.answer(f"Hello, {message.from_user.full_name}!")

@dp.message(Command(commands=["subscribe", "sub"]))
async def subscribe_handler(message) -> None:
	words: [str] = message.text.split()
	city: str = ' '.join(words[1:])

	user_id = str(message.from_user.id)

	grpc_request = bot_backend_pb2.SubscribeRequest(user_id=user_id, city=city)
	grpc_response = stub.Subscribe(grpc_request)

	await message.answer(grpc_response.text)

@dp.message()
async def chat_handler(message: Message) -> None:
	try:
		#grpc_request = bot_backend_pb2.MessageRequest(user_id=str(message.from_user.id), text=message.text)
		#grpc_response = stub.EchoMessage(grpc_request)

		request = bot_vectordb_pb2.ChatRequest(text=message.text)
		response = vectordb_stub.Query(request)

		await message.answer(response.text)
	except TypeError:
		await message.answer("Unsupported message!")

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
	try:
		asyncio.run(main())
	finally:
		logger.info("Bot stopped!")
