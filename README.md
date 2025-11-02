# RhymeBot Telegram

A Telegram bot that sends random Russian poetry to users. The bot can deliver poems on demand or schedule them for daily delivery.

## Features

- **Random Poetry**: Fetch and send random Russian poems from [russian-poetry.ru](http://russian-poetry.ru)
- **On-Demand Poems**: Request a poem instantly using the `/remind` command
- **Scheduled Delivery**: Set up daily poetry delivery with the `/daily` command
- **Flexible Timing**: Schedule poems to be sent after a specified number of seconds

## Commands

- `/start` - Start the bot and get a welcome message
- `/remind` - Request a poem immediately
- `/daily` - Set up daily poetry delivery

## Installation

1. Clone this repository:
```bash
git clone https://github.com/forb0t/rhymebot_tg.git
cd rhymebot_tg
```

2. Install required dependencies:
```bash
pip install pyTelegramBotAPI python-telegram-bot requests beautifulsoup4 pytz
```

## Configuration

1. Create a Telegram bot by talking to [@BotFather](https://t.me/BotFather) on Telegram
2. Get your bot token
3. Replace `'YOUR_BOT_TOKEN'` in the main bot file with your actual bot token:
   - Open `ggd.py` or `main.py`
   - Find the line: `bot = telebot.TeleBot('YOUR_BOT_TOKEN')`
   - Replace `'YOUR_BOT_TOKEN'` with your actual token

**Note**: For security, consider using environment variables to store your bot token instead of hardcoding it.

## Usage

1. Run the bot:
```bash
python ggd.py
```
or
```bash
python main.py
```

2. Open Telegram and find your bot
3. Send `/start` to begin
4. Use `/remind` to get a poem immediately or `/daily` for scheduled delivery

## Requirements

- Python 3.7+
- pyTelegramBotAPI
- python-telegram-bot
- requests
- beautifulsoup4
- pytz

## Project Structure

```
rhymebot_tg/
├── ggd.py           # Main bot implementation
├── main.py          # Alternative bot implementation
├── fd.py            # Additional bot code
├── fdf.py           # Additional bot code
├── .gitignore       # Git ignore file
└── README.md        # This file
```

## Notes

- The bot fetches poetry from the external source `russian-poetry.ru`
- Make sure you have an active internet connection
- The bot uses long polling to receive updates from Telegram

## License

This project is open source and available for modification and distribution.

