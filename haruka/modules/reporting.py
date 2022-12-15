import html
from typing import Optional, List
import re
from telegram import Message, Chat, Update, Bot, User, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Unauthorized
from telegram.ext import CommandHandler, RegexHandler, run_async, Filters, CallbackQueryHandler
from telegram.utils.helpers import mention_html

from haruka import dispatcher, LOGGER
from haruka.modules.helper_funcs.chat_status import user_not_admin, user_admin
from haruka.modules.log_channel import loggable
from haruka.modules.sql import reporting_sql as sql

from haruka.modules.translations.strings import tld

REPORT_GROUP = 5


@run_async
@user_admin
def report_setting(bot: Bot, update: Update, args: List[str]):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    if chat.type == chat.PRIVATE:
        if args:
            if args[0] in ("yes", "on"):
                sql.set_user_setting(chat.id, True)
                msg.reply_text("Turned on reporting! You'll be notified whenever anyone reports something.")

            elif args[0] in ("no", "off"):
                sql.set_user_setting(chat.id, False)
                msg.reply_text("Turned off reporting! You wont get any reports.")
        else:
            msg.reply_text(
                f"Your current report preference is: `{sql.user_should_report(chat.id)}`",
                parse_mode=ParseMode.MARKDOWN,
            )

    elif args:
        if args[0] in ("yes", "on"):
            sql.set_chat_setting(chat.id, True)
            msg.reply_text("Turned on reporting! Admins who have turned on reports will be notified when /report "
                           "or @admin are called.")

        elif args[0] in ("no", "off"):
            sql.set_chat_setting(chat.id, False)
            msg.reply_text("Turned off reporting! No admins will be notified on /report or @admin.")
    else:
        msg.reply_text(
            f"This chat's current setting is: `{sql.chat_should_report(chat.id)}`",
            parse_mode=ParseMode.MARKDOWN,
        )


