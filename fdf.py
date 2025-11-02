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


def remind(update, CallbackContext) -> None:
    # Add code for reminder here
    update.message.reply_text('Reminder set!')


def daily(update, CallbackContext) -> None:
    # Add code to be executed daily here
    update.message.reply_text('Daily job executed!')


def schedule_daily_job(context: CallbackContext) -> None:
    context.job_queue.run_daily(daily, time)


updater = Updater("TOKEN")
job_queue = JobQueue


updater.bot.add_handler(CommandHandler('remind', remind))
updater.bot.add_handler(CommandHandler('daily', daily))

job_queue.run_once(schedule_daily_job, 0)

updater.start_polling()
updater.idle()
