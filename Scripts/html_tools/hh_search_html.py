"""Читает карточки сохранённой выдачи hh без браузера и сетевых запросов."""

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from core import utils

# Эти элементы не имеют закрывающего тега и не увеличивают глубину разметки.
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


def merge_vacancy(vacancies, vacancy):
    """Повтор ID дополняет только пустые поля; первый заполненный вариант сохраняется."""
    saved = vacancies.setdefault(vacancy["ID"], dict(vacancy))
    for field in ("Заголовок", "Компания"):
        if not saved[field]:
            saved[field] = vacancy[field]


class SearchCardsParser(HTMLParser):
    """Держит текст внутри своей карточки, чтобы не перепутать компании соседних вакансий."""
    def __init__(self, base_url):
        super().__init__()
        self.base_url, self.vacancies = base_url, {}
        self.stack, self.card, self.capture = [], None, None
        self.card_depth = 0
        self.is_vacancy = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        qa = attrs.get("data-qa", "")
        if tag == "h1" and qa == "vacancy-title":
            self.is_vacancy = True
        if tag in VOID_TAGS:
            return
        self.stack.append(tag)
        depth = len(self.stack)
        if qa == "vacancy-serp__vacancy":
            self.card = {"ID": "", "Ссылка": "", "Заголовок": [], "Компания": []}
            self.card_depth = depth
        if self.card is None:
            return
        if tag == "a" and qa == "serp-item__title":
            try:
                vacancy_id, link = utils.parse_vacancy_link(urljoin(self.base_url, attrs.get("href") or ""))
            except ValueError:
                return
            self.card.update({"ID": vacancy_id, "Ссылка": link})
            self.capture = ("Заголовок", depth)
        elif qa in ("vacancy-serp__vacancy-employer", "vacancy-serp__vacancy-employer-text"):
            # Вложенный текстовый span ограничивает имя компании, исключая значки и рейтинг.
            self.capture = ("Компания", depth)

    def handle_data(self, text):
        if self.capture and not any(tag in ("script", "style") for tag in self.stack):
            self.card[self.capture[0]].append(text)

    def handle_endtag(self, tag):
        if tag not in self.stack:
            return
        # Ищем последний такой тег: div и span могут быть вложены друг в друга.
        depth = len(self.stack) - self.stack[::-1].index(tag)
        if self.capture and depth <= self.capture[1]:
            self.capture = None
        if self.card is not None and depth <= self.card_depth:
            self._finish_card()
        del self.stack[depth - 1:]

    def _finish_card(self):
        """Сохраняет обычный текст без HTML и повторяющихся пробелов."""
        if self.card["ID"]:
            vacancy = dict(self.card)
            for field in ("Заголовок", "Компания"):
                vacancy[field] = " ".join("".join(vacancy[field]).split())
            merge_vacancy(self.vacancies, vacancy)
        self.card, self.capture = None, None


def read_search_vacancies(file_path, base_url):
    """Читает один HTML в UTF-8, включая файлы с BOM."""
    parser = SearchCardsParser(base_url)
    parser.feed(Path(file_path).read_text(encoding="utf-8-sig"))
    parser.close()
    # Рекомендации на странице вакансии не считаем сохранённой поисковой выдачей.
    if parser.is_vacancy:
        raise ValueError("Сохранена страница вакансии. Нужен HTML выдачи поиска hh.")
    if not parser.vacancies:
        raise ValueError("В HTML не найдены карточки поиска hh.")
    return parser.vacancies
