# solver_requests.py
import time

import requests
from bs4 import BeautifulSoup

from common import BASE, USER_TOKEN, find_token, parse_step, parse_tables


def do_get(url, cookies, headers, query):
    return requests.get(
        url,
        params=query or {},
        headers=headers,
        cookies=cookies,
        timeout=30,
        allow_redirects=True,
    )


def do_post_form(url, cookies, headers, query, form):
    return requests.post(
        url,
        params=query or {},
        data=form or {},
        headers=headers,
        cookies=cookies,
        timeout=30,
        allow_redirects=True,
    )


def do_post_files(url, cookies, headers, files):
    # {'filename': 'content'}
    parts = [
        ("file", (name, content.encode("utf-8"), "application/octet-stream"))
        for name, content in files.items()
    ]
    return requests.post(
        url,
        files=parts,
        headers=headers,
        cookies=cookies,
        timeout=60,
        allow_redirects=True,
    )


def request_with_retries(fn, *args, attempts=5, **kwargs):
    last = None
    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except (requests.ConnectionError, requests.Timeout) as e:
            print(f"  ! попытка {i + 1}/{attempts}: {type(e).__name__}")
            last = e
            time.sleep(2)
    raise last


def main():
    print("GET /")
    r = request_with_retries(
        do_get,
        BASE + "/",
        cookies={"user": USER_TOKEN},
        headers={"Connection": "close"},
        query={},
    )

    for step in range(500):
        token = find_token(r.text)
        if token:
            print("=" * 60)
            print("TOKEN:", token)
            print("=" * 60)
            return

        soup = BeautifulSoup(r.text, "html.parser")
        method, path = parse_step(soup)
        if not path:
            print("Ошибка. Вот хвост ответа:")
            print(r.text[:2000])
            return

        # Что нести с собой?
        tables = parse_tables(soup)
        cookies = {"user": USER_TOKEN}  # ретрай куки
        cookies.update(tables["cookie"])  # + одноразовые печеньки этого шага
        headers = dict(tables["headers"])
        headers.setdefault("Connection", "close")

        url = BASE + path
        print(
            f"[{step}] {method} {path}  "
            f"query={len(tables['query'])} hdr={len(headers)} "
            f"form={len(tables['form'])} files={len(tables['files'])}"
        )

        # Запрос
        if method == "GET":
            r = request_with_retries(do_get, url, cookies, headers, tables["query"])
        elif method == "POST":
            r = request_with_retries(
                do_post_form, url, cookies, headers, tables["query"], tables["form"]
            )
        elif method == "POST_FILES":
            r = request_with_retries(
                do_post_files, url, cookies, headers, tables["files"]
            )
        else:
            print("Неизвестный метод:", method)
            return

        if r.status_code != 200:
            print("Ошибка:", r.status_code)
            print(r.text[:2000])
            return

    print("Токен не найден за 500 шагов")


if __name__ == "__main__":
    main()
