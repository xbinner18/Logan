import html
from typing import Optional, List
from datetime import datetime
from telegram import Message, Chat, Update, Bot, User
from telegram.ext import run_async, Filters
from haruka.modules.disable import DisableAbleCommandHandler
from haruka import dispatcher, MESSAGE_DUMP

START_TIME = datetime.now()

@run_async
def bug(bot: Bot, update: Update) -> str:
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    x = message.text[len('/bug '):]

    if chat and message.reply_to_message:
        chat_name = chat.title or chat.first or chat.username

        if chat.username and chat.type == Chat.SUPERGROUP:
            msg = f"#BUG" \
                  f" From {chat.title}" \
                  f"\nReported by {user.first_name}" \
                  f"\nReason: {x}" \
                  f"\nDate Time: {START_TIME}"
            
            link = f"\nLink: " \
                   f"http://t.me/{chat.username}/{message.message_id}"

            bot.send_message(MESSAGE_DUMP, msg + link)
            
    message.reply_text(f"Thanks {user.first_name} for point outing {x} this bug!")
                            

BUG_HANDLER = DisableAbleCommandHandler("bug", bug, filters=Filters.group)

dispatcher.add_handler(BUG_HANDLER)
