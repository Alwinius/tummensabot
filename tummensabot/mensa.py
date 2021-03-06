#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# @author Alwin Ebermann (alwin@alwin.net.au)
# @author Markus Pielmeier

import datetime
import logging
import time
from typing import List

from telegram import Update, Chat, ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, Message, Bot
from telegram.error import ChatMigrated, TimedOut, Unauthorized, BadRequest
from telegram.ext import CallbackContext, Updater, CommandHandler, CallbackQueryHandler, Filters, MessageHandler

from . import config
from .db import User, Session
from .meals import MenuManager, MENSEN

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

nav_pages = [
    [(421, 411), (422, 412), (423, 432)],  # Mensa
    [(450, 418), (455, 415), (416, 424)],  # StuBistro
    [(512, 526), (527, 524), (532,)]  # StuCafé
]

nav_page_titles = [
    "Mensa", "StuBistro", "StuCafé"
]


def get_page_by_id(mensa_id: int):
    for page, content in enumerate(nav_pages):
        for row in content:
            if mensa_id in row:
                return page
    return 0


def make_inline_markup(page=0, show_noti_btn=False, enable=True):
    arrangement = nav_pages[page]
    rows = []
    if show_noti_btn:
        if enable:
            noti_btn = InlineKeyboardButton("Auto-Update aktivieren", callback_data="5$1")
        else:
            noti_btn = InlineKeyboardButton("Auto-Update deaktivieren", callback_data="5$0")
        rows.append([noti_btn])

    for row in arrangement:
        row_btns = []
        for mensa_id in row:
            name = MENSEN[mensa_id]
            row_btns.append(InlineKeyboardButton(name, callback_data=f"{mensa_id}${name}"))
        rows.append(row_btns)
    prev_page = (page - 1) % len(nav_pages)
    next_page = (page + 1) % len(nav_pages)
    rows.append([
        InlineKeyboardButton("<<", callback_data=f"page${prev_page}"),
        InlineKeyboardButton(">>", callback_data=f"page${next_page}")
    ])
    return InlineKeyboardMarkup(rows)


default_reply_markup = make_inline_markup()

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
        if "Message is not modified" in e.message:
            # user clicked on same button twice, not an issue
            return True
        session = Session()
        user = session.query(User).filter(User.id == chat_id).first()
        user.notifications = -1
        logging.exception(f"Error while sending message to {user.first_name} (#{chat_id})")
        send_developer_message(bot, f"Error while sending message to {user.first_name} (#{chat_id})\n\n{e}")
        session.commit()
        session.close()
        return True
    except TimedOut:
        time.sleep(5)  # delays for 5 seconds
        return send(bot, chat_id, message, reply_markup, message_id)
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
    entry: User = session.query(User).filter(User.id == chat.id).first()
    if not entry:
        # create entry
        new_user = User(id=chat.id, first_name=chat.first_name, last_name=chat.last_name, username=chat.username,
                        title=chat.title, notifications=0, current_selection="0", counter=0)
        session.add(new_user)
        ret = [0, 0]
    else:
        if sel != 0:
            entry.current_selection = sel
        entry.counter += 1
        # update user data
        entry.first_name = chat.first_name
        entry.last_name = chat.last_name
        entry.username = chat.username
        entry.title = chat.title
        ret = [int(entry.notifications), int(entry.current_selection)]
    session.commit()
    session.close()
    return ret


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
           "@tummoodlebot\n - @mydealz\\_bot\n - @tumroomsbot\n - @aachenmensabot")
    send(context.bot, update.message.chat_id, msg)


def inline_callback(update: Update, context: CallbackContext):
    message: Message = update.callback_query.message
    args: List[str] = update.callback_query.data.split("$")

    # this will stop loading indicators
    context.bot.answer_callback_query(update.callback_query.id)

    if args[0] == "page":
        # change page
        page = int(args[1])
        noti, presel = checkuser(message.chat)

        msg = f"Seite {page+1} / {len(nav_pages)}\n"
        for i, title in enumerate(nav_page_titles):
            icon = "▪️" if i == page else "▫"
            msg += f"\n{icon} {title}"

        show_enable = noti <= 0 or noti != presel
        reply_markup = make_inline_markup(page=page, show_noti_btn=True, enable=show_enable)
        send(context.bot, message.chat_id, msg, reply_markup=reply_markup, message_id=message.message_id)
    elif int(args[0]) > 400:
        # show mealplan
        mensa_id, mensa_name = args
        page = get_page_by_id(int(mensa_id))
        noti, presel = checkuser(message.chat, sel=mensa_id)

        msg = menu_manager.get_menu(int(mensa_id)).get_meals_message()

        show_enable = noti <= 0 or noti != presel
        reply_markup = make_inline_markup(page=page, show_noti_btn=True, enable=show_enable)
        send(context.bot, message.chat_id, msg, reply_markup=reply_markup, message_id=message.message_id)
    elif int(args[0]) == 5 and len(args) > 1:
        # manage notifications
        noti, presel = checkuser(message.chat)
        enabled = args[1] == "1"
        change_notifications(message.chat, presel, enabled)

        if enabled:
            msg = "Auto-Update aktiviert für " + MENSEN[presel]
        else:
            msg = "Auto-Update deaktiviert"

        reply_markup = make_inline_markup(page=get_page_by_id(presel), show_noti_btn=True, enable=not enabled)
        send(context.bot, message.chat_id, msg, reply_markup=reply_markup, message_id=message.message_id)
    else:
        logging.error("unknown inline command")
        msg = "Kommando nicht erkannt"
        send(context.bot, message.chat_id, msg)
        dev_msg = f"Inlinekommando nicht erkannt.\n\nData: {update.callback_query.data}\nUser:{message.chat}"
        send_developer_message(context.bot, dev_msg)


def send_notifications(bot=None):
    if bot is None:
        bot = Bot(token=config['BotToken'])

    # clear cache to ensure latest results
    menu_manager.clear_cache()
    plans = {}
    for mensa_id, mensa_name in MENSEN.items():
        logging.debug(f"Getting plan for {mensa_name} (#{mensa_id})")
        plans[mensa_id] = menu_manager.get_menu(mensa_id)

    reply_markup = make_inline_markup(show_noti_btn=True, enable=False)

    session = Session()
    users = session.query(User).filter(User.notifications > 0)
    for user in users:
        user.counter += 1
        session.commit()
        try:
            logging.debug(f"Sending plan to {user.first_name}")
            send(bot, user.id, plans[int(user.notifications)].get_meals_message(),
                 reply_markup=reply_markup, message_id=user.message_id)
        except TypeError:
            logging.exception(f"Caught TypeError while processing user {user.first_name}")

    session.close()


def job_callback(context: CallbackContext):
    logging.debug("Scheduled notification update triggered")
    send_notifications(bot=context.bot)


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

    # schedule daily update
    hour = int(config.get('NotificationHour', 16))
    first = datetime.time(hour=hour, minute=0)
    now = datetime.datetime.now()
    logging.info(f"Job will run daily at {first}. Server time is {now.strftime('%H:%M:%S')}.")
    updater.job_queue.run_daily(job_callback, time=first)

    webhook_url = config.get('WebhookUrl', "").strip()
    if len(webhook_url) > 0:
        updater.bot.set_webhook(webhook_url)
        updater.start_webhook(
            listen=config.get('Host', 'localhost'),
            port=config.get('Port', 4215),
            webhook_url=webhook_url)
    else:
        # use polling if no webhook is set
        updater.start_polling()

    updater.idle()
    updater.stop()
