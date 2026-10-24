"""
Настройки из переменных окружения.
"""

import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


class ConfigError(RuntimeError):
    """Настройки заданы неверно."""


def get_bot_token() -> str:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token or token == "your_bot_token_here":
        raise ConfigError("не задан TELEGRAM_BOT_TOKEN")
    return token


def get_timezone() -> ZoneInfo:
    """Часовой пояс рассылки (BOT_TIMEZONE, по умолчанию Europe/Moscow)."""
    name = os.environ.get("BOT_TIMEZONE", "Europe/Moscow").strip()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Неизвестный часовой пояс %r, использую UTC", name)
        return ZoneInfo("UTC")