@run_async
@user_not_admin
@loggable
def report(bot: Bot, update: Update) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]

    message = update.effective_message
    if chat and message.reply_to_message and sql.chat_should_report(chat.id):
        reported_user = message.reply_to_message.from_user  # type: Optional[User]
        chat_name = chat.title or chat.first or chat.username
        admin_list = chat.get_administrators()

        #if reported_user == "483808054":
        #    continue
       # 
        #if user.id == "435606081":
        #    continue

        if chat.username and chat.type == Chat.SUPERGROUP:
            msg = f"<b>{html.escape(chat.title)}:</b>\n<b>Reported user:</b> {mention_html(reported_user.id, reported_user.first_name)} (<code>{reported_user.id}</code>)\n<b>Reported by:</b> {mention_html(user.id, user.first_name)} (<code>{user.id}</code>)"
            link = f'\n<b>Link:</b> <a href=\"http://telegram.me/{chat.username}/{message.message_id}\">click here</a>'

            keyboard = [
                [
                    InlineKeyboardButton(
                        u"➡ Message",
                        url=f"https://t.me/{chat.username}/{str(message.reply_to_message.message_id)}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        u"⚠ Kick",
                        callback_data=f"report_{chat.id}=kick={reported_user.id}={reported_user.first_name}",
                    ),
                    InlineKeyboardButton(
                        u"⛔️ Ban",
                        callback_data=f"report_{chat.id}=banned={reported_user.id}={reported_user.first_name}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        u"❎ Delete Message",
                        callback_data=f"report_{chat.id}=delete={reported_user.id}={message.reply_to_message.message_id}",
                    )
                ],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

        else:
            msg = f'{mention_html(user.id, user.first_name)} is calling for admins in \"{html.escape(chat_name)}\"!'
            link = ""
        should_forward = True
        all_admins = []
        for admin in admin_list:
            if admin.user.is_bot:  # can't message bots
                continue

            if sql.user_should_report(admin.user.id):
                all_admins.append("<a href='tg://user?id={}'>⁣</a>".format(admin.user.id))
                try:
                    if chat.type != Chat.SUPERGROUP:
                        bot.send_message(admin.user.id, msg + link, parse_mode=ParseMode.HTML)

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if len(message.text.split()) > 1:  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                    if not chat.username:
                        bot.send_message(admin.user.id, msg + link, parse_mode=ParseMode.HTML)

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if len(message.text.split()) > 1:  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                    if chat.username and chat.type == Chat.SUPERGROUP:
                        bot.send_message(admin.user.id, msg + link, parse_mode=ParseMode.HTML, reply_markup=reply_markup)

                        if should_forward:
                            message.reply_to_message.forward(admin.user.id)

                            if len(message.text.split()) > 1:  # If user is giving a reason, send his message too
                                message.forward(admin.user.id)

                except Unauthorized:
                    pass
                except BadRequest as excp:  # TODO: cleanup exceptions
                    LOGGER.exception("Exception while reporting user")

        bot.send_message(chat.id, tld(update.effective_message, "📢 {} <b>has been reported to the chat admins!</b>{}").format(
                                            mention_html(reported_user.id, reported_user.first_name),
                                            "".join(all_admins)), parse_mode=ParseMode.HTML, reply_to_message_id=message.reply_to_message.message_id)
        return msg

    return ""


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(bot, update, chat, chatP, user):
    return f"This chat is setup to send user reports to admins, via /report and @admin: `{sql.chat_should_report(chat.id)}`"


def __user_settings__(bot, update, user):
    if sql.user_should_report(user.id) == True:
        text = "You will receive reports from chats you're admin."
        keyboard = [[InlineKeyboardButton(text="Disable reporting", callback_data="panel_reporting_U_disable")]]
    else:
        text = "You will *not* receive reports from chats you're admin."
        keyboard = [[InlineKeyboardButton(text="Enable reporting", callback_data="panel_reporting_U_enable")]]

    return text, keyboard

    
def control_panel_user(bot, update):
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat
    query = update.callback_query
    enable = re.match(r"panel_reporting_U_enable", query.data)
    disable = re.match(r"panel_reporting_U_disable", query.data)

    query.message.delete()

    if enable:
        sql.set_user_setting(chat.id, True)
        text = "Enabled reporting in your pm!"
    else:
        sql.set_user_setting(chat.id, False)
        text = "Disabled reporting in your pm!"

    keyboard = [[InlineKeyboardButton(text="⬅️ Back", callback_data="cntrl_panel_U(1)")]]

    update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


def buttons(bot: Bot, update):
    query = update.callback_query
    splitter = query.data.replace("report_", "").split("=")
    chat = update.effective_chat
    if splitter[1] == "kick":
        try:
            bot.kickChatMember(splitter[0], splitter[2])
            bot.unbanChatMember(splitter[0], splitter[2])
            query.answer("✅ Succesfully kicked")
            return ""
        except Exception as err:
            query.answer("❎ Failed to kick")
            bot.sendMessage(
                text=f"Error: {err}",
                chat_id=query.message.chat_id,
                parse_mode=ParseMode.HTML,
            )
    elif splitter[1] == "banned":
        try:
            bot.kickChatMember(splitter[0], splitter[2])
            query.answer("✅  Succesfully Banned")
            return ""
        except Exception as err:
            bot.sendMessage(
                text=f"Error: {err}",
                chat_id=query.message.chat_id,
                parse_mode=ParseMode.HTML,
            )
            query.answer("❎ Failed to ban")
    elif splitter[1] == "delete":
        try:
            bot.deleteMessage(splitter[0], splitter[3])
            query.answer("✅ Message Deleted")
            return ""
        except Exception as err:
            bot.sendMessage(
                text=f"Error: {err}",
                chat_id=query.message.chat_id,
                parse_mode=ParseMode.HTML,
            )
            query.answer("❎ Failed to delete message!")


__mod_name__ = "Reporting"

__help__ = """
 - /report <reason>: reply to a message to report it to admins.
 - @admin: reply to a message to report it to admins.
NOTE: neither of these will get triggered if used by admins

*Admin only:*
 - /reports <on/off>: change report setting, or view current status.
   - If done in pm, toggles your status.
   - If in chat, toggles that chat's status.
"""

REPORT_HANDLER = CommandHandler("report", report, filters=Filters.group)
SETTING_HANDLER = CommandHandler("reports", report_setting, pass_args=True)
ADMIN_REPORT_HANDLER = RegexHandler("(?i)@admin(s)?", report)

cntrl_panel_user_callback_handler = CallbackQueryHandler(control_panel_user, pattern=r"panel_reporting_U")
report_button_user_handler = CallbackQueryHandler(buttons, pattern=r"report_")
dispatcher.add_handler(cntrl_panel_user_callback_handler)
dispatcher.add_handler(report_button_user_handler)

dispatcher.add_handler(REPORT_HANDLER, REPORT_GROUP)
dispatcher.add_handler(ADMIN_REPORT_HANDLER, REPORT_GROUP)
dispatcher.add_handler(SETTING_HANDLER)
