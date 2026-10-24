"""
Telegram-бот, присылающий случайные стихи русских поэтов — по кнопке или по расписанию.
"""

import asyncio
import html
import logging
import sys
from datetime import datetime, timedelta, timezone

from telegram import (
    BotCommand,
    InlineKeyboardButton as Button,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    Update,
)
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, Forbidden, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    MessageHandler,
    filters,
)

import bot_config
from bot_config import ConfigError
from poetry import Poem, PoetryError, random_poem
from storage import Storage, data_dir, from_ts

logger = logging.getLogger(__name__)

# Имя и описания бот выставляет себе сам при каждом запуске — так их не подменить надолго
BOT_NAME = "Rhymes"
# Показывается в пустом чате до нажатия «Старт» (до 512 символов)
DESCRIPTION = (
    "📜 Случайные стихи русских поэтов с сайта russian-poetry.ru.\n\n"
    "🎲 Новое стихотворение по кнопке в любой момент\n"
    "⏰ Рассылка: каждый день, через день или раз в неделю — в удобное время\n\n"
    "Нажмите «Старт», чтобы начать."
)
# Показывается в профиле бота (до 120 символов)
SHORT_DESCRIPTION = "Случайные стихи русских поэтов — по кнопке или по расписанию"
# Всё остальное делается кнопками меню
COMMANDS = [BotCommand("start", "Главное меню")]

FREQUENCIES = {1: "каждый день", 2: "через день", 7: "раз в неделю"}
FREQUENCY_BUTTONS = {1: "Каждый день", 2: "Через день", 7: "Раз в неделю"}
HOURS = (8, 9, 10, 12, 15, 18, 20, 22)
DEFAULT_EVERY_DAYS, DEFAULT_HOUR = 1, 9
MONTHS = ("янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")
# Лимит сообщения Telegram — 4096 символов; длинные стихи делим по строфам с запасом под заголовок
CHUNK_LIMIT = 3500
# EX_CONFIG: systemd не перезапускает бота, пока не поправят настройки (RestartPreventExitStatus)
EXIT_CONFIG_ERROR = 78

Screen = tuple[str, InlineKeyboardMarkup]


def esc(text) -> str:
    return html.escape(str(text or ""), quote=False)


