import json
from .models import ConfigEntry


def get_config(key, default=None):
    try:
        entry = ConfigEntry.objects.get(key=key)
        return entry.value
    except ConfigEntry.DoesNotExist:
        return default


def set_config(key, value):
    """Установить значение конфигурации"""
    entry, created = ConfigEntry.objects.get_or_create(key=key, defaults={'value': value})
    if not created:
        entry.value = value
        entry.save()
    return entry


def get_bool_config(key, default=False):
    value = get_config(key, None)
    if value is None:
        return default
    return str(value).lower() in ("true", "1", "yes", "on", "да", "вкл", "разрешить")


def get_elastic_config():
    """Получить конфигурацию для Elasticsearch"""
    return {
        'url': get_config('ELASTIC_URL', 'https://localhost:9200'),
        'username': get_config('ELASTIC_USERNAME', 'elastic'),
        'password': get_config('ELASTIC_PASSWORD', 'elastic'),
        'use_https': get_bool_config('ELASTIC_USE_HTTPS', True),  # По умолчанию HTTP для development
        'ca_cert_path': get_config('ELASTIC_CA_CERT_PATH', 'sre/compose/certs/ca/ca.crt'),
    }


def get_worker_credentials(worker_id):
    """
    Получить credentials для воркера из dynamic_config.
    
    Args:
        worker_id: Номер воркера (int)
    
    Returns:
        dict: Словарь с ключами 'username' и 'password', или None если не найдено
    """
    if worker_id is None:
        return None
    
    key = f'WORKER_{worker_id}_CREDS'
    creds_json = get_config(key)
    
    if creds_json:
        try:
            return json.loads(creds_json)
        except json.JSONDecodeError:
            return None
    return None


def set_worker_credentials(worker_id, username, password):
    """
    Сохранить credentials для воркера в dynamic_config.
    
    Args:
        worker_id: Номер воркера (int)
        username: Имя пользователя PNet
        password: Пароль пользователя PNet
    
    Returns:
        ConfigEntry: Созданная или обновленная запись конфигурации
    """
    key = f'WORKER_{worker_id}_CREDS'
    creds = {
        'username': username,
        'password': password
    }
    creds_json = json.dumps(creds)
    return set_config(key, creds_json)