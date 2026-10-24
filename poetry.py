"""
Случайные стихотворения с russian-poetry.ru.
"""

import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SITE_URL = "https://russian-poetry.ru/"
RANDOM_URL = urljoin(SITE_URL, "Random.php")
USER_AGENT = "RhymesTelegramBot/2.0 (+https://github.com/forb0t/rhymebot_tg)"
# Сайт иногда не отвечает с первого раза
ATTEMPTS = 3


class PoetryError(Exception):
    """Стихотворение не удалось получить."""


@dataclass
class Poem:
    title: str
    author: str | None
    author_url: str | None
    text: str
    # Дата написания или место публикации — то, что сайт пишет под стихотворением
    note: str | None


def _clean_line(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_poem(html_text: str) -> Poem:
    soup = BeautifulSoup(html_text, "html.parser")
    pre = soup.find("pre")
    if pre is None:
        raise PoetryError("на странице нет текста стихотворения")

    # Строки бывают с отступами — сохраняем их, убираем только пустоту по краям
    text = pre.get_text().replace("\r\n", "\n").strip("\n").rstrip()
    if not text.strip():
        raise PoetryError("пустое стихотворение")

    # Перед текстом идут абзацы: «Случайное стихотворение», автор (ссылка на его страницу), название
    author = author_url = title = None
    for paragraph in pre.find_all_previous("p"):
        link = paragraph.find("a", href=re.compile(r"Poet\.php"))
        if link is not None:
            author = _clean_line(link.get_text()) or None
            author_url = urljoin(SITE_URL, link["href"])
            break
        bold = paragraph.find("b")
        if title is None and bold is not None:
            candidate = _clean_line(bold.get_text())
            if candidate and candidate != "Случайное стихотворение":
                title = candidate

    # Под текстом до ссылки «Ещё!» — дата или источник
    note_parts = []
    for sibling in pre.next_siblings:
        if getattr(sibling, "name", None) == "p":
            break
        piece = sibling.get_text(" ") if hasattr(sibling, "get_text") else str(sibling)
        piece = _clean_line(piece)
        if piece:
            note_parts.append(piece)
    note = " ".join(note_parts) or None

    return Poem(title=title or "Без названия", author=author, author_url=author_url, text=text, note=note)


def random_poem() -> Poem:
    last_error: Exception | None = None
    for attempt in range(ATTEMPTS):
        try:
            response = requests.get(RANDOM_URL, headers={"User-Agent": USER_AGENT}, timeout=15)
            response.raise_for_status()
            # Сайт в windows-1251; если сервер не назвал кодировку, requests решит, что это latin-1
            if not response.encoding or response.encoding.lower() in ("iso-8859-1", "latin-1"):
                response.encoding = "windows-1251"
            return parse_poem(response.text)
        except (requests.RequestException, PoetryError) as exc:
            last_error = exc
            logger.warning("Не удалось получить стихотворение (попытка %d): %s", attempt + 1, exc)
            time.sleep(1 + attempt)
    raise PoetryError(f"сайт со стихами не отвечает: {last_error}")
