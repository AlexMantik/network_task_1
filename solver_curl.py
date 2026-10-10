# solver_curl.py
import os
import subprocess
import tempfile
import time

from bs4 import BeautifulSoup

from common import BASE, USER_TOKEN, find_token, parse_step, parse_tables


def run_curl(extra_args, timeout=60):
    """
    Запускает curl с переданными аргументами
    returns (status_code, body_text).
    тело кладём в tmp-файл через -o, статус вытаскиваем через -w.
    """
    with tempfile.NamedTemporaryFile(delete=False) as f:
        body_path = f.name

    cmd = [
        "curl",
        "-sS",  # -sS: silent, show errors;
        "-L",  # -L: follow redirects
        "--no-keepalive",  # после запроса закрыть соединение
        "-m",
        str(timeout),
        "-o",
        body_path,  # тело ответа во временный файл
        "-w",
        "%{http_code}",  # %{http_code} - шаблон курла
    ] + extra_args

    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout + 30)
        status_str = res.stdout.decode("utf-8", "replace").strip()
        # если было несколько редиректов, curl может печатать несколько кодов. берём последний
        status = int(status_str.split()[-1]) if status_str else 0
        with open(body_path, "r", encoding="utf-8", errors="replace") as fh:
            body = fh.read()
        return status, body
    finally:
        try:
            os.unlink(body_path)
        except OSError:
            pass


def cookie_str(cookies):
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


def curl_get(url, cookies, headers, query):
    args = ["-b", cookie_str(cookies)]
    for k, v in headers.items():
        args += ["-H", f"{k}: {v}"]
    if query:
        args += ["-G"]
        for k, v in query.items():
            args += ["--data-urlencode", f"{k}={v}"]
    args += [url]
    return run_curl(args)


def curl_post_form(url, cookies, headers, query, form):
    args = ["-X", "POST", "-b", cookie_str(cookies)]
    for k, v in headers.items():
        args += ["-H", f"{k}: {v}"]
    if query:
        # query-параметры в URL, а не в теле — поэтому вручную вклеим в URL
        from urllib.parse import urlencode

        url = url + (
            "?" + urlencode(query) if "?" not in url else "&" + urlencode(query)
        )
    for k, v in form.items():
        args += ["--data-urlencode", f"{k}={v}"]
    args += [url]
    return run_curl(args)


def curl_post_files(url, cookies, headers, files):
    # файлы из таблицы записываем на диск, чтобы curl мог их отправить через -F
    tmpdir = tempfile.mkdtemp(prefix="hw1_files_")
    try:
        args = ["-X", "POST", "-b", cookie_str(cookies)]
        for k, v in headers.items():
            args += ["-H", f"{k}: {v}"]
        for name, content in files.items():
            p = os.path.join(tmpdir, name)
            with open(p, "wb") as f:
                f.write(content.encode("utf-8"))
            args += ["-F", f"file=@{p};type=application/octet-stream"]
        args += [url]
        return run_curl(args, timeout=120)
    finally:
        import shutil

        shutil.rmtree(tmpdir, ignore_errors=True)


def with_retries(fn, *args, attempts=5, **kwargs):
    last = None
    for i in range(attempts):
        try:
            status, body = fn(*args, **kwargs)
            if status == 200:
                return body
            print(f"  ! статус {status}, попытка {i + 1}/{attempts}")
            last = f"status={status}"
        except subprocess.TimeoutExpired as e:
            print(f"  ! timeout, попытка {i + 1}/{attempts}")
            last = e
        time.sleep(3)
    raise RuntimeError(f"не удалось: {last}")


def main():
    print("GET /")
    body = with_retries(
        curl_get,
        BASE + "/",
        {"user": USER_TOKEN},
        {"Connection": "close"},
        {},
    )

    for step in range(500):
        token = find_token(body)
        if token:
            print("=" * 60)
            print("TOKEN:", token)
            print("=" * 60)
            return

        soup = BeautifulSoup(body, "html.parser")
        method, path = parse_step(soup)
        if not path:
            print("Не понял шаг. Вот хвост:")
            print(body[:2000])
            return

        tables = parse_tables(soup)
        cookies = {"user": USER_TOKEN}
        cookies.update(tables["cookie"])
        headers = dict(tables["headers"])
        headers.setdefault("Connection", "close")

        url = BASE + path
        print(
            f"[{step}] {method} {path}  "
            f"query={len(tables['query'])} hdr={len(headers)} "
            f"form={len(tables['form'])} files={len(tables['files'])}"
        )

        if method == "GET":
            body = with_retries(curl_get, url, cookies, headers, tables["query"])
        elif method == "POST":
            body = with_retries(
                curl_post_form, url, cookies, headers, tables["query"], tables["form"]
            )
        elif method == "POST_FILES":
            body = with_retries(curl_post_files, url, cookies, headers, tables["files"])
        else:
            print("Неизвестный метод:", method)
            return

    print("Токен не найден за 500 шагов")


if __name__ == "__main__":
    main()
