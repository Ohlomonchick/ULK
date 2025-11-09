import random
import string
import logging

logger = logging.getLogger(__name__)


def generate_flag(length=None):
    """
    Генерирует случайный флаг длиной 8-12 символов (буквы и цифры).
    
    Args:
        length: Длина флага. Если None, выбирается случайно от 8 до 12.
    
    Returns:
        str: Сгенерированный флаг
    """
    if length is None:
        length = random.randint(8, 12)
    else:
        length = max(8, min(12, length))
    
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def generate_flags_for_tasks(tasks):
    """
    Генерирует флаги для списка заданий.
    
    Args:
        tasks: QuerySet или список LabTask объектов
    
    Returns:
        dict: Словарь {task_id: flag}
    """
    flags = {}
    for task in tasks:
        if task.task_id:
            flags[task.task_id] = f"FLAG_{generate_flag()}"
        else:
            logger.warning(f"Task {task.id} has no task_id, skipping flag generation")
    return flags

