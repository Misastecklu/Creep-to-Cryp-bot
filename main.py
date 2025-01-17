import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from PIL import Image
import time
from datetime import datetime, timedelta
import random
import pytz
import os
import json
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.dispatcher.router import Router
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.bot import DefaultBotProperties
from aiogram.types import FSInputFile
import aiohttp
import asyncio
import ssl
import certifi

PORT = int(os.getenv("PORT", 5000))  # Render назначает порт через переменную $PORT

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация планировщика
scheduler = AsyncIOScheduler()

# Настройки для Selenium
options = webdriver.ChromeOptions()
options.binary_location = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
options.add_argument('--headless')  # Запуск в режиме без графического интерфейса
options.add_argument('--disable-gpu')  # Отключение GPU (опционально)
options.add_argument('--no-sandbox')  # Для совместимости с некоторыми системами
options.add_argument('--disable-dev-shm-usage')  # Для предотвращения проблем с памятью

# Telegram API Token и ID канала
API_TOKEN = "7606267540:AAFQpNUnwRZbsvVO0HRo0gRgowYHo89gpGE"  # Укажите ваш токен
CHANNEL_ID = "@creep_to_cryp"  # Укажите ID вашего канала

# CoinMarketCap API Key
CMC_API_KEY = 'b429c8fe-031e-4c93-847a-0fcb8353ec60'

# CoinGecko API для Альтсезона
COINGECKO_API_URL = 'https://api.coingecko.com/api/v3/global'

# Укажите путь к файлу для сохранения индекса
ALT_SEASON_FILE_PATH = "alt_season_index.json"

alt_fng_url = "https://api.alternative.me/fng/"

ssl_context = ssl.create_default_context(cafile=certifi.where())

session = AiohttpSession()
bot = Bot(
    token=API_TOKEN,
    session=session,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

router = Router()
dp = Dispatcher()
dp.include_router(router)

# Путь к файлу для хранения предыдущего индекса
ALT_SEASON_FILE_PATH = os.path.join(os.getcwd(), "alt_season_previous.json")

# Путь для скриншотов
SCREENSHOTS_DIR = "/Users/testin/PycharmProjects/Creep_to_Cryp Bot/screenshots"

async def dummy_server():
    app = web.Application()
    async def handle(request):
        return web.Response(text="Bot is running!")
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.getenv('PORT', 8080)))
    await site.start()

# Функция для создания скриншота
def capture_screenshot(url, output_path):
    try:
        # Настройка опций Chrome
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--start-maximized')

        # Запуск драйвера
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # Переход на URL и ожидание загрузки страницы
        driver.get(url)
        # Ожидаем, что страница полностью загрузится
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        # Добавляем небольшую задержку для прогрузки динамических элементов
        time.sleep(10)

        # Путь для сохранения скриншота
        screenshot_path = os.path.join(output_path,f"crypto_bubbles_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.png")

        # Снимаем скриншот
        driver.save_screenshot(screenshot_path)
        print(f"Скриншот сохранен по пути: {screenshot_path}")

        # Устанавливаем права на чтение и запись для всех пользователей
        os.chmod(screenshot_path, 0o666)

        # Завершаем работу драйвера
        driver.quit()

        # Обрезка изображения
        with Image.open(screenshot_path) as img:
            # Размер окна для обрезки
            cropped_img = img.crop((0, 200, 2880, 1355))  # Убедитесь, что эти размеры корректны
            cropped_img.save(screenshot_path)
            print("Изображение обрезано и сохранено.")

        return screenshot_path
    except Exception as e:
        print(f"Ошибка при создании скриншота: {e}")
        return None



