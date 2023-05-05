class StatusError(Exception):
    """Ошибка статуса домашней работы."""

    pass


class APIStatusCodeError(Exception):
    """Ошибка при запросе к API."""

    pass


class SendMessageError(Exception):
    """Ошибка отправки сообщения."""

    pass
