import os
import sys
import logging

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart

import grpc
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import bot_backend_pb2, bot_backend_pb2_grpc

logger = None

bot = None
dp = Dispatcher()

channel = grpc.insecure_channel("localhost:50051")
stub = bot_backend_pb2_grpc.MessageServiceStub(channel)

@dp.message(CommandStart())
async def start_handler(message) -> None:
	await message.answer(f"Hello, {message.from_user.full_name}!")

@dp.message()
async def echo_handler(message) -> None:
	try:
		grpc_request = bot_backend_pb2.MessageRequest(user_id=str(message.from_user.id), text=message.text)
		grpc_response = stub.EchoMessage(grpc_request)

		await message.answer(grpc_response.text)
	except TypeError:
		await message.answer("Unsupported message!")

async def on_startup() -> None:
	logger.info("Bot is starting...")
	bot_info = await bot.get_me()
	logger.info(f"Name: {bot_info.full_name}")
	logger.info(f"User: {bot_info.username}")
	logger.info(f"ID: {bot_info.id}")
	logger.info("Bot started!")

async def on_shutdown() -> None:
	logger.info("Bot is stopping...")
	logger.info("Bot stopped!")

async def main() -> None:
	dp.startup.register(on_startup)
	dp.shutdown.register(on_shutdown)
	await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
	load_dotenv()
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	logger = logging.getLogger()
	bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
	asyncio.run(main())
