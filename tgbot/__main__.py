import os
import sys
import logging

from dotenv import load_dotenv

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from . import core, start, chat

async def on_startup() -> None:
	core.logger.info("Bot is starting...")

	bot_info = await core.bot.get_me()
	core.logger.info(f"Name: {bot_info.full_name}")
	core.logger.info(f"User: {bot_info.username}")
	core.logger.info(f"ID: {bot_info.id}")

	core.logger.info("Bot started!")

async def on_shutdown() -> None:
	core.logger.info("Bot is stopping...")

async def main() -> None:
	dp.startup.register(on_startup)
	dp.shutdown.register(on_shutdown)
	await dp.start_polling(core.bot, skip_updates=True)

if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, stream=sys.stdout)
	core.logger = logging.getLogger()

	load_dotenv()

	core.bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
	dp = Dispatcher()
	dp.include_routers(start.router, chat.router)

	try:
		asyncio.run(main())
	finally:
		core.logger.info("Bot stopped!")
