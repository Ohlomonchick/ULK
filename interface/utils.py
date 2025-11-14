import hashlib
import re
import copy

from interface.config import get_web_url
from slugify import slugify
import jinja2

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


def patch_lab_description(competition, user):
    if competition.lab.description:
        template = jinja2.Template(competition.lab.description)
        competition.lab.description = template.render(
            username=user.username, 
            pnet_login=user.pnet_login, 
            username_uppercase=user.username.upper(), 
            pnet_login_uppercase=user.pnet_login.upper(),
            last_name=user.last_name if user.last_name else user.username,
            last_name_uppercase=user.last_name.upper() if user.last_name else user.username.upper(),
            last_name_latin=slugify(user.last_name) if user.last_name else user.username,
            last_name_latin_uppercase=slugify(user.last_name).upper() if user.last_name else user.username.upper()
        )
    else:
        return ''


def generate_usb_device_ids(total_participants):
    """
    Генерирует глобальную последовательность USB device IDs и распределяет их между участниками.
    
    Args:
        total_participants: Общее количество участников (пользователей или команд)
    
    Returns:
        list: Список списков USB device IDs для каждого участника
        Например: [[1, 2, 3], [4, 5, 6], [7, 8, 9]] для 3 участников по 3 ID каждый
    """
    from dynamic_config.utils import get_config
    
    # Получаем общее количество USB устройств из конфигурации, по умолчанию 20
    usb_devices_count = int(get_config('USB_DEVICES_COUNT', '20'))
    
    if total_participants == 0:
        return []
    
    # Генерируем глобальную последовательность ID от 1 до usb_devices_count
    all_ids = list(range(1, usb_devices_count + 1))
    
    # Вычисляем количество ID на участника
    ids_per_participant = usb_devices_count // total_participants
    
    # Распределяем ID между участниками
    distributed_ids = []
    for i in range(total_participants):
        start_idx = i * ids_per_participant
        end_idx = start_idx + ids_per_participant
        participant_ids = all_ids[start_idx:end_idx]
        distributed_ids.append(participant_ids)
    
    return distributed_ids


def replace_usb_device_ids_in_nodes(nodes_data, usb_device_ids):
    """
    Заменяет USB device IDs в qemu_options узлов на соответствующие ID из персонального списка.
    
    Ищет в qemu_options опции вида: -drive id=*,file=*.img или --drive id=*,file=*.img
    и заменяет file=*.img на file=/usr/share/qemu/usb_flash{i}.img, где i - ID из usb_device_ids.
    
    Поддерживает различные варианты:
    - -drive id=usbdisk,file=/usr/share/qemu/usb_flash1.img,if=none
    - --drive id=usb_drive,file=flashdrive.img
    - -drive id=usb_drive,file=flashdrive.img
    
    Args:
        nodes_data: Список словарей с данными узлов (NodesData)
        usb_device_ids: Список USB device IDs для использования (например, [1, 2, 3])
    
    Returns:
        list: Модифицированный список узлов с замененными USB device IDs
    """
    if not usb_device_ids:
        return nodes_data
    
    # Создаем копию, чтобы не изменять оригинальные данные
    modified_nodes = copy.deepcopy(nodes_data)
    
    for node in modified_nodes:
        usb_id_index = 0 # Пока делаем для одного узла доступными все флешки одного пользователя
        if not node or 'qemu_options' not in node:
            continue
        
        qemu_options = node.get('qemu_options', '')
        if not qemu_options:
            continue
        
        # Ищем все опции --drive с file=*.img
        # Паттерн для поиска: --drive id=*,file=*.img или -drive id=*,file=*.img
        # Учитываем различные варианты: id=usb_drive, id=usbdisk, и т.д.
        # Ищем паттерн вида: -drive или --drive, затем id=..., затем file=*.img
        pattern = r'(-{1,2}drive\s+[^,]*id=[^,]+,\s*file=)[^,\s]+\.img'
        
        # Находим все совпадения
        matches = list(re.finditer(pattern, qemu_options))
        
        if matches:
            # Заменяем каждое совпадение на соответствующий USB ID
            for match in reversed(matches):  # Идем с конца, чтобы индексы не сдвигались
                if usb_id_index < len(usb_device_ids):
                    usb_id = usb_device_ids[usb_id_index]
                    # Заменяем только часть file=*.img на file=/usr/share/qemu/usb_flash{i}.img
                    replacement = f'{match.group(1)}/usr/share/qemu/usb_flash{usb_id}.img'
                    qemu_options = qemu_options[:match.start()] + replacement + qemu_options[match.end():]
                    usb_id_index += 1
                else:
                    # Если закончились ID, просто удаляем опцию (включая пробелы вокруг)
                    # Удаляем опцию и возможные пробелы до и после
                    start = match.start()
                    end = match.end()
                    # Удаляем пробелы перед опцией, если они есть
                    while start > 0 and qemu_options[start - 1] == ' ':
                        start -= 1
                    # Удаляем пробелы после опции, если они есть
                    while end < len(qemu_options) and qemu_options[end] == ' ':
                        end += 1
                    qemu_options = qemu_options[:start] + qemu_options[end:]
            
            node['qemu_options'] = qemu_options
    
    return modified_nodes
