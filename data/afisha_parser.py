import requests
import re
import os
import pandas as pd
import shutil
import logging
from bs4 import BeautifulSoup
import psycopg2

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

urls = [
    "https://www.afisha.ru/spb/cinema/",
    "https://www.afisha.ru/spb/theatre/",
    "https://www.afisha.ru/spb/concerts/",
    "https://www.afisha.ru/spb/exhibitions/",
    "https://www.afisha.ru/msk/cinema/",
    "https://www.afisha.ru/msk/theatre/",
    "https://www.afisha.ru/msk/concerts/",
    "https://www.afisha.ru/msk/exhibitions/"
]

def get_afisha_events():
    def fetch_data(url):
        logging.info(f"Обрабатываю URL: {url}")
        data = []

        try:
            response = requests.get(url)
            response.raise_for_status()
            response_text = response.text
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при выполнении запроса для {url}: {e}")
            return pd.DataFrame(columns=["name", "description", "image", "town", "type"])

        pattern = re.compile(
            r'{"name":"(?P<name>.*?)",.*?"image":"(?P<image>.*?)",.*?"url":"(?P<url>.*?)"'
        )

        def get_description(detail_url):
            try:
                response = requests.get(detail_url)
                response.raise_for_status()
                html_content = response.text
                soup = BeautifulSoup(html_content, "html.parser")
                description_container = soup.find("div", class_="aEVDY t1V2l")
                if description_container:
                    return description_container.get_text(strip=True)
                else:
                    return ""
            except requests.exceptions.RequestException as e:
                return f"Ошибка запроса: {e}"
            except Exception as e:
                return f"Ошибка: {e}"

        try:
            for match in pattern.finditer(response_text):
                full_url = "https://www.afisha.ru" + match.group("url")
                data.append({
                    "name": match.group("name"),
                    "description": get_description(full_url),
                    "image": match.group("image"),
                    "url": full_url
                })
        except Exception as e:
            logging.error(f"Ошибка при парсинге данных для {url}: {e}")
            return pd.DataFrame(columns=["name", "description", "image", "town", "type"])

        try:
            df = pd.DataFrame(data, columns=["name", "description", "image"])
            if df.empty:
                logging.warning(f"Данные не найдены или не удалось их распарсить для {url}.")
            else:
                if "spb" in url:
                    df["town"] = "Санкт-Петербург"
                else:
                    df["town"] = "Москва"
                if "cinema" in url:
                    df["type"] = "cinema"
                elif "theatre" in url:
                    df["type"] = "theatre"
                elif "concerts" in url:
                    df["type"] = "concerts"
                elif "exhibitions" in url:
                    df["type"] = "exhibitions"
            logging.info(f"Закончил обработку URL: {url}\n_____________________________________________________________________________________________")
            return df
        except Exception as e:
            logging.error(f"Ошибка при создании DataFrame для {url}: {e}")
            return pd.DataFrame(columns=["name", "description", "image", "town", "type"])

    parsed_data = pd.DataFrame()
    for url in urls:
        logging.info(f"Начинаю обработку URL: {url}")
        df = fetch_data(url)
        parsed_data = pd.concat([parsed_data, df], ignore_index=True)

    logging.info("Завершена обработка всех URL")

    def make_correct_url(url):
        match = re.search(r'(https?://\S+\.(?:jpg|jpeg|png|gif|webp))', url)
        if match:
            return match.group(1)
        return None

    def clean_df(df):
        def has_unwanted_chars(description):
            if not isinstance(description, str):
                return False
            if re.search(r"<[^>]*>", description):
                return True
            return False
        df_cleaned = df[~df['description'].apply(has_unwanted_chars) & df['description'].str.strip().astype(bool)]
        return df_cleaned

    def replace_illegal_characters(text):
        if isinstance(text, str):
            return ''.join(char if char.isprintable() else ' ' for char in text)
        return text

    clean_data = (clean_df(parsed_data)
                .assign(image=lambda x: x['image'].apply(make_correct_url),
                        description=lambda x: x['description'].apply(replace_illegal_characters))
                .drop_duplicates(subset=['name', 'town', 'type'])
                .reset_index(drop=True))

    logging.info("Датафрейм очищен")

    image_folder = "images"
    paths = []

    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    def download_image(url, folder, filename):
        try:
            response = requests.get(url)
            response.raise_for_status()

            file_path = os.path.join(folder, filename)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return file_path
        except requests.exceptions.RequestException as e:
            logging.error(f"Ошибка при скачивании {url}: {e}")
            if response is not None:
                logging.error(f"Ответ сервера: {response.status_code} - {response.text[:100]}")
            return None

    for index, row in clean_data.iterrows():
        image_url = row["image"]
        if pd.notna(image_url) and isinstance(image_url, str):
            if image_url:
                filename = f"image_{index}.jpg"
                logging.info(f"Скачиваю картинку {image_url}")
                file_path = download_image(image_url, image_folder, filename)
                if file_path:
                    paths.append(file_path)
                else:
                    paths.append(None)
            else:
                logging.warning(f"Некорректный URL: {image_url}")
                paths.append(None)
        else:
            paths.append(None)

    clean_data['path'] = paths
    clean_data.drop(columns=['image'], inplace=True)

    logging.info("Скачивание картинок завершено, подготовлены качественные данные для загрузки в базу данных")

    try:
        conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host="localhost"
        )
        cursor = conn.cursor()
        logging.info("Подключение к базе данных успешно выполнено")
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")

    query = """
    CREATE TABLE IF NOT EXISTS events (
        name TEXT NOT NULL UNIQUE,
        description TEXT NOT NULL,
        town VARCHAR(100) NOT NULL,
        type VARCHAR(100) NOT NULL,
        path TEXT
    );
    """

    try:
        cursor.execute(query)
        conn.commit()
        logging.info("Таблица создана или уже существует")
    except Exception as e:
        logging.error(f"Ошибка при создании таблицы: {e}")

    def insert_data(df, conn):
        try:
            for index, row in df.iterrows():
                cursor.execute("""
                    INSERT INTO events (name, description, town, type, path)
                    VALUES (%s, %s, %s, %s, %s)
                """, (row['name'], row['description'], row['town'], row['type'], row['path']))
            conn.commit()
            logging.info("Данные успешно записаны в базу данных")
        except Exception as e:
            logging.error(f"Ошибка при записи данных: {e}")
            conn.rollback()

    insert_data(clean_data, conn)

    cursor.close()
    conn.close()
    logging.info("Соединение с базой данных закрыто")

    logging.info("Функция get_afisha_events() отработала, данные с афиши успешно загружены в базу данных")

if __name__ == "__main__":
    load_dotenv()
    get_afisha_events()
