from django.db.models import Q, Case, When, IntegerField
from .models import User, Competition2User, TeamCompetition2Team
from django.http import JsonResponse
from rest_framework import status


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

    if username:
        user = User.objects.filter(username=username).first()
        if not user:
            # Fallback: try to find by pnet_login if username not found
            user = User.objects.filter(pnet_login=username).first()
    else:
        user = User.objects.filter(pnet_login=pnet_login).first()

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
            lab_filter = {'competition__lab__slug': lab_name}
            issue = try_find_issue_by_lab(lab_filter, user, competition_filters)
    else:
        lab_filter = {'competition__lab__slug': lab_slug}
        issue = try_find_issue_by_lab(lab_filter, user, competition_filters)

    

    if issue:
        return issue, None
    else:
        return (
            None,
            JsonResponse({'message': 'No such issue'}, status=status.HTTP_404_NOT_FOUND)
        )
