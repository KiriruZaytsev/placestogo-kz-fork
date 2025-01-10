import os
import sys

from aiogram import Router, F
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, BotCommand, FSInputFile, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender

import grpc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../api/generated')))
import bot_vectordb_pb2, bot_vectordb_pb2_grpc

from . import core

bot_vectordb_channel = grpc.insecure_channel("localhost:50052")
vectordb_stub = bot_vectordb_pb2_grpc.BotVectorDBStub(bot_vectordb_channel)

class RateCallback(CallbackData, prefix="my"):
	rating: str

button_like = InlineKeyboardButton(text='👍', callback_data=RateCallback(rating='like').pack())
button_dislike = InlineKeyboardButton(text='👎', callback_data=RateCallback(rating='dislike').pack())
keyboard = InlineKeyboardMarkup(inline_keyboard=[[button_like, button_dislike]])

router = Router()

@router.message()
async def chat_handler(message: Message) -> None:
	async with ChatActionSender(bot=core.bot, chat_id=message.from_user.id, action="typing"):
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
	await core.bot.send_message(query.from_user.id, 'Спасибо!')


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

