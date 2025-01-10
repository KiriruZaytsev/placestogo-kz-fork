import os
import sys

from aiogram import Router, F
from aiogram.filters.callback_data import CallbackData
from aiogram.types import Message, BotCommand, FSInputFile, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.chat_action import ChatActionSender

from . import core

import bot_backend_pb2

class RateCallback(CallbackData, prefix="my"):
	rating: str

button_like = InlineKeyboardButton(text='👍', callback_data=RateCallback(rating='like').pack())
button_dislike = InlineKeyboardButton(text='👎', callback_data=RateCallback(rating='dislike').pack())
keyboard = InlineKeyboardMarkup(inline_keyboard=[[button_like, button_dislike]])

router = Router()

@router.message()
async def chat_handler(message: Message) -> None:
	async with ChatActionSender(bot=core.bot, chat_id=message.from_user.id, action="typing"):
		request = bot_backend_pb2.ChatRequest(user_id=message.from_user.id, text=message.text)
		response = core.bot_backend_stub.Chat(request)
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
	async with ChatActionSender(bot=core.bot, chat_id=query.from_user.id, action="typing"):
		await query.message.answer('Хорошо, поищу ещё что-нибудь...')
		request = bot_backend_pb2.RateRequest(user_id=query.from_user.id)
		response = core.bot_backend_stub.Dislike(request)
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