async def get_data_from_api():
    data = {}
    cmc_url = 'https://pro-api.coinmarketcap.com/v1/global-metrics/quotes/latest'
    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': CMC_API_KEY,
    }
    crypto_url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest"
    alt_fng_url = "https://api.alternative.me/fng/"
    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        ssl_context.verify_mode = ssl.CERT_OPTIONAL
        ssl_context.check_hostname = False

        async with aiohttp.ClientSession() as session:
            async with session.get(cmc_url, headers=headers, ssl=ssl_context) as global_response:
                global_response.raise_for_status()
                global_data = await global_response.json()

            print("Ответ от CoinMarketCap:", global_data)

            if "data" in global_data:
                data["market_cap"] = f"{global_data['data']['quote']['USD']['total_market_cap'] / 1e12:.2f}T"
                market_cap_change = global_data['data']['quote']['USD'].get("total_market_cap_yesterday_percentage_change", None)
                if market_cap_change is not None:
                    # Изменяем формулировку в зависимости от роста или падения
                    market_cap_phrase = f"{'падение' if market_cap_change < 0 else 'рост'} составило {abs(market_cap_change):.2f}%"
                    # Заменяем "составило" на "составил", если рост
                    if "рост" in market_cap_phrase:
                        market_cap_phrase = market_cap_phrase.replace("составило", "составил")
                    data["market_cap_change"] = market_cap_phrase
                else:
                    data["market_cap_change"] = "Нет данных об изменении капитализации."

                data["btc_dominance"] = f"{global_data['data']['btc_dominance']:.2f}%"
                data["btc_dominance_change"] = global_data['data'].get("btc_dominance_yesterday", 0)
                data["eth_dominance"] = f"{global_data['data']['eth_dominance']:.2f}%"
                data["eth_dominance_change"] = global_data['data'].get("eth_dominance_yesterday", 0)
            else:
                data["market_cap"] = "Ошибка данных из CoinMarketCap"

            symbols = ["BTC", "ETH", "SOL", "TON"]
            params = {"symbol": ",".join(symbols), "convert": "USD"}
            async with session.get(crypto_url, headers=headers, params=params, ssl=ssl_context) as crypto_response:
                crypto_response.raise_for_status()
                crypto_data = await crypto_response.json()

            print("Ответ от CoinMarketCap по криптовалютам:", crypto_data)

            if "data" in crypto_data:
                data["cryptos"] = "\n".join([
                    f"{symbol}: ${crypto_data['data'][symbol]['quote']['USD']['price']:.2f}"
                    for symbol in symbols if symbol in crypto_data['data']
                ])
            else:
                data["cryptos"] = "Ошибка данных о криптовалютах"

            async with session.get(alt_fng_url, ssl=ssl_context) as fng_response:
                fng_response.raise_for_status()
                fng_data = await fng_response.json()

            print("Ответ от Alternative.me:", fng_data)

            if "data" in fng_data and isinstance(fng_data["data"], list) and len(fng_data["data"]) > 0:
                fear_greed_value = fng_data["data"][0]["value"]
                fear_greed_classification = fng_data["data"][0]["value_classification"]
                data["fear_greed_index"] = f"Индекс страха и жадности: {fear_greed_value} ({fear_greed_classification})"
            else:
                data["fear_greed_index"] = "Ошибка данных индекса страха и жадности"

    except aiohttp.ClientError as e:
        print(f"Ошибка при получении данных: {e}")
        data["market_cap"] = "Ошибка получения данных"
        data["market_cap_change"] = "Ошибка получения данных изменения капитализации"
    except Exception as e:
        print(f"Ошибка: {e}")
        data = {"error": str(e)}

    print(f"Отладка данных перед публикацией: {data}")
    return data



