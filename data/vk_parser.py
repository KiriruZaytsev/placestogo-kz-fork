import requests
import json
import os
import psycopg2
from psycopg2 import pool
import concurrent.futures
import time
import re
from termcolor import colored

from dotenv import load_dotenv

# Переменные
TOKEN_USER = "cad5ddd7cad5ddd7cad5ddd728c9f2f736ccad5cad5ddd7adac85db23313ee3952317f9"
VERSION = "5.199"
DOMAINS = {"kudago": "Москва", "kudagospb": "Санкт-Петербург"}

# Настройки подключения к PostgreSQL
load_dotenv()
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = os.getenv("POSTGRES_DB")
DB_USER = os.getenv("POSTGRES_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD")

# Создаем папки для сохранения
os.makedirs('images', exist_ok=True)

# Пул соединений
db_pool = None

# Логирование с уровнями и цветами
def log(message, level="INFO"):
    colors = {"INFO": "green", "WARNING": "yellow", "ERROR": "red"}
    print(colored(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}", colors.get(level, "white")))

# Инициализация базы данных и пула соединений
def initialize_database():
    global db_pool
    try:
        log("Создание пула соединений к базе данных...")
        db_pool = psycopg2.pool.SimpleConnectionPool(1, 10,
                                                     host=DB_HOST,
                                                     port=DB_PORT,
                                                     dbname=DB_NAME,
                                                     user=DB_USER,
                                                     password=DB_PASSWORD)
        if db_pool:
            log("Пул соединений успешно создан.")
        else:
            log("Ошибка при создании пула соединений.", level="ERROR")
            exit(1)

        log("Подключение к базе данных для инициализации таблицы...")
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                town VARCHAR(100) NOT NULL,
                type VARCHAR(100) NOT NULL,
                path TEXT
            );
        ''')
        conn.commit()
        cursor.close()
        db_pool.putconn(conn)
        log("Инициализация базы данных завершена успешно.")
    except Exception as e:
        log(f"Ошибка при инициализации базы данных: {e}", level="ERROR")
        exit(1)

# Обработка одного поста
def process_post(item, domain, city, cursor):
    text = item.get('text', '')
    max_image_url = None
    image_filename = None

    title = re.sub(r'\[.*?\||\]|http[s]?://\S+', '', text.split('\n')[0]).strip()
    full_text = text.replace(title, '').strip()

    # Проверяем дубликат до скачивания изображения
    cursor.execute('SELECT 1 FROM events WHERE name = %s;', (title,))
    if cursor.fetchone():
        log(f"Пост пропущен как дубликат: {title}", level="WARNING")
        return

    attachments = item.get('attachments', [])
    for attachment in attachments:
        if attachment['type'] == 'photo':
            sizes = attachment['photo'].get('sizes', [])
            max_image = max(sizes, key=lambda x: x['width'] * x['height'])
            max_image_url = max_image.get('url')

            if max_image_url:
                image_filename = f"images/{domain}_post_{item['id']}.jpg"
                img_data = requests.get(max_image_url).content
                with open(image_filename, 'wb') as img_file:
                    img_file.write(img_data)
                log(f"Изображение сохранено: {image_filename}")
            break

    cursor.execute(
        'INSERT INTO events (town, name, description, path, type) VALUES (%s, %s, %s, %s, %s);',
        (city, title, full_text, image_filename if image_filename else "", 'event')
    )
    log(f"Пост добавлен в базу данных: {title}")

# Загрузка и обработка записей с retry
def fetch_and_process_posts(domain, city, cursor, count, offset):
    try:
        log(f"Запрос к API VK для {domain} с offset {offset}")
        response = requests.get('https://api.vk.com/method/wall.get',
                                params={'access_token': TOKEN_USER,
                                        'v': VERSION,
                                        'domain': domain,
                                        'count': count,
                                        'offset': offset,
                                        'filter': 'owner'})
        response.raise_for_status()
        data = response.json()
        items = data['response']['items']

        if not items:
            log(f"Нет больше записей для {domain}", level="INFO")
            return False, offset

        for item in items:
            process_post(item, domain, city, cursor)
        cursor.connection.commit()
        return True, offset + len(items)
    except requests.exceptions.RequestException as e:
        log(f"Ошибка при запросе к API VK: {e}", level="ERROR")
        time.sleep(5)
        return True, offset

# Обработка домена
def process_domain(domain, city):
    try:
        log(f"Обработка домена: {domain}")
        conn = db_pool.getconn()
        cursor = conn.cursor()
        process_old_posts = True
        offset = 0
        while True:
            if process_old_posts:
                has_old_posts, offset = fetch_and_process_posts(domain, city, cursor, count=100, offset=offset)
                if not has_old_posts:
                    process_old_posts = False
                    offset = 0
            else:
                has_new_posts, _ = fetch_and_process_posts(domain, city, cursor, count=2, offset=0)
                if not has_new_posts:
                    time.sleep(300)
        cursor.close()
        db_pool.putconn(conn)
    except Exception as e:
        log(f"Ошибка обработки домена {domain}: {e}", level="ERROR")

initialize_database()
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    executor.map(process_domain, DOMAINS.keys(), DOMAINS.values())
