from django.db.models import Q, Case, When, IntegerField
from .models import User, Competition2User, TeamCompetition2Team, TeamCompetition2TeamsAndUsers, TeamCompetition
from django.http import JsonResponse
from rest_framework import status
from slugify import slugify


def get_lab_type_priority_order():
    """
    Создает сортировку по приоритету lab_type:
    EXAM < PZ < COMPETITION < HW
    """
    return Case(
        When(competition__lab__lab_type='EXAM', then=0),
        When(competition__lab__lab_type='PZ', then=1),
        When(competition__lab__lab_type='COMPETITION', then=2),
        When(competition__lab__lab_type='HW', then=3),
        default=4,
        output_field=IntegerField(),
    )


def try_find_issue_by_lab(lab_filter, user, competition_filters):
    team_issue_filters = {
        'team__users': user
    }
    team_issue_filters.update(lab_filter)
    team_issue_filters.update(competition_filters)

    # Добавляем сортировку по приоритету lab_type
    issue = TeamCompetition2Team.objects.filter(**team_issue_filters).order_by(
        get_lab_type_priority_order(),
        '-competition__start'
    ).first()

    if issue is None:
        issue_filters = {
            'user': user
        }
        issue_filters.update(lab_filter)
        issue_filters.update(competition_filters)

        # Добавляем сортировку по приоритету lab_type
        issue = Competition2User.objects.filter(**issue_filters).order_by(
            get_lab_type_priority_order(),
            '-competition__start'
        ).first()

    return issue


def get_issue(data, competition_filters):
    """
    Extract username/pnet_login and Competition from data,
    then fetch corresponding User and Competition2User objects from DB.
    If missing or invalid, return (None, response_with_error).
    Otherwise, return (issue, None).
    """
    username = data.get("username")
    pnet_login = data.get("pnet_login")
    lab_name = data.get("lab")
    lab_slug = data.get("lab_slug")

    # Check required fields
    if not (username or pnet_login) or not (lab_name or lab_slug):
        return (
            None,
            JsonResponse({'message': 'Wrong request format'}, status=status.HTTP_400_BAD_REQUEST)
        )

    # Используем общую функцию для поиска пользователя
    user = get_user_by_username(username or pnet_login)
    
    if not user:
        return (
            None,
            JsonResponse({'message': 'User or lab does not exist'}, status=status.HTTP_404_NOT_FOUND)
        )

    if lab_name:
        # Сначала пытаемся найти по slug, затем по name
        lab_filter = {'competition__lab__name': lab_name}
        issue = try_find_issue_by_lab(lab_filter, user, competition_filters)
        if issue is None:
            lab_filter = {'competition__lab__pnet_slug': lab_name}
            issue = try_find_issue_by_lab(lab_filter, user, competition_filters)
        if issue is None:
            lab_filter = {'competition__lab__pnet_slug': slugify(lab_name)}
            issue = try_find_issue_by_lab(lab_filter, user, competition_filters)
    else:
        lab_filter = {'competition__lab__pnet_slug': lab_slug}
        issue = try_find_issue_by_lab(lab_filter, user, competition_filters)



    if issue:
        return issue, None
    else:
        return (
            None,
            JsonResponse({'message': 'No such issue'}, status=status.HTTP_404_NOT_FOUND)
        )


def get_user_by_username(username):
    """
    Получает пользователя по username или pnet_login.
    
    Args:
        username: имя пользователя или pnet_login
        
    Returns:
        User или None если пользователь не найден
    """
    return User.objects.filter(Q(username=username) | Q(pnet_login=username)).first()


def get_issue_for_user(competition, user):
    """
    Получает issue (TeamCompetition2Team или Competition2User) для пользователя в соревновании.
    
    ВАЖНО: 
    - Competition2User может быть как в Competition, так и в TeamCompetition
    - TeamCompetition2Team только в TeamCompetition
    
    Логика для TeamCompetition:
    1. Сначала пытается найти TeamCompetition2Team (командный участник)
    2. Затем Competition2User (одиночный участник в командном соревновании)
    
    Для обычных соревнований (Competition):
    - Пытается найти Competition2User
    
    Args:
        competition: объект Competition или TeamCompetition
        user: объект User
        
    Returns:
        tuple: (issue, error_response)
            - issue: TeamCompetition2Team или Competition2User
            - error_response: JsonResponse с ошибкой или None
    """
    if isinstance(competition, TeamCompetition):
        # Для командных соревнований: сначала ищем TeamCompetition2Team
        issue = TeamCompetition2Team.objects.select_related('team').filter(
            competition=competition,
            team__users=user
        ).first()
        if issue:
            return issue, None

        # Участник сессии по сегментам 
        issue = TeamCompetition2TeamsAndUsers.objects.filter(
            team_competition=competition
        ).filter(Q(teams__users=user) | Q(users=user)).select_related('master_user').first()
        if issue:
            return issue, None
    
    # Для обычных соревнований или одиночных участников в TeamCompetition
    try:
        issue = Competition2User.objects.get(competition=competition, user=user)
        return issue, None
    except Competition2User.DoesNotExist:
        return None, JsonResponse(
            {'error': 'User is not a participant of this competition'}, 
            status=404
        )


def create_lab_session_for_issue(competition, user, issue, pnet_url, cookies, xsrf_token):
    """
    Создает сессию лабы для пользователя в зависимости от типа issue.
    
    Для TeamCompetition2Team создаёт мастер-сессию (командная лаба).
    Для Competition2User создаёт индивидуальную сессию.
    
    Args:
        competition: объект Competition
        user: объект User
        issue: TeamCompetition2Team или Competition2User
        pnet_url: URL PNET
        cookies: cookies для запросов
        xsrf_token: XSRF токен
        
    Returns:
        tuple: (success, message, lab_path)
    """
    from .api import _ensure_team_session, _ensure_segment_session, get_lab_path
    from .eveFunctions import create_pnet_lab_session_common
    
    if isinstance(issue, TeamCompetition2Team):
        # Командная сессия с мастером
        return _ensure_team_session(competition, user, pnet_url, cookies, xsrf_token)

    if isinstance(issue, TeamCompetition2TeamsAndUsers):
        return _ensure_segment_session(competition, user, issue, pnet_url, cookies, xsrf_token)

    # Индивидуальная сессия 
    lab_path = get_lab_path(competition, user)
    success, message = create_pnet_lab_session_common(
        pnet_url, 
        user.pnet_login, 
        lab_path, 
        cookies
    )
    return success, message, lab_path
