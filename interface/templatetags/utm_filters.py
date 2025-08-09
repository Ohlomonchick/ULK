from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter
def get_utm_source(competition, is_team_list):
    """
    Принимает объект competition и флаг is_team_list
    Возвращает соответствующий utm_source
    """
    now = timezone.now()
    is_historical = competition.finish < now
    if is_historical:
        return "history"
    elif is_team_list:
        return "team_competitions"
    else:
        return "competitions"

@register.filter
def get_utm_source_team(competition):
    """ Для team competitions - автоматически определяет utm_source """
    now = timezone.now()
    is_historical = competition.finish < now
    if is_historical:
        return "history"
    return "team_competitions"

@register.filter
def get_utm_source_regular(competition):
    """ Для обычных competitions - автоматически определяет utm_source """
    now = timezone.now()
    is_historical = competition.finish < now
    if is_historical:
        return "history"
    return "competitions"

# --- NEW: очистка HTML от изображений и добавление класса для описания ---
@register.filter
def clean_html_images(html_content):
    """Удаляет теги <img> из HTML, оставляет форматирование и добавляет класс lab-description к <p>."""
    if not html_content:
        return ""
    # Remove <img ...> tags
    cleaned = re.sub(r'<img[^>]*>', '', str(html_content))
    # Remove empty paragraphs
    cleaned = re.sub(r'<p>\s*</p>', '', cleaned)
    # Add class to paragraphs
    cleaned = cleaned.replace('<p', '<p class="lab-description"')
    return mark_safe(cleaned)


# --- NEW: маппинг типа лаборатории в CSS-класс Bulma и фильтр ---
LAB_TYPE_TO_BULMA_CLASS = {
    "HW": "is-primary",         # Домашнее задание
    "PZ": "is-link",            # Практическое занятие
    "EXAM": "is-danger",        # Экзамен
    "COMPETITION": "is-warning" # Соревнование
}


@register.filter
def lab_type_class(lab_type_value: str) -> str:
    """Возвращает CSS-класс Bulma для переданного типа лаборатории."""
    if not lab_type_value:
        return "is-info"
    return LAB_TYPE_TO_BULMA_CLASS.get(str(lab_type_value), "is-info")
