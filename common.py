# common.py
import re

from bs4 import BeautifulSoup, NavigableString

BASE = "http://hw1.alexbers.com"
USER_TOKEN = "39968e0028bf9b17c2d38a8a512b1cb9"


def parse_step(soup: BeautifulSoup) -> tuple[str, str]:
    """
    return (method, path), method ∈ {'GET','POST','POST_FILES'}.
    """
    html = str(soup)

    # "Отправьте POST-запрос по адресу <code>/addr</code>""
    m = re.search(r"Отправьте (POST|GET)-запрос по адресу\s*<code>([^<]+)</code>", html)
    if m:
        return m.group(1), m.group(2)

    # "Загрузите файлы по адресу <code>/addr</code>"
    m = re.search(r"Загрузите файлы по адресу\s*<code>([^<]+)</code>", html)
    if m:
        return "POST_FILES", m.group(1)

    # «...по этой <a href="/ref">ссылке</a>» — считаем это GET
    m = re.search(r"<a href=['\"]([^'\"]+)['\"]>ссылке</a>", html)
    if m:
        return "GET", m.group(1)

    return None, None


def parse_tables(soup: BeautifulSoup):
    """
    Идёт по <body> сверху вниз. Когда видит фразу-"заголовок", то
    запоминает контекст. Следующая за ней таблица кладётся в этот контекст.
    """
    result: dict[str, dict] = {
        "cookie": {},
        "headers": {},
        "query": {},
        "form": {},
        "files": {},
    }
    context = None

    body = soup.body
    if body is None:
        return result

    for child in body.children:
        if isinstance(child, NavigableString):
            text = str(child).lower()
            if "выставлены cookie" in text:
                context = "cookie"
            elif "следующие заголовки" in text:
                context = "headers"
            elif "параметры запроса" in text:
                context = "query"
            elif "данные формы" in text:
                context = "form"
            elif "указанным содержимым" in text:
                context = "files"

        elif getattr(child, "name", None) == "table":
            # поиск названий столбцов
            first_tr = child.find("tr")
            if not first_tr:
                continue
            ths = [th.get_text(strip=True) for th in first_tr.find_all("th")]
            rows = []
            for tr in child.find_all("tr"):  # все строки таблицы
                tds = tr.find_all("td")  # все ячейки строки
                if len(tds) == 2:
                    rows.append(
                        (tds[0].get_text(strip=True), tds[1].get_text(strip=True))
                    )

            # таблица файлов (колонки "Имя файла" / "Содержимое")
            if "Имя файла" in ths and "Содержимое" in ths:
                for name, content in rows:
                    result["files"][name] = content
            elif context:
                for k, v in rows:
                    result[context][k] = v

    return result


def find_token(text):
    """Ищет фразу "токен ..." или "ключ ..." в готовом HTML."""
    m = re.search(r"[Тт]окен[:\s]+(?:<[^>]+>)*([A-Za-z0-9_\-]+)", text)
    if m:
        return m.group(1)
    m = re.search(r"ключ[:\s]+(?:<[^>]+>)*([A-Za-z0-9_\-]+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None
