from .models import ConfigEntry


def get_config(key, default=None):
    try:
        entry = ConfigEntry.objects.get(key=key)
        return entry.value
    except ConfigEntry.DoesNotExist:
        return default


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