# Функция для получения данных об индексе страха и жадности с API
def get_fear_and_greed_index(alt_fng_url):
    """
    Получает индекс страха и жадности с указанного API и формирует сообщение.
    """
    def get_correct_word_form(change):
        """
        Определяет правильную форму слова "пункт" в зависимости от числа.
        """
        if change % 10 == 1 and change % 100 != 11:
            return "пункт"
        elif 2 <= change % 10 <= 4 and not (12 <= change % 100 <= 14):
            return "пункта"
        else:
            return "пунктов"

    try:
        # Запрос к API
        response = requests.get(alt_fng_url, params={"limit": 2, "format": "json"})
        response.raise_for_status()  # Проверка успешности запроса
        data = response.json()

        # Проверка наличия данных
        if not data.get('data') or len(data['data']) < 2:
            raise ValueError("Недостаточно данных от API индекса страха и жадности.")

        # Получение текущих и предыдущих значений
        current_data = data['data'][0]
        previous_data = data['data'][1]

        current_value = int(current_data.get("value", 0))
        value_classification = current_data.get("value_classification", "Неизвестно")

        # Определение зоны
        if current_value <= 19:
            zone = "Экстремальный страх"
        elif current_value <= 39:
            zone = "Страх"
        elif current_value <= 59:
            zone = "Нейтральность"
        elif current_value <= 79:
            zone = "Жадность"
        else:
            zone = "Экстремальная жадность"

        # Вычисление изменения индекса
        previous_value = int(previous_data.get("value", 0))
        change = current_value - previous_value
        if change > 0:
            change_str = f"вырос на {change} {get_correct_word_form(change)}"
        elif change < 0:
            change_str = f"упал на {abs(change)} {get_correct_word_form(abs(change))}"
        else:
            change_str = "не изменился"

        # Формирование итогового сообщения
        result = f"Индекс страха и жадности {change_str}, и находится в зоне \"{zone}\" - {current_value}."
        return result

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе данных API: {e}")
        return "Не удалось получить данные о страхе и жадности. Проверьте подключение к интернету или URL API."
    except Exception as e:
        print(f"Ошибка: {e}")
        return "Произошла ошибка при обработке данных о страхе и жадности."



# Функция для получения данных об индексе альтсезона
def get_alt_season_index():
    try:
        # Запрос к API
        response = requests.get(COINGECKO_API_URL)
        response.raise_for_status()
        data = response.json()

        # Проверяем, что данные корректны
        if 'data' not in data or 'market_cap_percentage' not in data['data']:
            raise ValueError("Ответ API не содержит необходимых данных.")

        # Извлекаем процентное соотношение
        market_cap_percentage = data['data']['market_cap_percentage']
        btc_percentage = market_cap_percentage.get('btc')
        if btc_percentage is None:
            raise ValueError("Данные BTC отсутствуют в ответе API.")

        altcoin_percentage = 100 - btc_percentage

        # Загрузка предыдущего значения индекса
        previous_value = load_previous_alt_season_index()

        # Рассчитываем изменение
        if previous_value is not None:
            change = altcoin_percentage - previous_value
            if change > 0:
                change_text = f"вырос на {abs(change):.2f} пунктов"
            elif change < 0:
                change_text = f"упал на {abs(change):.2f} пунктов"
            else:
                change_text = "не изменился"
        else:
            change_text = ""

        # Сохраняем текущее значение индекса
        save_previous_alt_season_index(altcoin_percentage)

        # Формируем результат
        return altcoin_percentage, change_text

    except requests.RequestException as e:
        print(f"Ошибка соединения с API: {e}")
        return None, "Ошибка подключения к API."

    except Exception as e:
        print(f"Ошибка при обработке данных индекса альтсезона: {e}")
        return None, "Не удалось получить данные."



# Функция для сохранения текущего индекса
def save_previous_alt_season_index(value):
    try:
        # Проверяем, существует ли директория, и создаем её при необходимости
        dir_path = os.path.dirname(ALT_SEASON_FILE_PATH)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path, exist_ok=True)

        # Записываем данные в файл
        with open(ALT_SEASON_FILE_PATH, 'w') as file:
            json.dump({"alt_season_index": value}, file)

        print(f"Индекс альтсезона успешно сохранен: {value}")

    except OSError as e:
        print(f"Ошибка доступа или записи в файл {ALT_SEASON_FILE_PATH}: {e}")
    except Exception as e:
        print(f"Неожиданная ошибка при сохранении индекса альтсезона: {e}")



# Функция для загрузки предыдущего индекса
def load_previous_alt_season_index() -> float | None:
    try:
        with open(ALT_SEASON_FILE_PATH, "r") as file:
            data = json.load(file)
            value = data.get("alt_season_index")
            if value is None:
                print("Файл существует, но значение alt_season_index не найдено.")
            return value
    except FileNotFoundError:
        print(f"Файл {ALT_SEASON_FILE_PATH} не найден. Предыдущее значение отсутствует.")
        return None
    except json.JSONDecodeError as e:
        print(f"Ошибка чтения JSON из файла {ALT_SEASON_FILE_PATH}: {e}")
        return None
    except Exception as e:
        print(f"Неожиданная ошибка при загрузке индекса альтсезона: {e}")
        return None



