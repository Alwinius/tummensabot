#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import configparser
from datetime import date
from mensa_db import Base
from mensa_db import User
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import telegram
from telegram import InlineKeyboardButton
from telegram.error import ChatMigrated
from telegram.error import NetworkError
from telegram.error import TimedOut
from telegram.error import Unauthorized
from telegram.error import BadRequest

engine = create_engine('sqlite:///mensausers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
config = configparser.ConfigParser()
config.read('config.ini')
bot = telegram.Bot(token=config['DEFAULT']['BotToken'])
day = date.today().isoformat()

#acquire contents first
def getplan(day, mensa):
    r = requests.get("http://www.studentenwerk-muenchen.de/mensa/speiseplan/speiseplan_" + day + "_" + str(mensa) + "_-de.html")
    soup = BeautifulSoup(r.content, "lxml")
    try:
        message = soup.select(".heute_" + day + " span")[0].getText() + ":\n"
        cont = soup.select(".c-schedule__list")
    except IndexError:
        message = ""
    if message != "":
        meals = []
        lastcat=""
        for meal in cont[0].children:
            try:
                cat = meal.select(".stwm-artname")[0].string
                if lastcat != cat and cat is not None:
                    message += "*" + cat + "*:\n"
                    lastcat = cat
                mealname = meal.select(".js-schedule-dish-description")[0].find(text=True, recursive=False)
                message += "• " + mealname
                a = meal.select(".c-schedule__icon span")
                if len(a) > 0:
                    if "vegan" in a[0]["class"]:
                        message += " 🥑"
                    if "fleischlos" in a[0]["class"]:
                        message += " 🥕"
                meat = meal.select(".u-text-sup")
                if "S" in meat[0].getText():
                    message += "🐷"
                if "R" in meat[0].getText():
                    message += "🐄"
                message += "\n"
            except (AttributeError, IndexError):
                pass
        message+="\n🥑 = vegan, 🥕 = vegetarisch\n🐷 = Schwein, 🐄 = Rind"
        return message

def send(chat_id, message_id, message, reply_markup):	
    try:
        if message_id == None or message_id == 0:
            print("Sending new message")
            rep = bot.sendMessage(chat_id=chat_id, text=message, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)
            session = DBSession()
            user = session.query(User).filter(User.id == chat_id).first()
            user.message_id = rep.message_id
            session.commit()
            session.close()
            return True
        else:
            print("Updating message")
            bot.editMessageText(chat_id=chat_id, text=message, message_id=message_id, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)
            return True
    except (Unauthorized, BadRequest):
        session = DBSession()
        user = session.query(User).filter(User.id == chat_id).first()
        user.notifications = -1
        bot.sendMessage(chat_id=config["DEFAULT"]["AdminID"], text="Error sending meals to "+user.first_name)
        session.commit()
        session.close()
        return True
    except (TimedOut, NetworkError):
        import time
        time.sleep(5) # delays for 5 seconds
        return send(chat_id, message_id, message, reply_markup)
    except ChatMigrated as e:
        session = DBSession()
        user = session.query(User).filter(User.id == chat_id).first()
        user.id = e.new_chat_id
        session.commit()
        session.close()
        return True
    else:
        return False
	
urls = [421, 422, 411, 412, 423, 432, 424]
names = dict([(421, "Arcisstr"), (422, "Garching"), (411, "Leopoldstr."), (412, "Martinsried"), (423, "Weihenstephan"), (432, "Pasing"), (424, "Oettinger")])
contents = dict()
for url in urls:
    print("Getting plan from mensa "+names[url])
    contents[url] = getplan(day, url)

button_list = [[InlineKeyboardButton("Auto-Update deaktivieren", callback_data="5$0")], [InlineKeyboardButton("Mensa Arcisstr.", callback_data="421$Arcisstr"), InlineKeyboardButton("Mensa Leopoldstr.", callback_data="411$Leopoldstr")], [InlineKeyboardButton("Mensa Garching", callback_data="422$Garching"), InlineKeyboardButton("Mensa Martinsried", callback_data="412$Martinsried")], [InlineKeyboardButton("Mensa Weihenstephan", callback_data="423$Weihenstephan"), InlineKeyboardButton("Mensa Pasing", callback_data="432$Pasing")], [InlineKeyboardButton("StuBistro Oettingerstraße", callback_data="424$Oettinger")]]

reply_markup = telegram.InlineKeyboardMarkup(button_list)	

session = DBSession()
entries = session.query(User).filter(User.notifications > 0)

for entry in entries:
    entry.counter += 1
    session.commit()
    try:
        print("Sending plan to "+entry.first_name)
        send(entry.id, entry.message_id, "Mensa " + names[entry.notifications] + ", " + contents[entry.notifications], reply_markup)
    except TypeError:
        pass
session.close()
