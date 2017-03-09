#!/bin/python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import requests, telegram, configparser
from sqlalchemy import create_engine, distinct
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from mensa_db import User, Base
from telegram.error import (TelegramError, Unauthorized, 
                            TimedOut, ChatMigrated, NetworkError)

engine = create_engine('sqlite:///mensausers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
config = configparser.ConfigParser()
config.read('config.ini')

session = DBSession()
entries=session.query(User).filter(User.notifications>0)
session.close()
bot = telegram.Bot(token=config['DEFAULT']['BotToken'])

#acquire contents first
def getplan(url):
	r = requests.get(url)
	soup = BeautifulSoup(r.content, "lxml")
	cont = soup.select("a[name=heute]")
	message=str(cont[0].string)+"\n"
	cont=cont[0].parent.parent.parent.parent
	meals=[]
	for meal in cont:
		try:
			message+=str(meal.select(".stwm-artname")[0].string)+": "+str(meal.select(".beschreibung span")[0].getText())+"\n"
		except (AttributeError, IndexError): 
			pass
	return message

def send(chat_id, message, reply_markup):	
	try:
		bot.sendMessage(chat_id=chat_id, text=message, reply_markup=reply_markup)
	except Unauthorized:
		session = DBSession()
		user=session.query(User).filter(User.id==chat_id).first()
		user.notifications=-1
		session.commit()
		session.close()
		return True
	except (TimeOut, NetworkError):
		return send(chat_id, message, reply_markup)
	except ChatMigrated as e:
		session = DBSession()
		user=session.query(User).filter(User.id==user_id).first()
		user.id=e.new_chat_id
		session.commit()
		session.close()
		return True
	
urls=[421,422,411,412,423]
contents=dict()
for url in urls:
	contents[url]=getplan("http://www.studentenwerk-muenchen.de/mensa/speiseplan/speiseplan_"+str(url)+"_-de.html")

custom_keyboard=[["Mensa Arcisstraße"], ["Mensa Garching", "Mensa Leopoldstraße"], ["Mensa Martinsried", "Mensa Weihenstephan"]]



reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)	
for entry in entries:
	send(entry.id, contents[entry.notifications],reply_markup)