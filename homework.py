import logging
import os
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv

import requests

from exceptions import StatusError, APIStatusCodeError, SendMessageError

from telegram import Bot, TelegramError


load_dotenv()


PRACTICUM_TOKEN = os.getenv('TOKEN_PRAKT')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('MY_CHAD_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


def check_tokens() -> bool:
    """Проверяет наличие всех переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.info(f'Попытка отправки сообщения {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение успешно отправлено')
        return True
    except TelegramError as error:
        logging.error(error)
        return False


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ."""
    timestamp = timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Эндпоинт {ENDPOINT} недоступен: {error}'
        logger.error(message)
        raise APIStatusCodeError(message)
    if homework_statuses.status_code != HTTPStatus.OK:
        message = f'Код ответа API: {homework_statuses.status_code}'
        logger.error(message)
        raise APIStatusCodeError(message)
    try:
        return homework_statuses.json()
    except Exception as error:
        message = f'Ошибка преобразования в формат json: {error}'
        logger.error(message)
        raise APIStatusCodeError(message)


def check_response(response):
    """Проверяет наличие всех ключей в ответе API."""
    logging.info('Проверка ответа от API начата')

    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ от API не является словарём: response = {response}'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(
            'В ответе от API homeworks не список, '
            f'response = {response}'
        )
    current_date = response.get('current_date')
    if not isinstance(current_date, int):
        raise TypeError(
            'В ответе от API  пришло не число, '
            f'current_date = {current_date}'
        )

    return homeworks


def parse_status(homework):
    """Извлекает статус домашней работы."""
    if homework.get('homework_name') is None:
        message = 'Словарь ответа API не содержит ключа homework_name'
        raise KeyError(message)
    elif homework.get('status') is None:
        message = 'Словарь ответа API не содержит ключа status'
        raise KeyError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if homework_status not in HOMEWORK_VERDICTS:
        message = f'Статус {homework_status} неизвестен'
        raise StatusError(message)

    homework_name = homework['homework_name']
    verdict = HOMEWORK_VERDICTS.get(homework_status)

    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    logging.debug(message)

    return message


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = (
            'Отсутствуют обязательные переменные окружения: '
            'Программа принудительно остановлена'
        )
        logging.critical(error_message)
        sys.exit(error_message)

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    current_report = None
    prev_report = current_report

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response['current_date']
            homeworks = check_response(response)
            homework = homeworks[0]
            current_report = send_message(bot, parse_status(homework))

            if current_report == prev_report:
                logger.debug(
                    'Нет обновлений статуса домашней работы'
                )
        except SendMessageError as error:
            logger.error(error)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logger.error(message)
        else:
            logger.info('функция main полностью сработала')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
