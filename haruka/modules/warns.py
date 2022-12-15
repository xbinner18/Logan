import html
import re
from typing import Optional, List

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User, CallbackQuery
from telegram import Message, Chat, Update, Bot
from telegram.error import BadRequest
from telegram.ext import CommandHandler, run_async, DispatcherHandlerStop, MessageHandler, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html

from haruka import dispatcher, BAN_STICKER
from haruka.modules.disable import DisableAbleCommandHandler
from haruka.modules.helper_funcs.chat_status import is_user_admin, bot_admin, user_admin_no_reply, user_admin, \
    can_restrict
from haruka.modules.helper_funcs.extraction import extract_text, extract_user_and_text, extract_user
from haruka.modules.helper_funcs.filters import CustomFilters
from haruka.modules.helper_funcs.misc import split_message
from haruka.modules.helper_funcs.string_handling import split_quotes
from haruka.modules.log_channel import loggable
from haruka.modules.sql import warns_sql as sql

WARN_HANDLER_GROUP = 9


# Not async
def warn(user: User, chat: Chat, reason: str, message: Message, warner: User = None) -> str:
    if is_user_admin(chat, user.id):
        message.reply_text("I'm not going to warn an admin!")
        return ""
    if user.id == 777000:
        message.reply_text("I can't warn tg ;-;")
        return ""

    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = f"{limit} warnings, {mention_html(user.id, user.first_name)} has been kicked!"

        else:  # ban
            chat.kick_member(user.id)
            reply = f"{limit} warnings, {mention_html(user.id, user.first_name)} has been banned!"

        for warn_reason in reasons:
            reply += f"\n • {html.escape(warn_reason)}"

        keyboard = []
        log_reason = f"<b>{html.escape(chat.title)}:</b>\n#WARN_BAN\n<b>Admin:</b> {warner_tag}\n<b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n<b>Reason:</b> {reason}\n<b>Counts:</b> <code>{num_warns}/{limit}</code>"

    else:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Remove warn⚠️(admin only)",
                        callback_data=f"rm_warn({user.id})",
                    )
                ]
            ]
        )

        reply = f"{mention_html(user.id, user.first_name)} <b>has been warned!</b>\nTotal warn that this user have {num_warns}/{limit}"
        if reason:
            reply += f"\nReason for the warn:\n<code>{html.escape(reason)}</code>"

        log_reason = f"<b>{html.escape(chat.title)}:</b>\n#WARN\n<b>Admin:</b> {warner_tag}\n<b>User:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)\n<b>Reason:</b> {reason}\n<b>Counts:</b> <code>{num_warns}/{limit}</code>"

    try:
        message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(reply, reply_markup=keyboard, parse_mode=ParseMode.HTML, quote=False)
        else:
            raise
    return log_reason


@run_async
@bot_admin
@loggable
def button(bot: Bot, update: Update) -> str:
    query = update.callback_query  # type: Optional[CallbackQuery]
    user = update.effective_user  # type: Optional[User]
    if match := re.match(r"rm_warn\((.+?)\)", query.data):
        user_id = match[1]
        chat = update.effective_chat  # type: Optional[Chat]
        if not is_user_admin(chat, int(user.id)):
            query.answer(text="You are not authorized to remove this warn! Only administrators may remove warns.", show_alert=True)
            return ""
        if res := sql.remove_warn(user_id, chat.id):
            update.effective_message.edit_text(
                f"Warn removed by {mention_html(user.id, user.first_name)}.",
                parse_mode=ParseMode.HTML,
            )
            user_member = chat.get_member(user_id)
            return f"<b>{html.escape(chat.title)}:</b>\n#UNWARN\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\n<b>User:</b> {mention_html(user_member.user.id, user_member.user.first_name)} (<code>{user_member.user.id}</code>)"
        else:
            update.effective_message.edit_text(
                f"{mention_html(user.id, user.first_name)} has already has 0 warns.",
                parse_mode=ParseMode.HTML,
            )

    return ""


