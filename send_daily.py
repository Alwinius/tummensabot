#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# created by Alwin Ebermann (alwin@alwin.net.au)

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


config = configparser.ConfigParser()
config.read('config.ini')

engine = create_engine('sqlite:///mensausers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

bot = telegram.Bot(token=config['DEFAULT']['BotToken'])
button_list = [[InlineKeyboardButton("Mensa Arcisstr.", callback_data="421$Arcisstr"),
                InlineKeyboardButton("Mensa Leopoldstr.", callback_data="411$Leopoldstr")],
               [InlineKeyboardButton("Mensa Garching", callback_data="422$Garching"),
                InlineKeyboardButton("Mensa Martinsried", callback_data="412$Martinsried")],
               [InlineKeyboardButton("Mensa Weihenstephan", callback_data="423$Weihenstephan"),
                InlineKeyboardButton("Mensa Pasing", callback_data="432$Pasing")]]


def getplan(day, mensa):
    r = requests.get(
        "http://www.studentenwerk-muenchen.de/mensa/speiseplan/speiseplan_" + day + "_" + str(mensa) + "_-de.html")
    soup = BeautifulSoup(r.content, "lxml")
    try:
        message = soup.select(".heute_" + day + " span")[0].getText() + ":\n"
        cont = soup.select(".c-schedule__list")
    except IndexError:
        message = ""
    if message != "":
        meals = []
        lastcat = ""
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
        message += "\n🥑 = vegan, 🥕 = vegetarisch\n🐷 = Schwein, 🐄 = Rind"
        return message


urls = [421, 422, 411, 412, 423, 432]
names = dict([(421, "Arcisstr"), (422, "Garching"), (411, "Leopoldstr."), (412, "Martinsried"), (423, "Weihenstephan"),
              (432, "Pasing")])
contents = dict()
day = date.today().isoformat()
for url in urls:
    print("Getting plan from mensa " + names[url])
    contents[url] = getplan(day, url)

reply_markup = telegram.InlineKeyboardMarkup(button_list)

session=DBSession()
entries=session.query(User)
for entry in entries:
    if entry.dailymsg is not None and entry.dailymsg[date.today().weekday()]=="1" and contents[entry.daily_selection]!="":
        rep=bot.sendMessage(text=contents[entry.daily_selection], chat_id=entry.id, reply_markup=reply_markup, parse_mode=telegram.ParseMode.MARKDOWN)
        entry.message_id = rep.message_id
        print("Sending message to "+entry.first_name)
session.commit()
session.close()