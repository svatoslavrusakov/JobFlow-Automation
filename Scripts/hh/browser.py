# browser.py

import json
import subprocess
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.selenium_manager import SeleniumManager
from urllib3.exceptions import HTTPError

from core import config
from hh import captcha
from core import stop_control
from core.settings_store import check_timeout


def read_chrome_version(address=None, timeout=None):
    """Проверяет порт уже открытого Chrome до запуска Selenium."""
    timeout = check_timeout(config.CHROME_DEBUG_TIMEOUT if timeout is None else timeout, "CHROME_DEBUG_TIMEOUT")
    # Локальное подключение не направляем через системный прокси.
    opener = build_opener(ProxyHandler({}))
    address = f"http://{address or config.CHROME_DEBUG_PORT}/json/version"
    with opener.open(address, timeout=timeout) as response:
        product = json.load(response).get("Browser", "")
    version = product.rsplit("/", 1)[-1]
    if not version or not all(part.isdigit() for part in version.split(".")):
        raise ValueError("На указанном порту не найдена версия Chrome.")
    return version


def find_chromedriver(browser_version):
    """Использует готовый совместимый драйвер; при его отсутствии подбирает новый."""
    manager = SeleniumManager()
    args = [
        "--browser", "chrome", "--browser-version", browser_version,
        "--avoid-browser-download", "--avoid-stats",
    ]
    try:
        cached = manager.binary_paths(args + ["--offline"])
        path = Path(cached.get("driver_path", ""))
        if path.is_file():
            info = subprocess.run(
                [str(path), "--version"], capture_output=True, text=True,
                check=True, timeout=config.CHROME_DEBUG_TIMEOUT,
            ).stdout.split()
            # Сверяем сборку реально запущенного Chrome, включая major.minor.build.
            if len(info) > 1 and info[1].split(".")[:3] == browser_version.split(".")[:3]:
                print(f"Использую установленный ChromeDriver {info[1]}.")
                return str(path)
    except (WebDriverException, OSError, subprocess.SubprocessError):
        # При пустом или устаревшем кэше остаётся обычный подбор Selenium.
        pass

    stop_control.check()
    timeout = config.CHROMEDRIVER_NETWORK_TIMEOUT
    print(f"Готового драйвера нет. Подбор/загрузка: сетевой тайм-аут {timeout} с.")
    return manager.binary_paths(args + ["--timeout", str(timeout)])["driver_path"]


def connect_browser():
    """Подключается к открытому Chrome; при ошибке возвращает None."""
    options = Options()
    # Адрес Chrome берём из общей настройки для обоих сценариев.
    options.add_experimental_option("debuggerAddress", config.CHROME_DEBUG_PORT)

    try:
        stop_control.check()
        check_timeout(config.CHROMEDRIVER_NETWORK_TIMEOUT, "CHROMEDRIVER_NETWORK_TIMEOUT")
        print(f"Проверяю Chrome на {config.CHROME_DEBUG_PORT}…")
        version = read_chrome_version()
        print(f"Chrome {version} доступен. Подбираю драйвер…")
        path = find_chromedriver(version)
        stop_control.check()
        driver = webdriver.Chrome(service=Service(path), options=options)
        print("Подключение к Chrome установлено.")
        return driver
    except (WebDriverException, HTTPError, OSError, ValueError, KeyError) as error:
        print(f"Не удалось подключиться к Chrome: {error}")
        print(f"Запустите Chrome с --remote-debugging-port={config.CHROME_DEBUG_PORT.rsplit(':', 1)[-1]} по команде из README.")
        return None


def login_form_visible(driver):
    """Возвращает True, если hh показывает настоящую форму входа."""
    forms = driver.find_elements(
        By.CSS_SELECTOR, '[data-qa="account-login-form"]',
    )
    return any(form.is_displayed() for form in forms)


def check_authorization(driver):
    """Останавливает работу, если hh требует авторизацию."""
    # Капча может лежать поверх обычной вакансии с видимым описанием.
    captcha.stop_if_visible(driver)
    contents = driver.find_elements(
        By.CSS_SELECTOR, 'main [data-qa="main-content"]',
    )
    for content in contents:
        if not content.is_displayed():
            continue

        text = " ".join(content.text.split()).casefold()
        # Недоступная вакансия тоже может содержать форму входа.
        if "вам недоступна эта вакансия" in text:
            return

    if login_form_visible(driver):
        raise PermissionError("hh требует входа. Проверьте авторизацию.")


def switch_to_new_tab(driver, previous_handles):
    """Переключается во вкладку, появившуюся после действия программы."""
    opened = set(driver.window_handles) - previous_handles
    if len(opened) > 1:
        raise RuntimeError("Открылось несколько вкладок. Проверьте браузер.")
    if opened:
        driver.switch_to.window(opened.pop())


def close_new_tabs(driver, previous_handles, original_window):
    """Закрывает вкладки текущего отклика и возвращается в исходную."""
    for handle in set(driver.window_handles) - previous_handles:
        driver.switch_to.window(handle)
        driver.close()
    driver.switch_to.window(original_window)


def launch_browser(values):
    """Открывает отдельный профиль Chrome только по кнопке пользователя."""
    from core.settings_store import resolve_path
    host, port = values["chrome_address"].rsplit(":", 1)
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Кнопка запуска предназначена для локального Chrome.")
    executable = resolve_path(values["chrome_executable"])
    if not executable.is_file():
        raise ValueError("Не найден chrome.exe; выберите его в настройках.")
    subprocess.Popen([
        str(executable), f"--remote-debugging-port={port}",
        f"--user-data-dir={resolve_path(values['chrome_profile'])}", "https://hh.ru",
    ])
