from typing import Optional

from telegram import Message, Update, Bot, User
from telegram import MessageEntity, ParseMode
from telegram.error import BadRequest
from telegram.ext import Filters, MessageHandler, run_async

from haruka import dispatcher
from haruka.modules.disable import DisableAbleCommandHandler, DisableAbleRegexHandler
from haruka.modules.sql import afk_sql as sql
from haruka.modules.users import get_user_id

from haruka.modules.translations.strings import tld

AFK_GROUP = 7
AFK_REPLY_GROUP = 8


@run_async
def afk(bot: Bot, update: Update):
    user = update.effective_user
    chat = update.effective_chat  # type: Optional[Chat]
    args = update.effective_message.text.split(None, 1)
    if user.id == 777000:  # ignore channels
        return
    reason = args[1] if len(args) >= 2 else ""
    sql.set_afk(update.effective_user.id, reason)
    fname = update.effective_user.first_name
    update.effective_message.reply_text(tld(chat.id, f"User {fname} is now AFK!"))


@run_async
def no_longer_afk(bot: Bot, update: Update):
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]

    if user.id == 777000:  # ignore channels
        return

    if res := sql.rm_afk(user.id):
        firstname = update.effective_user.first_name
        try:
            update.effective_message.reply_text(tld(chat.id, f"User {firstname} is no longer AFK!"))
        except:
            return


@run_async
def reply_afk(bot: Bot, update: Update):
    message = update.effective_message  # type: Optional[Message]
    user = update.effective_user
    if user.id == 777000:
        return
    if message.entities and message.parse_entities([MessageEntity.TEXT_MENTION, MessageEntity.MENTION]):
        entities = message.parse_entities([MessageEntity.TEXT_MENTION, MessageEntity.MENTION])
        for ent in entities:
            if ent.type == MessageEntity.TEXT_MENTION:
                user_id = ent.user.id
                fst_name = ent.user.first_name

            elif ent.type == MessageEntity.MENTION:
                user_id = get_user_id(message.text[ent.offset:ent.offset + ent.length])
                if not user_id:
                    # Should never happen, since for a user to become AFK they must have spoken. Maybe changed username?
                    return
                try:
                    chat = bot.get_chat(user_id)
                except BadRequest:
                    print(f"Error: Could not fetch userid {user_id} for AFK module")
                    return
                fst_name = chat.first_name

            else:
                return

            check_afk(bot, update, user_id, fst_name)

    elif message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        fst_name = message.reply_to_message.from_user.first_name
        check_afk(bot, update, user_id, fst_name)


def check_afk(bot, update, user_id, fst_name):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user
    if user.id == 777000:
        return
    if sql.is_afk(user_id):
        user = sql.check_afk_status(user_id)
        res = (
            tld(
                chat.id,
                f"User {fst_name} is AFK! says its because of:\n{user.reason}",
            )
            if user.reason
            else tld(chat.id, f"User {fst_name} is AFK!")
        )
        update.effective_message.reply_text(res)


__help__ = ""
__mod_name__ = "AFK"

AFK_HANDLER = DisableAbleCommandHandler("afk", afk)
AFK_REGEX_HANDLER = DisableAbleRegexHandler("(?i)brb", afk, friendly="afk")
NO_AFK_HANDLER = MessageHandler(Filters.all & Filters.group, no_longer_afk)
AFK_REPLY_HANDLER = MessageHandler(Filters.all & Filters.group, reply_afk)

dispatcher.add_handler(AFK_HANDLER, AFK_GROUP)
dispatcher.add_handler(AFK_REGEX_HANDLER, AFK_GROUP)
dispatcher.add_handler(NO_AFK_HANDLER, AFK_GROUP)
dispatcher.add_handler(AFK_REPLY_HANDLER, AFK_REPLY_GROUP)
