import os
import sys
import time
from functools import wraps
from django.conf import settings

if 'makemigrations' not in sys.argv and 'migrate' and 'loaddata' not in sys.argv:
    from dynamic_config.utils import get_config
else:
    def get_config(key, default):
        return default


def cache_for_minutes(minutes):
    """Simple cache decorator that caches function results for specified minutes"""
    def decorator(func):
        cache = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create a cache key based on function name and arguments
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            current_time = time.time()
            
            # Check if we have a cached result and it's still valid
            if cache_key in cache:
                cached_result, cached_time = cache[cache_key]
                if current_time - cached_time < minutes * 60:  # Convert minutes to seconds
                    return cached_result
            
            # If not cached or expired, call the function and cache the result
            result = func(*args, **kwargs)
            cache[cache_key] = (result, current_time)
            return result
        
        return wrapper
    return decorator


@cache_for_minutes(1)
def get_pnet_url():
    config = get_config('PNET_URL', 'http://172.18.4.160')
    if 'http' not in config:
        return None
    return config


@cache_for_minutes(1)
def get_pnet_base_dir():
    if settings.DEBUG:
        return get_config('PNET_BASE_DIR', '/Practice work/Test_Labs/api_test_dir')
    else:
        return get_config(
            'PNET_BASE_DIR', os.environ.get('PNET_BASE_DIR', '/Practice work/Test_Labs/api_test_dir')
        )


@cache_for_minutes(1)
def get_student_workspace():
    """Возвращает путь к рабочему пространству студента"""
    return get_config('STUDENT_WORKSPACE', 'Practice work/Test_Labs')


def get_web_url():
    """Возвращает URL для внутренних запросов к nginx/веб-серверу"""
    return get_config('WEB_URL', 'http://127.0.0.1:80')