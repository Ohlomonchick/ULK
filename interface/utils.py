import hashlib

from interface.config import get_web_url

def get_pnet_password(user_password):
    return hashlib.md5((user_password + '42').encode()).hexdigest()[:8]


def get_pnet_lab_name(competition):
    return competition.lab.slug + '_' + competition.lab.lab_type.lower() + '_' + competition.created_at.strftime('%Y%m%d%H%M%S')


def get_database_type():
    """
    Определяет тип базы данных на основе настроек Django.
    Возвращает 'sqlite' или 'postgresql'.
    """
    from django.conf import settings
    from django.db import connection
    
    # Проверяем engine базы данных
    engine = settings.DATABASES['default']['ENGINE']
    
    if 'sqlite' in engine:
        return 'sqlite'
    elif 'postgresql' in engine:
        return 'postgresql'
    else:
        # Fallback - определяем по connection
        vendor = connection.vendor
        if vendor == 'sqlite':
            return 'sqlite'
        elif vendor == 'postgresql':
            return 'postgresql'
        else:
            raise ValueError(f"Неподдерживаемый тип базы данных: {vendor}")


def get_kibana_url():
    return 'http:' + get_web_url().split(':')[1] + ':5601'
