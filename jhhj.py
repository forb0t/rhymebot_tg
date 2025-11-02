import requests
from bs4 import BeautifulSoup
from telegram import Update, Bot, Dispatcher
from telegram.ext import JobQueue, Dispatcher

# Replace with your Telegram bot token
TOKEN = '5445241159:AAFH1swIuaqLkHk3gpitFHxKoOfBv3roKnQ'


def verse(update, context):
    r = requests.get("http://russian-poetry.ru/Random.php").text
    soup = BeautifulSoup(r, "html.parser")
    m = soup.find("title").text
    b = soup.find("pre").text
    msg = m + b
    update.message.reply_text(text=msg, parse_mode='html')


def schedule_daily_reminder(update, context):
    job = context.job_queue.run_repeating(callback=verse, interval=86400, first=0)  # Daily interval (24 hours)
    update.message.reply_text(text="Daily reminder successfully scheduled!")


def main():
    bot = Bot(token=TOKEN)
    job_queue = JobQueue()

    # Handle '/remind' command
    bot.dispatcher.add_handler(CommandHandler('remind', verse))

    # Handle '/daily' command - pass context for job_queue access
    bot.dispatcher.add_handler(CommandHandler('daily', schedule_daily_reminder))

    bot.infinity_polling()


if __name__ == "__main__":
    main()