def keyboard(*rows: list[Button]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([row for row in rows if row])


def menu_row() -> list[Button]:
    return [Button("🏠 Меню", callback_data="menu")]


def split_text(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Делит стихотворение на части не длиннее limit — по строфам, а слишком длинные строфы — по строкам."""
    pieces = []
    for stanza in text.split("\n\n"):
        if len(stanza) <= limit:
            pieces.append(stanza)
            continue
        current = ""
        for line in stanza.split("\n"):
            if current and len(current) + len(line) + 1 > limit:
                pieces.append(current)
                current = ""
            current = f"{current}\n{line}" if current else line[:limit]
        pieces.append(current)

    parts, current = [], ""
    for piece in pieces:
        candidate = f"{current}\n\n{piece}" if current else piece
        if current and len(candidate) > limit:
            parts.append(current)
            current = piece
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts


class RhymesBot:
    def __init__(self, token: str) -> None:
        self.db = Storage()
        self.tz = bot_config.get_timezone()

        defaults = Defaults(parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
        self.app = Application.builder().token(token).defaults(defaults).post_init(self._post_init).build()

        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CallbackQueryHandler(self.on_button))
        # Любое сообщение в личке — показываем меню, чтобы было понятно, куда нажимать
        self.app.add_handler(MessageHandler(
            filters.UpdateType.MESSAGE & filters.ChatType.PRIVATE & ~filters.COMMAND, self.cmd_start,
        ))
        self.app.add_error_handler(self.on_error)

    async def _post_init(self, app: Application) -> None:
        bot = app.bot
        try:
            await bot.set_my_commands(COMMANDS)
            # Сравниваем перед записью: у Telegram жёсткие лимиты на смену имени и описаний
            if (await bot.get_my_name()).name != BOT_NAME:
                await bot.set_my_name(BOT_NAME)
            if (await bot.get_my_description()).description != DESCRIPTION:
                await bot.set_my_description(DESCRIPTION)
            if (await bot.get_my_short_description()).short_description != SHORT_DESCRIPTION:
                await bot.set_my_short_description(SHORT_DESCRIPTION)
        except TelegramError as exc:
            logger.warning("Не удалось обновить имя, описание или команды бота: %s", exc)

        app.job_queue.run_repeating(
            self.deliver_due,
            interval=60,
            first=10,
            name="deliver_due",
            # Если ноутбук спал, выполнить проверку сразу после пробуждения
            job_kwargs={"misfire_grace_time": None, "coalesce": True},
        )

    def run(self) -> None:
        logger.info("🚀 Запуск бота...")
        # Сообщения, присланные пока бот был выключен, Telegram хранит сутки — обрабатываем их
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    # ------------------------------------------------------------------ time
    def tz_label(self) -> str:
        return "московское" if self.tz.key == "Europe/Moscow" else self.tz.key

    def when(self, moment: datetime) -> str:
        local = moment.astimezone(self.tz)
        today = datetime.now(self.tz).date()
        clock = local.strftime("%H:%M")
        if local.date() == today:
            return f"сегодня в {clock}"
        if local.date() == today + timedelta(days=1):
            return f"завтра в {clock}"
        return f"{local.day} {MONTHS[local.month - 1]} в {clock}"

    def first_slot(self, hour: int, now: datetime) -> datetime:
        """Ближайшее наступление часа hour — сегодня или завтра."""
        local = now.astimezone(self.tz)
        slot = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        return slot if slot > local else slot + timedelta(days=1)

    def next_slot(self, sub, now: datetime) -> datetime:
        """Следующая рассылка после состоявшейся. Пропущенные (бот был выключен) не досылаем."""
        step = timedelta(days=sub["every_days"])
        slot = from_ts(sub["next_at"]).astimezone(self.tz) + step
        while slot <= now:
            slot += step
        return slot

    # ------------------------------------------------------------------ screens
    def schedule_line(self, sub) -> str:
        return f"{FREQUENCIES.get(sub['every_days'], 'каждый день')} в {sub['hour']:02d}:00"

    def screen_menu(self, chat_id: int) -> Screen:
        sub = self.db.get(chat_id)
        if sub and sub["enabled"]:
            schedule = (
                f"⏰ Рассылка: {self.schedule_line(sub)}\n"
                f"📬 Следующий стих — {self.when(from_ts(sub['next_at']))}"
            )
        else:
            schedule = "⏰ Рассылка выключена — настройте её, и стихи будут приходить сами"

        text = "\n".join([
            "📜 <b>Rhymes</b>",
            "",
            "Случайные стихи русских поэтов с сайта russian-poetry.ru.",
            "",
            schedule,
        ])
        return text, keyboard(
            [Button("🎲 Случайный стих", callback_data="poem")],
            [Button("⏰ Рассылка", callback_data="schedule")],
        )

    def screen_schedule(self, chat_id: int) -> Screen:
        sub = self.db.get(chat_id)
        enabled = bool(sub and sub["enabled"])
        every = sub["every_days"] if sub else DEFAULT_EVERY_DAYS
        hour = sub["hour"] if sub else DEFAULT_HOUR

        lines = ["⏰ <b>Рассылка стихов</b>", ""]
        if enabled:
            lines += [
                f"🔔 Включена: {self.schedule_line(sub)}",
                f"📬 Следующий стих — {self.when(from_ts(sub['next_at']))}",
            ]
        else:
            lines.append("🔕 Выключена")
        lines += [
            "",
            "Выберите, как часто и во сколько присылать стихи — настройки сохраняются сразу.",
            f"<i>Время {esc(self.tz_label())}.</i>",
        ]

        def mark(selected: bool, label: str) -> str:
            return f"✅ {label}" if selected else label

        frequency_row = [
            Button(mark(enabled and every == days, label), callback_data=f"freq:{days}")
            for days, label in FREQUENCY_BUTTONS.items()
        ]
        hour_buttons = [Button(mark(enabled and hour == h, f"{h:02d}:00"), callback_data=f"hour:{h}") for h in HOURS]
        toggle = (
            Button("🔕 Выключить рассылку", callback_data="off") if enabled
            else Button("🔔 Включить рассылку", callback_data="on")
        )
        return "\n".join(lines), keyboard(frequency_row, hour_buttons[:4], hour_buttons[4:], [toggle], menu_row())

    def screen_poem_error(self) -> Screen:
        return (
            "😔 Не удалось загрузить стихотворение — сайт russian-poetry.ru сейчас не отвечает.\n\n"
            "Попробуйте ещё раз чуть позже.",
            keyboard([Button("🔁 Ещё раз", callback_data="poem"), Button("🏠 Меню", callback_data="menu")]),
        )

    @staticmethod
    def poem_keyboard() -> InlineKeyboardMarkup:
        return keyboard([Button("🎲 Ещё стих", callback_data="more"), Button("🏠 Меню", callback_data="poem_menu")])

    @staticmethod
    def poem_messages(poem: Poem, header: str | None = None) -> list[str]:
        head = [header, ""] if header else []
        head.append(f"<b>{esc(poem.title)}</b>")
        if poem.author and poem.author_url:
            head.append(f'<i><a href="{html.escape(poem.author_url, quote=True)}">{esc(poem.author)}</a></i>')
        elif poem.author:
            head.append(f"<i>{esc(poem.author)}</i>")

        parts = [esc(part) for part in split_text(poem.text)]
        parts[0] = "\n".join(head) + "\n\n" + parts[0]
        if poem.note:
            parts[-1] += f"\n\n<i>{esc(poem.note)}</i>"
        return parts

    # ------------------------------------------------------------------ message helpers
    async def show(self, update: Update, screen: Screen) -> Message:
        """Нажатие кнопки — перерисовываем то же сообщение, иначе — присылаем новое."""
        text, markup = screen
        query = update.callback_query
        if query is not None and isinstance(query.message, Message):
            try:
                return await query.edit_message_text(text, reply_markup=markup)
            except BadRequest as exc:
                if "not modified" in str(exc).lower():
                    return query.message
                logger.debug("Не удалось отредактировать сообщение: %s", exc)
        return await update.effective_chat.send_message(text, reply_markup=markup)

    @staticmethod
    async def drop_buttons(message) -> None:
        """Убирает кнопки со старого стихотворения — они остаются только под последним."""
        if isinstance(message, Message):
            try:
                await message.edit_reply_markup(reply_markup=None)
            except TelegramError:
                pass

    async def fetch_poem(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> Poem | None:
        try:
            await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
        except TelegramError:
            pass
        try:
            return await asyncio.to_thread(random_poem)
        except PoetryError as exc:
            logger.warning("%s", exc)
            return None

    # ------------------------------------------------------------------ handlers
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.show(update, self.screen_menu(update.effective_chat.id))

    async def on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        action, _, value = (query.data or "").partition(":")
        chat_id = update.effective_chat.id

        async def answer(text: str | None = None) -> None:
            # Нажатие, сделанное пока бот был выключен, Telegram подтвердить уже не даст — не страшно
            try:
                await query.answer(text)
            except BadRequest:
                pass

        if action in ("freq", "hour", "on", "off"):
            await answer(self.update_schedule(chat_id, action, value))
            await self.show(update, self.screen_schedule(chat_id))
            return

        await answer()
        if action == "menu":
            await self.show(update, self.screen_menu(chat_id))
        elif action == "schedule":
            await self.show(update, self.screen_schedule(chat_id))
        elif action == "poem":
            await self.poem_from_menu(update, context)
        elif action == "more":
            await self.drop_buttons(query.message)
            await self.send_poem(update, context)
        elif action == "poem_menu":
            await self.drop_buttons(query.message)
            text, markup = self.screen_menu(chat_id)
            await update.effective_chat.send_message(text, reply_markup=markup)

    async def poem_from_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Из меню: само меню превращается в стихотворение, а если стих длинный — уступает место нескольким сообщениям."""
        poem = await self.fetch_poem(context, update.effective_chat.id)
        if poem is None:
            await self.show(update, self.screen_poem_error())
            return

        parts = self.poem_messages(poem)
        if len(parts) == 1:
            await self.show(update, (parts[0], self.poem_keyboard()))
            return
        try:
            await update.callback_query.message.delete()
        except TelegramError:
            pass
        await self.send_parts(context.bot, update.effective_chat.id, parts)

    async def send_poem(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        poem = await self.fetch_poem(context, chat_id)
        if poem is None:
            text, markup = self.screen_poem_error()
            await update.effective_chat.send_message(text, reply_markup=markup)
            return
        await self.send_parts(context.bot, chat_id, self.poem_messages(poem))

    async def send_parts(self, bot, chat_id: int, parts: list[str]) -> None:
        for index, text in enumerate(parts):
            markup = self.poem_keyboard() if index == len(parts) - 1 else None
            await bot.send_message(chat_id, text, reply_markup=markup)

    def update_schedule(self, chat_id: int, action: str, value: str) -> str:
        """Сохраняет настройку рассылки и возвращает текст всплывающей подсказки."""
        sub = self.db.get(chat_id)
        every = sub["every_days"] if sub else DEFAULT_EVERY_DAYS
        hour = sub["hour"] if sub else DEFAULT_HOUR

        if action == "off":
            self.db.save(chat_id, every, hour, enabled=False, next_at=None)
            return "🔕 Рассылка выключена"

        if action == "freq" and value.isdigit() and int(value) in FREQUENCIES:
            every = int(value)
        elif action == "hour" and value.isdigit() and int(value) in HOURS:
            hour = int(value)

        # Любой выбор частоты или времени включает рассылку
        self.db.save(chat_id, every, hour, enabled=True, next_at=self.first_slot(hour, datetime.now(timezone.utc)))
        return f"🔔 Стихи будут приходить {FREQUENCIES[every]} в {hour:02d}:00"

    # ------------------------------------------------------------------ scheduled delivery
    async def deliver_due(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        now = datetime.now(timezone.utc)
        for sub in self.db.due(now):
            try:
                poem = await asyncio.to_thread(random_poem)
            except PoetryError as exc:
                # Сайт лежит — не сдвигаем расписание, попробуем через минуту
                logger.warning("Рассылка отложена: %s", exc)
                return

            if await self.deliver(context.bot, sub["chat_id"], poem):
                self.db.set_next(sub["chat_id"], self.next_slot(sub, now))
            # Лимит Telegram — около 30 сообщений в секунду
            await asyncio.sleep(0.05)

    async def deliver(self, bot, chat_id: int, poem: Poem) -> bool:
        parts = self.poem_messages(poem, header="📬 <i>Стих по расписанию</i>")
        for _attempt in range(3):
            try:
                await self.send_parts(bot, chat_id, parts)
                return True
            except RetryAfter as exc:
                await asyncio.sleep(exc.retry_after)
            except Forbidden:
                # Пользователь заблокировал бота или удалил его из группы
                logger.info("Чат %s недоступен — удаляю подписку", chat_id)
                self.db.delete(chat_id)
                return False
            except BadRequest as exc:
                if "chat not found" in str(exc).lower():
                    self.db.delete(chat_id)
                else:
                    logger.warning("Не удалось отправить стих в %s: %s", chat_id, exc)
                return False
            except TelegramError as exc:
                # Сеть пропала — расписание не сдвигаем, попробуем через минуту
                logger.warning("Не удалось отправить стих в %s: %s", chat_id, exc)
                return False
        return False

    async def on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Ошибка при обработке обновления", exc_info=context.error)


def setup_logging() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(data_dir() / "bot.log", encoding="utf-8"),
        ],
    )
    # httpx пишет в лог каждый запрос к Telegram вместе с токеном в адресе
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    setup_logging()
    try:
        token = bot_config.get_bot_token()
    except ConfigError as exc:
        logger.error("❌ %s — задайте его в окружении (.env или ~/.config/rhymebot/env)", exc)
        sys.exit(EXIT_CONFIG_ERROR)

    RhymesBot(token).run()


if __name__ == "__main__":
    main()
