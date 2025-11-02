import requests
from bs4 import BeautifulSoup
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


# Функция для генерации стиха

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, 'Привет, этот бот будет присылать тебе случайное стихотворение, пожалуйста '
                                      'выбери частоту отправки')


def generate_verse(context):
    r = requests.get("http://russian-poetry.ru/Random.php").text
    soup = BeautifulSoup(r, "html.parser")
    title = soup.find("title").text
    poem = soup.find("pre").text
    return title + "\n\n" + poem


# Обработчик команды /remind
@bot.message_handler(commands=['remind'])
def remind(update, context):
    chat_id = update.effective_chat.id
    text = "Введите время, через которое хотите получить стих (в секуndax):"
    bot.send_message(chat_id, text=text)


# Обработчик ввода времени для напоминания
@bot.message_handler(filters=filters.Text)
def remind_time(update, context):
    try:
        seconds = int(update.message.text)
    except ValueError:
        bot.send_message(update.message.chat_id, text="Неверный формат времени. Введите число.")
        return

    chat_id = update.message.chat_id
    job_queue = context.job_queue
    job = job_queue.run_once(generate_verse, seconds, chat_id=chat_id)
    bot.send_message(chat_id, text=f"Стих будет отправлен через {seconds} секунд.")


# Обработчик команды /daily
@bot.message_handler(commands=['daily'])
def daily(update, context):
    chat_id = update.message.chat_id
    job_queue = context.job_queue
    job = job_queue.run_repeating(generate_verse, interval=86400, first=0, chat_id=chat_id)
    bot.send_message(chat_id, text="Стих будет отправляться ежедневно в одно и то же время.")


bot.infinity_polling()
