#!/bin/python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import requests, logging, telegram, configparser
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from sqlalchemy import create_engine, distinct
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from mensa_db import User, Base
from datetime import datetime
	
config = configparser.ConfigParser()
config.read('config.ini')
	
engine = create_engine('sqlite:///mensausers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
custom_keyboard=[["Mensa Arcisstraße"], ["Mensa Garching", "Mensa Leopoldstraße"], ["Mensa Martinsried", "Mensa Weihenstephan"]]

def getplan(sel):
	urls=[0,421,422,411,412,423]
	r = requests.get("http://www.studentenwerk-muenchen.de/mensa/speiseplan/speiseplan_"+str(sel)+"_-de.html")
	soup = BeautifulSoup(r.content, "lxml")
	cont = soup.select("a[name=heute]")
	message=str(cont[0].string)+"\n"
	noww=datetime.today()
	if noww.hour>15 and noww.weekday()<5:
		cont=cont[0].parent.parent.parent.parent.next_sibling.next_sibling
		message=str(cont.select("a > strong")[0].string+"\n")
	else:
		message=str(cont[0].string)+"\n"
		cont=cont[0].parent.parent.parent.parent
	meals=[]
	for meal in cont:
		try:
			message+=str(meal.select(".stwm-artname")[0].string)+": "+str(meal.select(".beschreibung span")[0].getText())+"\n"
		except (AttributeError, IndexError): 
			pass
	return message

def checkuser(sel, update):
	session = DBSession()
	entry=session.query(User).filter(User.id==update.message.chat_id).first()
	if not entry:
		#create entry
		new_user = User(id=update.message.chat_id, first_name=update.message.chat.first_name, last_name=update.message.chat.last_name, username=update.message.chat.username, title=update.message.chat.title, notifications=0, current_selection="0")
		session.add(new_user)
		session.commit()
		session.close()
		return [0, 0]
	else:
		presel=entry.current_selection
		entry.current_selection=sel
		noti=entry.notifications
		session.commit()
		session.close()
		return [noti, presel]
	
def changenotifications(update, sel, task):
	session = DBSession()
	entry=session.query(User).filter(User.id==update.message.chat_id).first()
	if task==True and sel!=0:
		entry.notifications=sel
		session.commit()
		session.close()
		return True
	elif task==False and entry.notifications!=0:
		entry.notifications=0
		session.commit()
		session.close()
		return True
	else:
		session.close()
		return False
	
def start(bot, update):
	checkuser(0, update)
	reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
	bot.sendMessage(chat_id=update.message.chat_id, text="Bitte über das Menü eine Mensa wählen. Informationen über diesen Bot gibt's hier /about.", reply_markup=reply_markup)

def about(bot, update):
	checkuser(0, update)
	reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
	bot.sendMessage(chat_id=update.message.chat_id, text="Dieser Bot wurde erstellt von @Alwinius. Der Quellcode ist unter https://github.com/Alwinius/tummensabot verfügbar.", reply_markup=reply_markup)	
	
def echo(bot, update):
	mensa=update.message.text
	if mensa=="Mensa Arcisstraße":
		sel=421
	elif mensa=="Mensa Garching":
		sel=422
	elif mensa=="Mensa Leopoldstraße":
		sel=411
	elif mensa=="Mensa Martinsried":
		sel=412
	elif mensa=="Mensa Weihenstephan":
		sel=423
	elif mensa=="Benachrichtigungen aktivieren":
		sel=0
		user=checkuser(0, update)
		if changenotifications(update, user[1], True):
			reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
			bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigung für zuletzt ausgewählte Mensa aktiviert", reply_markup=reply_markup)
		else:
			reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
			bot.sendMessage(chat_id=update.message.chat_id, text="Bitte zuerst eine Mensa auswählen.", reply_markup=reply_markup)
	elif mensa=="Benachrichtigungen deaktivieren":
		sel=0
		user=checkuser(0, update)
		if changenotifications(update, user[1], False):
			reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
			bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigung deaktiviert", reply_markup=reply_markup)
		else:
			reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
			bot.sendMessage(chat_id=update.message.chat_id, text="Keine Benachrichtigung aktiv", reply_markup=reply_markup)
	else:
		sel=0
	if sel != 0:
		user=checkuser(sel, update)
		if user[0]==sel:
			#notification active for current selection
			keyboard=[["Benachrichtigungen deaktivieren"]]+custom_keyboard
		else:
			keyboard=[["Benachrichtigungen aktivieren"]]+custom_keyboard
		reply_markup = telegram.ReplyKeyboardMarkup(keyboard)
		bot.sendMessage(chat_id=update.message.chat_id, text=getplan(sel), reply_markup=reply_markup)
		
updater = Updater(token=config['DEFAULT']['BotToken'])
dispatcher = updater.dispatcher
start_handler = CommandHandler('start', start)
dispatcher.add_handler(start_handler)
about_handler = CommandHandler('about', about)
dispatcher.add_handler(about_handler)		
echo_handler = MessageHandler(Filters.text, echo)
dispatcher.add_handler(echo_handler)
updater.start_webhook(listen='localhost', port=4215, webhook_url=config['DEFAULT']['WebhookUrl'])
updater.idle()
updater.stop()