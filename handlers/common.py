# -*- coding: utf-8 -*-
"""Общие отправки для хендлеров жизни (работа, брак, дома)."""

from telegram import InlineKeyboardMarkup

from services.media import send_with_pic


def own_kb(rows):
    return InlineKeyboardMarkup(rows)


async def life_send(update, context, text, key=None, api=None, kb=None, gif=None):
    """Сообщение с картинкой (свои «раб:курьер» и т.п.), гифкой из Giphy или аниме-гифкой и кнопками."""
    return await send_with_pic(context.bot, update.effective_chat.id, text, [key] if key else [],
                               reply_to=update.effective_message.message_id, api_cat=api,
                               markup=kb, gif_query=gif)
