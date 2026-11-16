import time
import random
import re
import gspread
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# --- НАСТРОЙКИ ---
SEARCH_URL = "https://rostov.hh.ru/search/vacancy?area=76&from=header-menu&hhtmFromLabel=header&hhtmFrom=suitable_vacancies"
CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = "HH_Vacancies_Analytics"

BLACK_LIST = []

def human_delay(min_sec, max_sec):
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)

def get_vacancy_id(url):
    match = re.search(r'/vacancy/(\d+)', url)
    return match.group(1) if match else None

def init_google_sheet():
    try:
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        sh = gc.open(SPREADSHEET_NAME).sheet1
        existing_ids = set(sh.col_values(1))
        print(f"📁 Из Google Таблицы успешно загружено {len(existing_ids)} ранее сохраненных ID.\n")
        return sh, existing_ids
    except Exception as e:
        print(f"❌ Ошибка подключения к Google Таблице: {e}")
        return None, set()

def process_vacancies():
    sheet, existing_ids = init_google_sheet()
    if not sheet:
        return

    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    driver = webdriver.Chrome(options=options)
    
    print(f"🚀 Открываю поиск: {SEARCH_URL}")
    driver.get(SEARCH_URL)
    human_delay(4.0, 7.0)

    # --- ФАЗА 1: СОБИРАЕМ ДАННЫЕ В ПАМЯТЬ PYTHON (без переходов по ссылкам) ---
    cards = driver.find_elements(By.CSS_SELECTOR, 'a[data-qa="serp-item__title"]')
    print(f"🔍 Найдено карточек на странице: {len(cards)}\n")

    vacancies_to_process = []
    for card in cards:
        try:
            title = card.text.strip()
            raw_link = card.get_attribute('href')
            clean_link = raw_link.split('?')[0]
            vacancy_id = get_vacancy_id(clean_link)
            
            if vacancy_id and title:
                vacancies_to_process.append({
                    'id': vacancy_id,
                    'title': title,
                    'link': clean_link
                })
        except Exception:
            continue

    # --- ФАЗА 2: ОБРАБАТЫВАЕМ СОБРАННЫЙ СПИСОК ---
    for item in vacancies_to_process:
        vacancy_id = item['id']
        title = item['title']
        clean_link = item['link']

        # 1. Черный список по заголовку
        if any(bad_word in title.lower() for bad_word in BLACK_LIST):
            print(f"[-] ПРОПУСК (Черный список): {title}")
            continue

        # 2. Проверка на дубликат в Google Таблице
        if vacancy_id in existing_ids:
            print(f"[=] ДУБЛИКАТ (ID {vacancy_id} уже в таблице): {title}")
            print("    Немного ждем и идем к следующей...")
            human_delay(1.5, 3.0)
            continue

        # 3. Переход на НОВУЮ вакансию
        print(f"\n[+] НОВАЯ ВАКАНСИЯ! Открываю (ID: {vacancy_id}): {title}")
        driver.get(clean_link)
        human_delay(3.0, 6.0)

        # Скроллинг (имитация чтения)
        driver.execute_script("window.scrollBy(0, 1000);")
        human_delay(2.0, 4.0)

        # Сбор описания
        try:
            description = driver.find_element(By.CSS_SELECTOR, '[data-qa="vacancy-description"]').text
        except Exception:
            description = "Не удалось извлечь описание"

        # 4. Запись в Google Таблицу
        row_data = [vacancy_id, title, description, clean_link]
        sheet.append_row(row_data)
        
        # Запоминаем ID в памяти текущего сеанса
        existing_ids.add(vacancy_id)
        print(f"    ✅ ЗАПИСАНО В GOOGLE ТАБЛИЦУ (ID: {vacancy_id})")

        # Безопасная пауза перед следующей вакансией
        human_delay(15.0, 30.0)

    print("\n🎉 Все вакансии со страницы успешно обработаны!")

if __name__ == "__main__":
    process_vacancies()