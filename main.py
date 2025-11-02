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

bot = telebot.TeleBot('5445241159:AAFH1swIuaqLkHk3gpitFHxKoOfBv3roKnQ')


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


@bot.message_handler(commands=['daily'])
def daily(update, job_queue):
    job_queue = JobQueue()
    job_queue.run_repeating(callback = verse, interval=10, first=0)


bot.infinity_polling()
