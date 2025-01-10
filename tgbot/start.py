from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import grpc

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import bot_backend_pb2, bot_backend_pb2_grpc

bot_backend_channel = grpc.insecure_channel("localhost:50051")
bot_backend_stub = bot_backend_pb2_grpc.BotBackendStub(bot_backend_channel)

router = Router()

class Start(StatesGroup):
	city = State()


@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
	await state.set_state(Start.city)
	await message.answer(f"Приветствую, {message.from_user.full_name}!\n\n"
		"Этот чат-бот поможет Вам найти место или мероприятие, где можно хорошо отдохнуть одному или с друзьями!\n"
		"Просто напишите сюда чем бы Вы хотели хотели заняться, а бот предложит место куда можно сходить.\n\n"
		"Также чат-бот поддерживает лайк/дизлайк систему: если не понравилось предложение, "
		"нажмите на дизлайк и будет предложено ещё одно подходящее под ваш запрос предложение.\n\n"
		"Прежде чем мы начнём, напишите город, в котором Вы живёте:",
		parse_mode='Markdown')


@router.message(Start.city)
async def city_handler(message: Message, state: FSMContext):
	message_parts = message.text.title().split()
	city = " ".join(message_parts)

	request = bot_backend_pb2.StartRequest(user_id=message.from_user.id, city=city)
	response = bot_backend_stub.Start(request)

	if response.success:
		await state.clear()
		await message.answer(f"Вы выбрали город {city}.\n"
		                     "Теперь Вы можете писать запросы, а бот будет искать подходящие "
		                     "места и мероприятия в выбранном вами городе!")
	else:
		await message.answer("К сожалению, такой город не поддерживается чат-ботом...\n"
		                     "Но не стоит расстраиваться: разработчики в скором времени добавят и его!\n"
		                     "Может, всё-таки вы имели в виду город Москва или Санкт-Петербург? :^)")

