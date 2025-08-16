import os
import sys
from django.conf import settings

if 'makemigrations' not in sys.argv and 'migrate' not in sys.argv:
    from dynamic_config.utils import get_config
else:
    def get_config(key, default):
        return default


def get_pnet_url():
    return get_config('PNET_URL', 'http://172.18.4.160')


def get_pnet_base_dir():
    if settings.DEBUG:
        return get_config('PNET_BASE_DIR', '/Practice work/Test_Labs/api_test_dir')
    else:
        return get_config(
            'PNET_BASE_DIR', os.environ.get('PNET_BASE_DIR', '/Practice work/Test_Labs/api_test_dir')
        )


def get_web_url():
    """Возвращает URL для внутренних запросов к nginx/веб-серверу"""
    return get_config('WEB_URL', 'http://127.0.0.1:80')