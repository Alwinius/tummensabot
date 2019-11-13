#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @author Alwin Ebermann (alwin@alwin.net.au)
# @author Markus Pielmeier

import logging
from typing import List

from telegram import Update, Chat, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, Message, Bot
from telegram.error import ChatMigrated, TimedOut, Unauthorized, BadRequest
from telegram.ext import CallbackContext, Updater, CommandHandler, CallbackQueryHandler, Filters, MessageHandler

from .meals import MenuManager, MENSEN
from .db import User, Session
from . import config

logging.basicConfig(level=logging.DEBUG)

def make_button_list():
    arrangement = [(421, 411), (422, 412), (423, 432)]
    rows = []
    for row in arrangement:
        row_btns = []
        for mensa_id in row:
            name = MENSEN[mensa_id]
            row_btns.append(InlineKeyboardButton(name, callback_data=f"{mensa_id}${name}"))
        rows.append(row_btns)
    return rows


button_list = make_button_list()
default_reply_markup = InlineKeyboardMarkup(button_list)

menu_manager = MenuManager()


def send(bot, chat_id, message, reply_markup=default_reply_markup, message_id=None):
    try:
        if message_id is None or message_id == 0:
            rep = bot.sendMessage(chat_id=chat_id, text=message, reply_markup=reply_markup,
                                  parse_mode=ParseMode.MARKDOWN)
            session = Session()
            user = session.query(User).filter(User.id == chat_id).first()
            user.message_id = rep.message_id
            session.commit()
            session.close()
            return True
        else:
            rep = bot.editMessageText(chat_id=chat_id, text=message, message_id=message_id, reply_markup=reply_markup,
                                      parse_mode=ParseMode.MARKDOWN)
            session = Session()
            user = session.query(User).filter(User.id == chat_id).first()
            user.message_id = rep.message_id
            session.commit()
            session.close()
            return True
    except (Unauthorized, BadRequest) as e:
        session = Session()
        user = session.query(User).filter(User.id == chat_id).first()
        user.notifications = -1
        send_developer_message(bot, f"Error while sending message to {user.first_name} (#{chat_id})\n\n{e}")
        session.commit()
        session.close()
        return True
    except TimedOut:
        import time
        time.sleep(50)  # delays for 5 seconds
        return send(bot, chat_id, message_id, message, reply_markup)
    except ChatMigrated as e:
        session = Session()
        user = session.query(User).filter(User.id == chat_id).first()
        user.id = e.new_chat_id
        session.commit()
        session.close()
        return True


def send_developer_message(bot: Bot, msg):
    fallback = config['AdminId']
    chat_ids = config.get('DeveloperIds', fallback).split(",")

    for chat_id in chat_ids:
        bot.send_message(text=msg, chat_id=chat_id)


def checkuser(chat: Chat, sel=0):
    session = Session()
    entry = session.query(User).filter(User.id == chat.id).first()
    if not entry:
        # create entry
        new_user = User(id=chat.id, first_name=chat.first_name, last_name=chat.last_name, username=chat.username,
                        title=chat.title, notifications=0, current_selection="0", counter=0)
        session.add(new_user)
        session.commit()
        session.close()
        return [0, 0]
    else:
        entry.current_selection = sel if sel != 0 else entry.current_selection
        presel = entry.current_selection
        entry.counter += 1
        noti = entry.notifications
        session.commit()
        session.close()
        return [noti, presel]


def change_notifications(chat: Chat, mensa_id: int, enabled: bool):
    session = Session()
    user = session.query(User).filter(User.id == chat.id).first()
    user.notifications = mensa_id if enabled else 0
    session.commit()
    session.close()


# Handlers
def start(update: Update, context: CallbackContext):
    checkuser(update.message.chat)
    msg = "Bitte über das Menü eine Mensa wählen. Informationen über diesen Bot gibt's hier /about."
    send(context.bot, update.message.chat_id, msg)