def add_weekday_emoji(phrase):
    # Проверяем, относится ли фраза к "Сегодня..."
    if phrase and "Сегодня" in phrase:  # Проверка на пустую строку и наличие слова "Сегодня"
        # Определяем текущий день недели
        weekday = datetime.now().weekday()  # 0 - Понедельник, 1 - Вторник, ..., 6 - Воскресенье

        # Словарь дней недели и их соответствующих эмодзи
        weekday_emojis = {
            0: "<tg-emoji emoji-id='5231197925178089666'></tg-emoji>",  # Понедельник
            1: "<tg-emoji emoji-id='5199414711921155936'></tg-emoji>",  # Вторник
            2: "<tg-emoji emoji-id='5203916679460953989'></tg-emoji>",  # Среда
            3: "<tg-emoji emoji-id='5231148142212162509'></tg-emoji>",  # Четверг
            4: "<tg-emoji emoji-id='5244988927726591377'></tg-emoji>",  # Пятница
            5: "<tg-emoji emoji-id='5247087775164932249'></tg-emoji>",  # Суббота
            6: "<tg-emoji emoji-id='5402206854136732611'></tg-emoji>",  # Воскресенье
        }

        # Получаем эмодзи для текущего дня недели
        emoji = weekday_emojis.get(weekday, "")

        # Возвращаем фразу с добавленным эмодзи
        return f"{phrase} {emoji}"
    else:
        # Если фраза не соответствует "Сегодня...", возвращаем её без изменений
        return phrase

# Функция для добавления эмодзи в зависимости от изменения (для роста и падения)
def add_emoji(change, phrase, is_percentage=True):
    # Для процента (is_percentage=True) и для пунктов (is_percentage=False)
    # Условия для фразы "Индекс альтсезона"
    if "Индекс альтсезона" in phrase:
        if "упал" in phrase:
            if change < 4:
                return f"{phrase} <tg-emoji emoji-id='5334970846219882371'></tg-emoji>"
            elif change < 7:
                return f"{phrase} <tg-emoji emoji-id='5327763955521692359'></tg-emoji>"
            elif change < 10:
                return f"{phrase} <tg-emoji emoji-id='5332466704192644976'></tg-emoji>"
            else:
                return f"{phrase} <tg-emoji emoji-id='5330477082067607932'></tg-emoji>"
        elif "вырос" in phrase:
            if change < 4:
                return f"{phrase} <tg-emoji emoji-id='5332373894244345863'></tg-emoji>"
            elif change < 7:
                return f"{phrase} <tg-emoji emoji-id='5332385572260422555'></tg-emoji>"
            elif change < 10:
                return f"{phrase} <tg-emoji emoji-id='5332394832209913514'></tg-emoji>"
            else:
                return f"{phrase} <tg-emoji emoji-id='5334890788029474975'></tg-emoji>"
        elif "не изменился" in phrase:
            return f"{phrase} <tg-emoji emoji-id='5327983338156205610'></tg-emoji>"
        else:
            return phrase  # Возврат без изменений, если слово не подходит


    # Функция для добавления эмодзи в зависимости от изменения
    def emoji_for_change(change, is_percentage=True):
        # Проверка на рост
        if "вырос" in phrase or "рост" in phrase:
            if is_percentage:
                if change >= 3:
                    return f"{phrase} <tg-emoji emoji-id='5220149804708930165'></tg-emoji>" * 3  # 3 эмодзи при изменении >= 3%
                elif change >= 1:
                    return f"{phrase} <tg-emoji emoji-id='5220149804708930165'></tg-emoji>" * 2  # 2 эмодзи при изменении >= 1%
                else:
                    return f"{phrase} <tg-emoji emoji-id='5220149804708930165'></tg-emoji>"  # 1 эмодзи при изменении < 1%
            else:  # Для изменения в пунктах
                if change >= 10:
                    return f"{phrase} <tg-emoji emoji-id='5220149804708930165'></tg-emoji>" * 3  # 3 эмодзи при изменении >= 10 пунктов
                elif change >= 5:
                    return f"{phrase} <tg-emoji emoji-id='5220149804708930165'></tg-emoji>" * 2  # 2 эмодзи при изменении >= 5 пунктов
                else:
                    return f"{phrase} <tg-emoji emoji-id='5220149804708930165'></tg-emoji>"  # 1 эмодзи при изменении < 5 пунктов

        # Проверка на падение
        elif "упал" in phrase or "падение" in phrase:
            if is_percentage:
                if change >= 3:
                    return f"{phrase} <tg-emoji emoji-id='5220015831794067172'></tg-emoji>" * 3  # 3 эмодзи при изменении >= 3%
                elif change >= 1:
                    return f"{phrase} <tg-emoji emoji-id='5220015831794067172'></tg-emoji>" * 2  # 2 эмодзи при изменении >= 1%
                else:
                    return f"{phrase} <tg-emoji emoji-id='5220015831794067172'></tg-emoji>"  # 1 эмодзи при изменении < 1%
            else:  # Для изменения в пунктах
                if change >= 10:
                    return f"{phrase} <tg-emoji emoji-id='5220015831794067172'></tg-emoji>" * 3  # 3 эмодзи при изменении >= 10 пунктов
                elif change >= 5:
                    return f"{phrase} <tg-emoji emoji-id='5220015831794067172'></tg-emoji>" * 2  # 2 эмодзи при изменении >= 5 пунктов
                else:
                    return f"{phrase} <tg-emoji emoji-id='5220015831794067172'></tg-emoji>"  # 1 эмодзи при изменении < 5 пунктов

        return phrase  # Если нет роста или падения, то возвращаем исходную фразу

    return emoji_for_change(change, is_percentage)



