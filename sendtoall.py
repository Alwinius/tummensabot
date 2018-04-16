#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import configparser
from mensa_db import Base
from mensa_db import User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import telegram
from telegram import InlineKeyboardButton
from telegram.error import ChatMigrated
from telegram.error import TimedOut
from telegram.error import Unauthorized

config = configparser.ConfigParser()
config.read('config.ini')
	
engine = create_engine('sqlite:///mensausers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

bot = telegram.Bot(token=config['DEFAULT']['BotToken'])
button_list = [[InlineKeyboardButton("Mensa Arcisstr.", callback_data="421$Arcisstr"), InlineKeyboardButton("Mensa Leopoldstr.", callback_data="411$Leopoldstr")], [InlineKeyboardButton("Mensa Garching", callback_data="422$Garching"), InlineKeyboardButton("Mensa Martinsried", callback_data="412$Martinsried")], [InlineKeyboardButton("Mensa Weihenstephan", callback_data="423$Weihenstephan"), InlineKeyboardButton("Mensa Pasing", callback_data="432$Pasing")]]

def send(bot, chat_id, message_id, message, reply_markup):	
    try:
        if message_id == None or message_id == 0:
            rep = bot.sendMessage(chat_id=chat_id, text=message, reply_markup=reply_markup)
            session = DBSession()
            user = session.query(User).filter(User.id == chat_id).first()
            user.message_id = rep.message_id
            session.commit()
            session.close()
            return True
        else:
            bot.editMessageText(chat_id=chat_id, text=message, message_id=message_id, reply_markup=reply_markup)
            return True
    except Unauthorized:
        session = DBSession()
        user = session.query(User).filter(User.id == chat_id).first()
        user.notifications = -1
        session.commit()
        session.close()
        return True
    except TimedOut:
        import time
        time.sleep(50) # delays for 50 seconds
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
	
def checkuser(sel, userid):
    session = DBSession()
    entry = session.query(User).filter(User.id == userid).first()
    entry.current_selection = sel if sel != 0 else entry.current_selection
    presel = entry.current_selection
    entry.counter += 1
    noti = entry.notifications
    session.commit()
    session.close()
    return [noti, presel]


def sendMessage(bot, userid):
    message=""
    checkuser(0, userid)
    reply_markup = telegram.InlineKeyboardMarkup(button_list)
    send(bot, userid, None, message, reply_markup)

session=DBSession()
entries=session.query(User)
for entry in entries:
    sendMessage(bot, entry.id)
session.close()