@run_async
@user_admin
@bot_admin
@loggable
def remove_warns(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if user_id := extract_user(message, args):
        sql.remove_warn(user_id, chat.id)
        message.reply_text("Last warn has been removed!")
        warned = chat.get_member(user_id).user
        return f"<b>{html.escape(chat.title)}:</b>\n#UNWARN\n<b>• Admin:</b> {mention_html(user.id, user.first_name)}\n<b>• User:</b> {mention_html(warned.id, warned.first_name)}\n<b>• ID:</b> <code>{warned.id}</code>"
    else:
        message.reply_text("No user has been designated!")
    return ""

@run_async
@user_admin
@can_restrict
@loggable
def warn_user(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    warner = update.effective_user  # type: Optional[User]

    user_id, reason = extract_user_and_text(message, args)

    if user_id:
        if message.reply_to_message and message.reply_to_message.from_user.id == user_id:
            return warn(message.reply_to_message.from_user, chat, reason, message.reply_to_message, warner)
        else:
            return warn(chat.get_member(user_id).user, chat, reason, message, warner)
    else:
        message.reply_text("No user was designated!")
    return ""


@run_async
@user_admin
@bot_admin
@loggable
def reset_warns(bot: Bot, update: Update, args: List[str]) -> str:
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    if user_id := extract_user(message, args):
        sql.reset_warns(user_id, chat.id)
        message.reply_text("Warnings have been reset!")
        warned = chat.get_member(user_id).user
        return f"<b>{html.escape(chat.title)}:</b>\n#RESETWARNS\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\n<b>User:</b> {mention_html(warned.id, warned.first_name)} (<code>{warned.id}</code>)"
    else:
        message.reply_text("No user has been designated!")
    return ""


@run_async
def warns(bot: Bot, update: Update, args: List[str]):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user_id = extract_user(message, args) or update.effective_user.id
    result = sql.get_warns(user_id, chat.id)

    if result and result[0] != 0:
        num_warns, reasons = result
        limit, soft_warn = sql.get_warn_setting(chat.id)

        if reasons:
            text = f"This user has {num_warns}/{limit} warnings, for the following reasons:"
            for reason in reasons:
                text += f"\n • {reason}"

            msgs = split_message(text)
            for msg in msgs:
                update.effective_message.reply_text(msg)
        else:
            update.effective_message.reply_text(
                f"User has {num_warns}/{limit} warnings, but no reasons for any of them."
            )
    else:
        update.effective_message.reply_text("This user hasn't got any warnings!")


# Dispatcher handler stop - do not async
@user_admin
def add_warn_filter(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 2:
        return

    # set trigger -> lower, so as to avoid adding duplicate filters with different cases
    keyword = extracted[0].lower()
    content = extracted[1]

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat.id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat.id, keyword, content)

    update.effective_message.reply_text("Warn handler added for '`{key}`' in *{chat}*".format(key=keyword, chat=chat.title),
                                        parse_mode=ParseMode.MARKDOWN)
    raise DispatcherHandlerStop


@user_admin
def remove_warn_filter(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(None, 1)  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 1:
        return

    to_remove = extracted[0]

    chat_filters = sql.get_chat_warn_triggers(chat.id)

    if not chat_filters:
        msg.reply_text(
            f"*No warning filters are active in {chat.title}:*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    for filt in chat_filters:
        if filt == to_remove:
            sql.remove_warn_filter(chat.id, to_remove)
            msg.reply_text("Yo, I'll stop warning people for '`{key}`' in *{chat}*.".format(key=keyword, chat=chat.title),
                           parse_mode=ParseMode.MARKDOWN)
            raise DispatcherHandlerStop

    msg.reply_text("That's not a current warning filter - run /warnlist for all active warning filters.")


@run_async
def list_warn_filters(bot: Bot, update: Update):
    chat = update.effective_chat  # type: Optional[Chat]
    all_handlers = sql.get_chat_warn_triggers(chat.id)
    CURRENT_WARNING_FILTER_STRING = f"*Active warning filters in {chat.title}:*\n"

    if not all_handlers:
        update.effective_message.reply_text(
            f"*No warning filters are active in {chat.title};*",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    filter_list = CURRENT_WARNING_FILTER_STRING
    for keyword in all_handlers:
        entry = f" • `{html.escape(keyword)}`\n"
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(filter_list, parse_mode=telegram.ParseMode.MARKDOWN)
            filter_list = entry
        else:
            filter_list += entry

    if filter_list != CURRENT_WARNING_FILTER_STRING:
        update.effective_message.reply_text(filter_list, parse_mode=telegram.ParseMode.MARKDOWN)


@run_async
@loggable
def reply_filter(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]

    chat_warn_filters = sql.get_chat_warn_triggers(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return ""

    for keyword in chat_warn_filters:
        pattern = r"( |^|[^\w])" + re.escape(keyword) + r"( |$|[^\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user = update.effective_user  # type: Optional[User]
            warn_filter = sql.get_warn_filter(chat.id, keyword)
            return warn(user, chat, warn_filter.reply, message)
    return ""


@run_async
@user_admin
@loggable
def set_warn_limit(bot: Bot, update: Update, args: List[str]) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]

    if args:
        if args[0].isdigit():
            if int(args[0]) < 3:
                msg.reply_text("The minimum warn limit is 3!")
            else:
                sql.set_warn_limit(chat.id, int(args[0]))
                msg.reply_text(f"Updated the warn limit to {args[0]}")
                return f"<b>{html.escape(chat.title)}:</b>\n#SET_WARN_LIMIT\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nSet the warn limit to <code>{args[0]}</code>"
        else:
            msg.reply_text("Give me a number as an arg!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)

        msg.reply_text(f"The current warn limit is {limit}")
    return ""


@run_async
@user_admin
def set_warn_strength(bot: Bot, update: Update, args: List[str]):
    msg = update.effective_message  # type: Optional[Message]

    chat = update.effective_chat
    if args:
        user = update.effective_user  # type: Optional[User]
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat.id, False)
            msg.reply_text("Too many warns will now result in a ban!")
            return f"<b>{html.escape(chat.title)}:</b>\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nHas enabled strong warns. Users will be banned."

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat.id, True)
            msg.reply_text("Too many warns will now result in a kick! Users will be able to join again after.")
            return f"<b>{html.escape(chat.title)}:</b>\n<b>Admin:</b> {mention_html(user.id, user.first_name)}\nHas disabled strong warns. Users will only be kicked."

        else:
            msg.reply_text("I only understand on/yes/no/off!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)
        if soft_warn:
            msg.reply_text("Warns are currently set to *kick* users when they exceed the limits.",
                           parse_mode=ParseMode.MARKDOWN)
        else:
            msg.reply_text("Warns are currently set to *ban* users when they exceed the limits.",
                           parse_mode=ParseMode.MARKDOWN)
    return ""


def __stats__():
    return f"{sql.num_warns()} overall warns, across {sql.num_warn_chats()} chats.\n{sql.num_warn_filters()} warn filters, across {sql.num_warn_filter_chats()} chats."


def __import_data__(chat_id, data):
    for user_id, count in data.get('warns', {}).items():
        for _ in range(int(count)):
            sql.warn_user(user_id, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn = sql.get_warn_setting(chat_id)
    return f'This chat has `{num_warn_filters}` warn filters. It takes `{limit}` warns before the user gets *{"kicked" if soft_warn else "banned"}*.'


__help__ = """
 - /warns <userhandle>: get a user's number, and reason, of warnings.
 - /warnlist: list of all current warning filters

*Admin only:*
 - /warn <userhandle>: warn a user. After 3 warns, the user will be banned from the group. Can also be used as a reply.
 - /resetwarn <userhandle>: reset the warnings for a user. Can also be used as a reply.
 - /addwarn <keyword> <reply message>: set a warning filter on a certain keyword. If you want your keyword to \
be a sentence, encompass it with quotes, as such: `/addwarn "very angry" This is an angry user`. 
 - /nowarn <keyword>: stop a warning filter
 - /warnlimit <num>: set the warning limit
 - /strongwarn <on/yes/off/no>: If set to on, exceeding the warn limit will result in a ban. Else, will just kick.
 - /rmwarn <userhandle>: removes latest warn for a user. It also can be used as reply.
 - /unwarn <userhandle>: same as /rmwarn
"""

__mod_name__ = "Warnings"

WARN_HANDLER = DisableAbleCommandHandler("warn", warn_user, pass_args=True, filters=Filters.group, admin_ok=True)
RESET_WARN_HANDLER = DisableAbleCommandHandler(["resetwarn", "resetwarns"], reset_warns, pass_args=True, filters=Filters.group)
CALLBACK_QUERY_HANDLER = CallbackQueryHandler(button, pattern=r"rm_warn")
MYWARNS_HANDLER = DisableAbleCommandHandler("warns", warns, pass_args=True, filters=Filters.group, admin_ok=True)
ADD_WARN_HANDLER = DisableAbleCommandHandler("addwarn", add_warn_filter, filters=Filters.group, admin_ok=True)
RM_WARN_HANDLER = DisableAbleCommandHandler(["nowarn", "stopwarn"], remove_warn_filter, filters=Filters.group, admin_ok=True)
LIST_WARN_HANDLER = DisableAbleCommandHandler(["warnlist", "warnfilters"], list_warn_filters, filters=Filters.group, admin_ok=True)
WARN_FILTER_HANDLER = MessageHandler(CustomFilters.has_text & Filters.group, reply_filter)
WARN_LIMIT_HANDLER = DisableAbleCommandHandler("warnlimit", set_warn_limit, pass_args=True, filters=Filters.group, admin_ok=True)
WARN_STRENGTH_HANDLER = CommandHandler("strongwarn", set_warn_strength, pass_args=True, filters=Filters.group)
REMOVE_WARNS_HANDLER = CommandHandler(["rmwarn", "unwarn"], remove_warns, pass_args=True, filters=Filters.group)

dispatcher.add_handler(WARN_HANDLER)
dispatcher.add_handler(CALLBACK_QUERY_HANDLER)
dispatcher.add_handler(RESET_WARN_HANDLER)
dispatcher.add_handler(MYWARNS_HANDLER)
dispatcher.add_handler(ADD_WARN_HANDLER)
dispatcher.add_handler(RM_WARN_HANDLER)
dispatcher.add_handler(LIST_WARN_HANDLER)
dispatcher.add_handler(WARN_LIMIT_HANDLER)
dispatcher.add_handler(WARN_STRENGTH_HANDLER)
dispatcher.add_handler(WARN_FILTER_HANDLER, WARN_HANDLER_GROUP)
dispatcher.add_handler(REMOVE_WARNS_HANDLER)
