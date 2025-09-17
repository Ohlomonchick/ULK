import os
import logging
from elasticsearch import Elasticsearch
from django.conf import settings
from dynamic_config.utils import get_elastic_config

logger = logging.getLogger(__name__)


def get_elastic_client():
    """Создать клиент Elasticsearch с настройками из конфигурации"""
    config = get_elastic_config()

    # Определяем протокол и формируем полный URL
    protocol = "https" if config['use_https'] else "http"
    # Если URL уже содержит протокол, используем его как есть
    if config['url'].startswith(('http://', 'https://')):
        url = config['url']
    else:
        url = f"{protocol}://{config['url']}"

    # Настройки для HTTPS
    ssl_settings = {}
    if config['use_https']:
        ca_cert_path = os.path.join(settings.BASE_DIR, config['ca_cert_path'])
        if os.path.exists(ca_cert_path):
            ssl_settings['ca_certs'] = ca_cert_path
            ssl_settings['verify_certs'] = True
            # Отключаем проверку имени хоста для development
            ssl_settings['ssl_assert_hostname'] = False
            ssl_settings['ssl_assert_fingerprint'] = False
        else:
            logger.warning(f"CA certificate not found at {ca_cert_path}, using verify_certs=False")
            ssl_settings['verify_certs'] = False

    try:
        client = Elasticsearch(
            url,
            basic_auth=(config['username'], config['password']),
            **ssl_settings
        )

        # Проверяем подключение
        if client.ping():
            logger.info("Successfully connected to Elasticsearch")
            return client
        else:
            logger.error("Failed to ping Elasticsearch")
            return None

    except Exception as e:
        logger.error(f"Failed to create Elasticsearch client: {e}")
        return None


def transliterate_username(username):
    """Транслитерирует имя пользователя для использования в именах ролей Elasticsearch"""
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya'
    }

    result = ''
    for char in username:
        if char in translit_map:
            result += translit_map[char]
        elif char.isalnum() or char in '_-':
            result += char
        else:
            result += '_'

    return result

def create_elastic_user(username, password, index="suricata-*"):
    """
    Создать пользователя в Elasticsearch с ролью для доступа к указанному индексу

    Args:
        username (str): Имя пользователя
        password (str): Пароль пользователя
        index (str): Индекс для доступа (по умолчанию suricata-*)

    Returns:
        str: Результат операции ('created', 'role was not created', 'user was not created', 'connection failed')
    """
    client = get_elastic_client()
    if not client:
        return 'connection failed'

    try:
        # Создаем роль для пользователя (транслитерируем имя для совместимости)
        safe_username = transliterate_username(username)
        role_name = f"user_{safe_username}_role"
        response_role = client.security.put_role(
            name=role_name,
            cluster=[],
            indices=[
                {
                    "names": [index],
                    "privileges": ["read"],
                }
            ],
            applications=[
                {
                    "application": "kibana-.kibana",
                    "privileges": ["read"],
                    "resources": ["*"]
                }
            ],
            transient_metadata={'enabled': True}
        )

        if not response_role.get('role', {}).get('created', False):
            logger.warning(f"Role {role_name} was not created")
            return 'role was not created'

        # Создаем пользователя (используем транслитерированное имя)
        response_user = client.security.put_user(
            username=safe_username,
            password=password,
            roles=[role_name],
        )

        if not response_user.get('created', False):
            logger.warning(f"User {username} was not created")
            return 'user was not created'

        logger.info(f"Successfully created Elasticsearch user: {username}")
        return 'created'

    except Exception as e:
        logger.error(f"Failed to create Elasticsearch user {username}: {e}")
        return 'error'


def delete_elastic_user(username):
    """
    Удалить пользователя и его роль из Elasticsearch

    Args:
        username (str): Имя пользователя

    Returns:
        str: Результат операции ('deleted', 'connection failed', 'error')
    """
    client = get_elastic_client()
    if not client:
        return 'connection failed'

    try:
        role_name = f"user_{username}_role"

        # Удаляем пользователя
        try:
            client.security.delete_user(username=username)
            logger.info(f"Deleted Elasticsearch user: {username}")
        except Exception as e:
            logger.warning(f"Failed to delete user {username}: {e}")

        # Удаляем роль
        try:
            client.security.delete_role(name=role_name)
            logger.info(f"Deleted Elasticsearch role: {role_name}")
        except Exception as e:
            logger.warning(f"Failed to delete role {role_name}: {e}")

        return 'deleted'

    except Exception as e:
        logger.error(f"Failed to delete Elasticsearch user {username}: {e}")
        return 'error'