def about(update: Update, context: CallbackContext):
    checkuser(update.message.chat)
    msg = ("Dieser Bot wurde erstellt von @Alwinius, und wird weiterentwickelt von @markuspi.\n"
           "Der Quellcode ist unter https://github.com/Alwinius/tummensabot verfügbar.\n"
           "Weitere interessante Bots: \n - "
           "@tummoodlebot\n - @mydealz\_bot\n - @tumroomsbot")
    print(msg)
    send(context.bot, update.message.chat_id, msg)


def inline_callback(update: Update, context: CallbackContext):
    message: Message = update.callback_query.message
    args: List[str] = update.callback_query.data.split("$")

    if int(args[0]) > 400:
        # show mealplan
        mensa_id, mensa_name = args
        noti, presel = checkuser(message.chat, sel=mensa_id)

        if int(noti) <= 0 or int(noti) != int(mensa_id):
            noti_btn = InlineKeyboardButton("Auto-Update aktivieren", callback_data="5$1")
        else:
            noti_btn = InlineKeyboardButton("Auto-Update deaktivieren", callback_data="5$0")

        msg = menu_manager.get_menu(int(mensa_id)).get_meals_message()
        reply_markup = InlineKeyboardMarkup([[noti_btn]] + button_list)
        send(context.bot, message.chat_id, msg, reply_markup=reply_markup, message_id=message.message_id)
    elif int(args[0]) == 5 and len(args) > 1:
        # manage notifications
        noti, presel = checkuser(message.chat)
        enabled = args[1] == "1"
        change_notifications(message.chat, presel, enabled)

        if enabled:
            noti_btn = InlineKeyboardButton("Auto-Update deaktivieren", callback_data="5$0")
            msg = "Auto-Update aktiviert für Mensa " + MENSEN[int(presel)]
        else:
            noti_btn = InlineKeyboardButton("Auto-Update aktivieren", callback_data="5$1")
            msg = "Auto-Update deaktiviert"

        reply_markup = InlineKeyboardMarkup([[noti_btn]] + button_list)
        send(context.bot, message.chat_id, msg, reply_markup=reply_markup, message_id=message.message_id)
    else:
        logging.error("unknown inline command")
        msg = "Kommando nicht erkannt"
        send(context.bot, message.chat_id, msg)
        dev_msg = f"Inlinekommando nicht erkannt.\n\nData: {update.callback_query.data}\nUser:{message.chat}"
        send_developer_message(context.bot, dev_msg)


def send_notifications():
    bot = Bot(token=config['BotToken'])

    plans = {}
    for mensa_id, mensa_name in MENSEN.items():
        print(f"Getting plan for {mensa_name} (#{mensa_id})")
        plans[mensa_id] = menu_manager.get_menu(mensa_id)

    noti_btn = InlineKeyboardButton("Auto-Update deaktivieren", callback_data="5$0")
    reply_markup = InlineKeyboardMarkup([[noti_btn]] + button_list)

    session = Session()
    users = session.query(User).filter(User.notifications > 0)
    for user in users:
        user.counter += 1
        session.commit()
        try:
            print("Sending plan to", user.first_name)
            send(bot, user.id, plans[int(user.notifications)].get_meals_message(), reply_markup=reply_markup, message_id=user.message_id)
        except TypeError:
            logging.exception(f"Caught TypeError while processing user {user.first_name}")

    session.close()


def run_daemon():
    updater = Updater(token=config["BotToken"], use_context=True)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', start)
    dispatcher.add_handler(start_handler)
    about_handler = CommandHandler('about', about)
    dispatcher.add_handler(about_handler)
    inline_handler = CallbackQueryHandler(inline_callback)
    dispatcher.add_handler(inline_handler)
    fallback_handler = MessageHandler(Filters.all, start)
    dispatcher.add_handler(fallback_handler)

    webhook_url = config.get('WebhookUrl', "").strip()
    if len(webhook_url) > 0:
        updater.start_webhook(
            listen=config.get('Host', 'localhost'),
            port=config.get('Port', 4215),
            webhook_url=webhook_url)
    else:
        # use polling if no webhook is set
        updater.start_polling()

    updater.idle()
    updater.stop()