def get_russian_month(date):
    """Возвращает дату с русским названием месяца."""
    months = {
        1: "января",
        2: "февраля",
        3: "марта",
        4: "апреля",
        5: "мая",
        6: "июня",
        7: "июля",
        8: "августа",
        9: "сентября",
        10: "октября",
        11: "ноября",
        12: "декабря",
    }
    return date.strftime(f"%d {months[date.month]} %Y года")



# Асинхронная функция для формирования сообщения
async def generate_message(data):
    if not data:
        return "Не удалось получить данные. Проверьте API."

    # Проверяем наличие ключа 'market_cap_change' и извлекаем проценты безопасно
    market_cap_change = data.get('market_cap_change', "0%").split()[-1].replace('%', '')
    try:
        market_cap_change = float(market_cap_change)
    except ValueError:
        market_cap_change = 0.0

    # Формируем фразу о рыночной капитализации
    market_cap_phrase = f"Капитализация рынка равна ${data['market_cap']} - {data['market_cap_change']}."

    # Получение индекса страха и жадности
    fear_greed_phrase = get_fear_and_greed_index(alt_fng_url)

    # Функция для преобразования значения доминации
    def parse_dominance(value):
        if isinstance(value, str):
            return float(value.replace('%', ''))  # Убираем '%' и преобразуем в float
        return float(value)  # Если уже float, просто возвращаем

    # Получение данных текущей и вчерашней доминации
    btc_dominance = parse_dominance(data.get("btc_dominance", "0"))  # Текущая доминация BTC
    btc_dominance_yesterday = parse_dominance(data.get("btc_dominance_change", "0"))  # Доминация BTC за вчера

    eth_dominance = parse_dominance(data.get("eth_dominance", "0"))  # Текущая доминация ETH
    eth_dominance_yesterday = parse_dominance(data.get("eth_dominance_change", "0"))  # Доминация ETH за вчера

    # Расчет изменений
    btc_dominance_diff = btc_dominance - btc_dominance_yesterday
    eth_dominance_diff = eth_dominance - eth_dominance_yesterday

    # Формируем фразы для доминирования BTC
    if btc_dominance_diff > 0:
        btc_change_phrase = f"рост за сутки на {btc_dominance_diff:.2f}%"
    elif btc_dominance_diff < 0:
        btc_change_phrase = f"падение за сутки на {abs(btc_dominance_diff):.2f}%"
    else:
        btc_change_phrase = "без изменений за сутки"
    btc_dominance_phrase = f"Доминирование BTC составляет {btc_dominance:.2f}% - {btc_change_phrase}."

    # Формируем фразы для доминирования ETH
    if eth_dominance_diff > 0:
        eth_change_phrase = f"рост за сутки на {eth_dominance_diff:.2f}%"
    elif eth_dominance_diff < 0:
        eth_change_phrase = f"падение за сутки на {abs(eth_dominance_diff):.2f}%"
    else:
        eth_change_phrase = "без изменений за сутки"
    eth_dominance_phrase = f"Доминирование ETH составляет {eth_dominance:.2f}% - {eth_change_phrase}."

    # Индекс альтсезона
    alt_season_index, alt_season_change_text = get_alt_season_index()
    if alt_season_index is not None:
        if alt_season_change_text:
            alt_season_phrase = (
                f"Индекс альтсезона за сутки {alt_season_change_text} - {int(alt_season_index)}/100."
            )
        else:
            alt_season_phrase = f"Индекс альтсезона за сутки не изменился - {int(alt_season_index)}/100."

    # Получение текущей даты с русским месяцем
    current_date = get_russian_month(datetime.now())


    custom_emoji_1 = "<tg-emoji emoji-id='5039972988884092041'></tg-emoji>"
    custom_emoji_2 = "<tg-emoji emoji-id='5345970124320941088'></tg-emoji>"

    return (
        f"<b>Короче говоря!</b>\n\n"
        f"Сегодня {current_date}.\n\n"
        f"{market_cap_phrase}\n\n"
        f"{fear_greed_phrase}\n\n"
        f"{btc_dominance_phrase}\n\n"
        f"{eth_dominance_phrase}\n\n"
        f"{alt_season_phrase}\n\n"
        f"Курсы криптовалют:\n{data.get('cryptos', 'Нет данных о криптовалютах.')}\n\n"
        f"<b>Я торгую на <a href='https://www.bybit.com/invite?ref=3XJXDLW'>Bybit</a></b>{custom_emoji_1}\n\n"
        f"<b>Подписывайтесь в <a href='https://t.me/creep_to_cryp'>Telegram</a></b>{custom_emoji_2}"
    )

