#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import configparser
from datetime import date
from datetime import datetime
from datetime import timedelta
import logging
from mensa_db import Base
from mensa_db import User
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import telegram
from telegram import InlineKeyboardButton
from telegram.error import ChatMigrated
from telegram.error import TimedOut
from telegram.error import Unauthorized
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler
from telegram.ext import CommandHandler
from telegram.ext import Filters
from telegram.ext import MessageHandler
from telegram.ext import Updater

config = configparser.ConfigParser()
config.read('config.ini')

engine = create_engine('sqlite:///mensausers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
button_list = [[InlineKeyboardButton("Mensa Arcisstr.", callback_data="421$Arcisstr"),
                InlineKeyboardButton("Mensa Leopoldstr.", callback_data="411$Leopoldstr")],
               [InlineKeyboardButton("Mensa Garching", callback_data="422$Garching"),
                InlineKeyboardButton("Mensa Martinsried", callback_data="412$Martinsried")],
               [InlineKeyboardButton("Mensa Weihenstephan", callback_data="423$Weihenstephan"),
                InlineKeyboardButton("Mensa Pasing", callback_data="432$Pasing")]]
names = dict([(421, "Arcisstr"), (422, "Garching"), (411, "Leopoldstr."), (412, "Martinsried"), (423, "Weihenstephan"),
              (432, "Pasing")])


def getplan(mensa):
    day = date.today()
    counter = 0
    now = datetime.now()
    if now.hour > 15 and now.date().weekday() < 5:
        # nachmittags wochentags
        day = day + timedelta(days=1)  # nächsten Tag anzeigen
    if day.isoweekday() in set((6, 7)):  # falls nun wochenende ausgewählt nächsten Montag nehmen
        day += timedelta(days=8 - day.isoweekday())
    r = requests.get("http://www.studentenwerk-muenchen.de/mensa/speiseplan/speiseplan_" + day.isoformat() + "_" + str(
        mensa) + "_-de.html")
    while r.status_code == 404 and counter < 20:  # bei fehlenden Tagen immer weiter nächsten nehmen
        day = day + timedelta(days=1)
        counter += 1
        r = requests.get(
            "http://www.studentenwerk-muenchen.de/mensa/speiseplan/speiseplan_" + day.isoformat() + "_" + str(
                mensa) + "_-de.html")
    soup = BeautifulSoup(r.content, "lxml")
    message = soup.select(".heute_" + day.isoformat() + " span")[0].getText() + ":*\n\n"
    cont = soup.select(".c-schedule__list")
    lastcat=""
    for meal in cont[0].children:
        try:
            cat = meal.select(".stwm-artname")[0].string
            if lastcat != cat and cat is not None:
                message+="*"+cat+"*:\n"
                lastcat=cat
            mealname=meal.select(".js-schedule-dish-description")[0].find(text=True, recursive=False)
            message += "• " + mealname
            a=meal.select(".c-schedule__icon span")
            if len(a)>0:
                if "vegan" in a[0]["class"]:
                    message += " 🥑"
                if "fleischlos"in a[0]["class"]:
                    message += " 🥕"
            meat=meal.select(".u-text-sup")
            if "S" in meat[0].getText():
                message += "🐷"
            if "R" in meat[0].getText():
                message += "🐄"
            message+= "\n"
        except (AttributeError, IndexError):
            pass
    message += "\n🥑 = vegan, 🥕 = vegetarisch\n🐷 = Schwein, 🐄 = Rind"
    return message


def send(bot, chat_id, message_id, message, reply_markup):
    try:
        if message_id == None or message_id == 0:
            rep = bot.sendMessage(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)
            session = DBSession()
            user = session.query(User).filter(User.id == chat_id).first()
            user.message_id = rep.message_id
            session.commit()
            session.close()
            return True
        else:
            bot.editMessageText(chat_id=chat_id, text=message, message_id=message_id, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)
            return True
    except (Unauthorized, BadRequest):
        session = DBSession()
        user = session.query(User).filter(User.id == chat_id).first()
        user.notifications = -1
        session.commit()
        session.close()
        return True
    except TimedOut:
        import time
        time.sleep(50)  # delays for 5 seconds
        return send(bot, chat_id, message_id, message, reply_markup)
    except ChatMigrated as e:
        session = DBSession()
        user = session.query(User).filter(User.id == chat_id).first()
        user.id = e.new_chat_id
        session.commit()
        session.close()
        return True
    else:
        return False


def checkuser(sel, update):
    session = DBSession()
    try:
        chat = update.message.chat
    except AttributeError:
        chat = update.callback_query.message.chat
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


def changenotifications(update, sel, task):
    session = DBSession()
    entry = session.query(User).filter(User.id == update.callback_query.message.chat.id).first()
    if task == "1":
        entry.notifications = sel
        session.commit()
        session.close()
        return True
    else:
        entry.notifications = 0
        session.commit()
        session.close()
        return False


def start(bot, update):
    checkuser(0, update)
    reply_markup = telegram.InlineKeyboardMarkup(button_list)
    send(bot, update.message.chat_id, None,
         "Bitte über das Menü eine Mensa wählen. Informationen über diesen Bot gibt's hier /about.", reply_markup)


def about(bot, update):
    checkuser(0, update)
    reply_markup = telegram.InlineKeyboardMarkup(button_list)
    send(bot, update.message.chat_id, None,
         "Dieser Bot wurde erstellt von @Alwinius. Der Quellcode ist unter https://github.com/Alwinius/tummensabot "
         "verfügbar.\nWeitere interessante Bots: \n - @tummoodlebot\n - @mydealz_bot",
         reply_markup)


def AllInline(bot, update):
    args = update.callback_query.data.split("$")
    if int(args[0]) > 400:
        # Speiseplan anzeigen
        user = checkuser(args[0], update)
        msg = getplan(args[0])
        if int(user[0]) <= 0:
            custom_keyboard = [[InlineKeyboardButton("Auto-Update aktivieren", callback_data="5$1")]] + button_list
        else:
            custom_keyboard = [[InlineKeyboardButton("Auto-Update deaktivieren", callback_data="5$0")]] + button_list
        reply_markup = telegram.InlineKeyboardMarkup(custom_keyboard)
        send(bot, update.callback_query.message.chat.id, update.callback_query.message.message_id,
             "*Mensa " + args[1] + " " + msg, reply_markup)
    elif int(args[0]) == 5 and len(args) > 1:
        # Benachrichtigungen ändern
        user = checkuser(0, update)
        if changenotifications(update, user[1], args[1]):
            custom_keyboard = [[InlineKeyboardButton("Auto-Update deaktivieren", callback_data="5$0")]] + button_list
            reply_markup = telegram.InlineKeyboardMarkup(custom_keyboard)
            send(bot, update.callback_query.message.chat.id, update.callback_query.message.message_id,
                 "Auto-Update aktiviert für Mensa " + names[int(user[1])], reply_markup)
        else:
            custom_keyboard = [[InlineKeyboardButton("Auto-Update aktivieren", callback_data="5$1")]] + button_list
            reply_markup = telegram.InlineKeyboardMarkup(custom_keyboard)
            send(bot, update.callback_query.message.chat.id, update.callback_query.message.message_id,
                 "Auto-Update deaktiviert", reply_markup)
    else:
        reply_markup = telegram.InlineKeyboardMarkup(button_list)
        send(bot, update.callback_query.message.chat.id, update.callback_query.message.message_id,
             "Kommando nicht erkannt", reply_markup)
        bot.sendMessage(text="Inlinekommando nicht erkannt.\n\nData: " + update.callback_query.data + "\n User: " + str(
            update.callback_query.message.chat), chat_id=config['DEFAULT']['AdminId'])


updater = Updater(token=config['DEFAULT']['BotToken'])
dispatcher = updater.dispatcher
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)
about_handler = CommandHandler('about', about)
dispatcher.add_handler(about_handler)
inlinehandler = CallbackQueryHandler(AllInline)
dispatcher.add_handler(inlinehandler)
fallbackhandler = MessageHandler(Filters.all, start)
dispatcher.add_handler(fallbackhandler)

updater.start_webhook(listen='localhost', port=4215, webhook_url=config['DEFAULT']['WebhookUrl'])
updater.idle()
updater.stop()
