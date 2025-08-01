import logging
import json

from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta, datetime

from slugify import slugify

from .models import Competition, LabLevel, Lab, LabTask, Answers, User, Competition2User, TeamCompetition2Team, \
    TeamCompetition
from .serializers import LabLevelSerializer, LabTaskSerializer


@api_view(['GET'])
def get_time(request, competition_id):  # pragma: no cover
    try:
        # Fetch the competition by ID
        competition = Competition.objects.get(id=competition_id)

        # Calculate remaining time
        remaining_time = competition.finish - timezone.now()
        if remaining_time < timedelta(0):
            remaining_time = timedelta(0)

        hours, remainder = divmod(remaining_time.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        return Response({
            'hours': hours,
            'minutes': minutes,
            'seconds': seconds,
        })
    except Competition.DoesNotExist:
        return Response({'error': 'Competition not found'}, status=404)


def make_solution_data(solution, competition):
    user = User.objects.get(pk=solution["user_id"])
    return {
        "pos": 0,
        "user_first_name": user.first_name,
        "user_last_name": user.last_name,
        "user_platoon": str(user.platoon),
        "spent": str(solution["datetime"] - competition.start).split(".")[0] if solution["datetime"] else "",
        "datetime": solution["datetime"].strftime("%H:%M:%S") if solution["datetime"] else "",
        "raw_datetime": solution["datetime"],
        "team_name": "",
        "user_id": solution["user_id"]
    }


@api_view(['GET'])
def get_solutions(request, slug):
    try:
        competition = TeamCompetition.objects.get(slug=slug)
    except TeamCompetition.DoesNotExist:
        competition = get_object_or_404(Competition, slug=slug)
    total_tasks = competition.tasks.count()
    is_team_competition = hasattr(competition, 'teams')

    all_individual_users = User.objects.filter(
        platoon__in=competition.platoons.all()) | competition.non_platoon_users.all()
    if is_team_competition:
        team_user_ids = User.objects.filter(team__in=competition.teams.all()).values_list("id", flat=True)
        all_individual_users = all_individual_users.exclude(id__in=team_user_ids)

    individual_filter = Q(user__isnull=False) & (
            Q(user__platoon__in=competition.platoons.all()) |
            Q(user__in=competition.non_platoon_users.all())
    )
    individual_answers_qs = Answers.objects.filter(
        individual_filter,
        lab=competition.lab,
        datetime__lte=competition.finish,
        datetime__gte=competition.start
    )

    # 2a. If team competition, also query team answers.
    team_answers_qs = Answers.objects.none()
    if is_team_competition:
        team_answers_qs = Answers.objects.filter(
            team__in=competition.teams.all(),
            lab=competition.lab,
            datetime__lte=competition.finish,
            datetime__gte=competition.start,
            team__isnull=False
        )

    individual_data = {}
    for answer in individual_answers_qs:
        uid = answer.user.id
        if uid not in individual_data:
            individual_data[uid] = {
                'answers': [],
                'progress': 0,
                'raw_datetime': answer.datetime
            }
        individual_data[uid]['answers'].append(answer)
        if total_tasks > 0:
            individual_data[uid]['progress'] = len(individual_data[uid]['answers'])
        else:
            individual_data[uid]['progress'] = 1  # if lab has no tasks, a single answer gives progress 1.
        if answer.datetime > individual_data[uid]['raw_datetime']:
            individual_data[uid]['raw_datetime'] = answer.datetime

    for user in all_individual_users:
        if user.id not in individual_data:
            individual_data[user.id] = {
                'answers': [],
                'progress': 0,
                'raw_datetime': None
            }

    solutions_data = []
    # Create solution entries for individual answers.
    for uid, data in individual_data.items():
        dummy_solution = {
            "user_id": uid,
            "datetime": data['raw_datetime']
        }
        sol = make_solution_data(dummy_solution, competition)
        sol["progress"] = data['progress']
        solutions_data.append(sol)

    # 4. Process team answers if applicable – group by team.
    if is_team_competition:
        team_data = {}
        for answer in team_answers_qs:
            tid = answer.team.id
            if tid not in team_data:
                team_data[tid] = {
                    'answers': [],
                    'progress': 0,
                    'raw_datetime': answer.datetime,
                    'team': answer.team
                }
            team_data[tid]['answers'].append(answer)
            if total_tasks > 0:
                team_data[tid]['progress'] = len(team_data[tid]['answers'])
            else:
                team_data[tid]['progress'] = 1
            if answer.datetime > team_data[tid]['raw_datetime']:
                team_data[tid]['raw_datetime'] = answer.datetime

        for team in competition.teams.all():
            if team.id not in team_data:
                team_data[team.id] = {
                    'answers': [],
                    'progress': 0,
                    'raw_datetime': None,
                    'team': team
                }

        # For every team, create a solution entry for each member.
        for tid, data in team_data.items():
            team_obj = data['team']
            for user in team_obj.users.all():
                dummy_solution = {
                    "user_id": user.id,
                    "datetime": data['raw_datetime']
                }
                sol = make_solution_data(dummy_solution, competition)
                sol["progress"] = data['progress']
                sol["team_name"] = team_obj.name
                solutions_data.append(sol)

    # 5. Sorting: sort first by progress (descending), then by team_name (if present) and by submission time.
    solutions_data.sort(key=lambda x: (-x["progress"], x["raw_datetime"], x["team_name"]))

    # Re-assign positions based on sorted order.
    pos = 1
    for sol in solutions_data:
        sol["pos"] = pos
        pos += 1

    # 3.a. If lab has tasks, include the total_tasks in the JSON.
    response = {
        "solutions": solutions_data,
        "max_total_progress": competition.participants,
        "total_progress":  sum(solution["progress"] for solution in solutions_data),
        "total_tasks": 1
    }
    if total_tasks:
        response["max_total_progress"] = competition.participants * total_tasks
        response["total_tasks"] = total_tasks
    return JsonResponse(response)


@api_view(['GET'])
def load_levels(request, lab_name):  # pragma: no cover
    try:
        # Сначала пытаемся найти по slug, затем по name
        try:
            lab = Lab.objects.get(slug=lab_name)
        except Lab.DoesNotExist:
            lab = Lab.objects.get(name=lab_name)
        levels = LabLevel.objects.filter(lab=lab)
        serializer = LabLevelSerializer(levels, many=True)
        return Response(serializer.data)
    except Lab.DoesNotExist:
        return Response({"error": "Lab not found"}, status=404)


@api_view(['GET'])
def load_tasks(request, lab_name):  # pragma: no cover
    try:
        # Сначала пытаемся найти по slug, затем по name
        try:
            lab = Lab.objects.get(slug=lab_name)
        except Lab.DoesNotExist:
            lab = Lab.objects.get(name=lab_name)
        tasks = LabTask.objects.filter(lab=lab)
        serializer = LabTaskSerializer(tasks, many=True)
        return Response(serializer.data)
    except Lab.DoesNotExist:
        return Response({"error": "Lab not found"}, status=404)


def change_iso_timezone(utc_time):  # pragma: no cover
    print(utc_time)
    if utc_time[-1] == 'Z':
        utc_time = utc_time[:-1]
    return datetime.fromisoformat(utc_time) + timedelta(hours=3)


@api_view(['POST'])
def press_button(request, action):  # pragma: no cover
    try:
        lab_name = request.data.get('lab')
        start_time = request.data.get('start')
        finish_time = request.data.get('finish')

        start_time = change_iso_timezone(start_time)
        finish_time = change_iso_timezone(finish_time)

        competition = Competition.objects.get(
            lab__name=lab_name,
            finish=finish_time,
            start=start_time,
        )
        if action == "start":
            competition.start = timezone.now()
            competition.save()
            cache.set("competitions_update", True, timeout=60)

            start_time_str = competition.start.strftime("%Y-%m-%d-%H-%M-%S-%f")
            slug = slugify(f"{lab_name}{start_time_str}", allow_unicode=False)
            competition_url = f"/cyberpolygon/competitions/{slug}/"
            return JsonResponse({"redirect_url": competition_url}, status=200)
        else:
            return JsonResponse({"error": "Unknown action"}, status=400)

    except Exception as e:
        print(f"Server error: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@api_view(['GET'])
def check_updates(request):  # pragma: no cover
    last_update = cache.get("competitions_update", False)
    if last_update:
        cache.delete("competitions_update")
    return JsonResponse({"update_required": last_update})


@api_view(['GET'])
def check_availability(request, slug):  # pragma: no cover
    try:
        competition = Competition.objects.get(slug=slug)
        available = competition.finish > timezone.now()
        return JsonResponse({"available": available})
    except Competition.DoesNotExist:
        return JsonResponse({"error": "Competition not found"}, status=404)


@api_view(['GET'])
def get_users_in_platoons(request):  # pragma: no cover
    platoon_ids = request.GET.get('platoons', '')

    if platoon_ids:
        ids = [int(x) for x in platoon_ids.split(',') if x.isdigit()]
        users = User.objects.filter(platoon__number__in=ids).order_by('username')
        print(users)
        data = [{"id": user.pk, "login": user.username} for user in users]
    else:
        data = []
    return JsonResponse(data, safe=False)


def create_var_text(second_name):
    new_var = rf"""/testdir/ 1 1 1 1 1 1 1 1 1 1
./ {second_name}d1 drwxrwxrwxm-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}d2 drwxrwx---m-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}f1 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}f3 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0"""
    return new_var


def parse_request_data(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (ValueError, TypeError):
        raise


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
    else:
        user = User.objects.filter(pnet_login=pnet_login).first()

    if lab_name:
        # Сначала пытаемся найти по slug, затем по name
        lab = Lab.objects.filter(slug=lab_name).first()
        if not lab:
            lab = Lab.objects.filter(name=lab_name).first()
    else:
        # Если передан lab_slug, ищем по slug
        lab = Lab.objects.filter(slug=lab_slug).first()

    if not user or not lab:
        return (
            None,
            JsonResponse({'message': 'User or lab does not exist'}, status=status.HTTP_404_NOT_FOUND)
        )

    team_issue_filters = {
        'competition__lab': lab,
        'team__users': user
    }
    team_issue_filters.update(competition_filters)
    issue = TeamCompetition2Team.objects.filter(**team_issue_filters).first()

    if issue is None:
        issue_filters = {
            'competition__lab': lab,
            'user': user
        }
        issue_filters.update(competition_filters)
        issue = Competition2User.objects.filter(**issue_filters).first()

    if issue:
        return issue, None
    else:
        return (
            None,
            JsonResponse({'message': 'No such issue'}, status=status.HTTP_404_NOT_FOUND)
        )


@api_view(['GET'])
def start_lab(request):
    if request.method == 'GET':
        issue, error_response = get_issue(
            parse_request_data(request),
            {'competition__finish__gt': timezone.now()}
        )
        if error_response:
            return error_response

        response_data = {
            "tasks": [task.task_id for task in issue.competition.tasks.all()]
        }
        if hasattr(issue, 'user'):
            response_data["task"] = create_var_text(issue.user.last_name),
        if hasattr(issue, 'level') and issue.level:
            response_data["variant"] = issue.level.level_number
        if issue.competition.lab.answer_flag:
            response_data["flag"] = issue.competition.lab.answer_flag
        if hasattr(issue, 'team') and issue.team:
            response_data["team"] = [user.pnet_login for user in issue.team.users.all()]
        return JsonResponse(response_data)


@api_view(['POST'])
def end_lab(request):
    if request.method == 'POST':
        issue, error_response = get_issue(
            parse_request_data(request),
            {'competition__start__lt': timezone.now()}
        )
        if error_response:
            return error_response

        if hasattr(issue, 'user'):
            ans = Answers(lab=issue.competition.lab, user=issue.user, datetime=timezone.now())
            ans.save()
        elif hasattr(issue, 'team'):
            ans = Answers(lab=issue.competition.lab, team=issue.team, datetime=timezone.now())
            ans.save()

        return JsonResponse({'message': 'Task finished'})
