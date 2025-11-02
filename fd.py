import datetime
import logging
import pytz
import time

import requests
import telebot
import telegram
from bs4 import BeautifulSoup as bs
from telebot import util
from telegram.ext import Updater, CommandHandler, MessageHandler, Updater, filters, Job, JobQueue, CallbackContext

bot = telebot.TeleBot('YOUR_BOT_TOKEN') #Replace your token

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Привет, этот бот будет присылать тебе случайное стихотворение, пожалуйста '
                                      'выбери частоту отправки')

@bot.message_handler(commands=['remind'])
def verse(message):
    r = requests.get("http://russian-poetry.ru/Random.php").text
    soup = bs(r, "html.parser")
    m = soup.find("title").text
    b = soup.find("pre").text
    msg = m + b
    bot.send_message(message.chat.id, text=msg, parse_mode='html')

def daily(context: CallbackContext):
    r = requests.get("http://russian-poetry.ru/Random.php").text
    soup = bs(r, "html.parser")
    m = soup.find("title").text
    b = soup.find("pre").text
    msg = m + b
    context.bot.send_message(context.job.context, text=msg, parse_mode='html')

def start_daily(update: telegram.Update, context: CallbackContext):
    context.job_queue.run_repeating(daily, interval=10, first=0, context=update.effective_chat.id)

if __name__ == '__main__':
    updater = Updater("YOUR_BOT_TOKEN", use_context=True) #Replace your token
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("remind", verse))
    dispatcher.add_handler(CommandHandler("daily", start_daily))

    updater.start_polling()
    updater.idle()