async def post_to_channel():
    try:
        # Получаем данные из API асинхронно
        data = await get_data_from_api()

        # Проверка на успешный ответ от API
        if not data:
            print("Не удалось получить данные от API.")
            return

        # Генерация сообщения
        message = await generate_message(data)
        print(f"Отладка перед отправкой: {message}")

        # Создание скриншота
        screenshot_path = capture_screenshot("https://cryptobubbles.net/", "./screenshots")

        # Проверка на наличие пути к файлу
        if screenshot_path:
            try:
                # Создаем объект FSInputFile для скриншота
                photo_input = FSInputFile(screenshot_path)

                # Отправка фото с текстом в одном сообщении
                await bot.send_photo(chat_id=CHANNEL_ID, photo=photo_input, caption=message, parse_mode="HTML")
                print("Фото и сообщение отправлены в канал.")
            except Exception as e:
                print(f"Ошибка при отправке скриншота: {e}")

    except Exception as e:
        # Логирование ошибки для отладки
        print(f"Ошибка при публикации в канал: {e}")
        await asyncio.sleep(1)



# Функция для генерации случайного времени для публикации
def random_post_schedule(scheduler):
    # Устанавливаем Московское время
    msk_timezone = pytz.timezone("Europe/Moscow")
    current_time = datetime.now(msk_timezone)

    # Генерируем случайное время в промежутке с 09:00 до 09:15
    start_time = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(minutes=15)

    # Случайное время в этом интервале
    random_time = start_time + timedelta(minutes=random.randint(0, 15))

    # Планируем задачу на случайное время
    # Мы используем IntervalTrigger для планирования задачи на каждый день в случайное время
    trigger = IntervalTrigger(start_date=random_time, hours=24, timezone=msk_timezone)
    scheduler.add_job(post_to_channel, trigger)
    print(f"Публикация будет выполнена в {random_time.strftime('%H:%M')} по МСК.")



# Основной запуск
async def main():
    # Создаем планировщик задач
    scheduler = AsyncIOScheduler()
    scheduler.start()

    # Запускаем задачу по публикации в случайное время
    random_post_schedule(scheduler)

    await dp.start_polling(bot)



# Запуск асинхронной функции
if __name__ == "__main__":
    asyncio.run(main())


