from django import template
from django.utils import timezone

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
    """
    Для team competitions - автоматически определяет utm_source
    """
    now = timezone.now()
    is_historical = competition.finish < now
    
    if is_historical:
        return "history"
    else:
        return "team_competitions"

@register.filter
def get_utm_source_regular(competition):
    """
    Для обычных competitions - автоматически определяет utm_source
    """
    now = timezone.now()
    is_historical = competition.finish < now
    
    if is_historical:
        return "history"
    else:
        return "competitions"
