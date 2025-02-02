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

from .models import Competition, LabLevel, Lab, LabTask, Answers, User, Competition2User
from .serializers import LabLevelSerializer, LabTaskSerializer


@api_view(['GET'])
def get_time(request, competition_id):
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
        "spent": str(solution["datetime"] - competition.start).split(".")[0],
        "datetime": solution["datetime"].strftime("%d.%m.%Y %H:%M:%S"),
        "raw_datetime": solution["datetime"]
    }


@api_view(['GET'])
def get_solutions(request, slug):
    competition = get_object_or_404(Competition, slug=slug)
    solutions = Answers.objects.filter(
        Q(user__platoon__in=competition.platoons.all()) | Q(user__in=competition.non_platoon_users.all()),
        lab=competition.lab,
        datetime__lte=competition.finish,
        datetime__gte=competition.start
    ).order_by('user').order_by('datetime').values()

    tasks_to_complete = competition.tasks.count()

    solutions_data = []
    current_user_score = 0
    current_user_id = None
    for solution in solutions:
        if tasks_to_complete:
            if current_user_id is None:
                current_user_id = solution["user_id"]
            elif current_user_id != solution["user_id"]:
                current_user_score = 0
                current_user_id = solution["user_id"]

            current_user_score += 1
            if current_user_score == tasks_to_complete:
                solutions_data.append(make_solution_data(solution, competition))
        else:
            solutions_data.append(make_solution_data(solution, competition))

    solutions_data.sort(key=lambda x: x["raw_datetime"])
    pos = 1
    for sol in solutions_data:
        sol["pos"] = pos
        pos += 1

    return JsonResponse({"solutions": solutions_data})


@api_view(['GET'])
def load_levels(request, lab_name):
    try:
        lab = Lab.objects.get(name=lab_name)
        levels = LabLevel.objects.filter(lab=lab)
        serializer = LabLevelSerializer(levels, many=True)
        return Response(serializer.data)
    except Lab.DoesNotExist:
        return Response({"error": "Lab not found"}, status=404)


@api_view(['GET'])
def load_tasks(request, lab_name):
    try:
        lab = Lab.objects.get(name=lab_name)
        tasks = LabTask.objects.filter(lab=lab)
        serializer = LabTaskSerializer(tasks, many=True)
        return Response(serializer.data)
    except Lab.DoesNotExist:
        return Response({"error": "Lab not found"}, status=404)


def change_iso_timezone(utc_time):
    if utc_time[-1] == 'Z':
        utc_time = utc_time[-1]
    return datetime.fromisoformat(utc_time) + timedelta(hours=3)


@api_view(['POST'])
def press_button(request, action):
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
def check_updates(request):
    last_update = cache.get("competitions_update", False)
    if last_update:
        cache.delete("competitions_update")
    return JsonResponse({"update_required": last_update})


@api_view(['GET'])
def check_availability(request, slug):
    try:
        competition = Competition.objects.get(slug=slug)
        available = competition.finish > timezone.now()
        return JsonResponse({"available": available})
    except Competition.DoesNotExist:
        return JsonResponse({"error": "Competition not found"}, status=404)


@api_view(['GET'])
def get_users_in_platoons(request):
    platoon_ids = request.GET.get('platoons', '')

    if platoon_ids:
        ids = [int(x) for x in platoon_ids.split(',') if x.isdigit()]
        users = User.objects.filter(platoon__number__in=ids).order_by('username')
        print(users)
        data = [{"id": user.pk, "login": user.username} for user in users]
    else:
        data = []
    return JsonResponse(data, safe=False)


# Хардкодный ответ (генерация потом)
hardcode = r"""/testdir/ 1 1 1 1 1 1 1 1 1 1
./ Горяиновd1 drwxrwxrwxm-- admin admin Секретно:Низкий:Нет:0x0
Горяиновd1/ Горяиновd2 drwxrwx---m-- admin admin Секретно:Низкий:Нет:0x0
Горяиновd1/ Горяиновf1 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0
Горяиновd1/ Горяиновf3 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0"""


def create_var_text(text, second_name):
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
        lab = Lab.objects.filter(name=lab_name).first()
    else:
        lab = Lab.objects.filter(name=lab_slug).first()

    if not user or not lab:
        return (
            None,
            JsonResponse({'message': 'User or lab does not exist'}, status=status.HTTP_404_NOT_FOUND)
        )

    issue_filters = {
        'competition__lab': lab,
        'user': user
    }
    issue_filters.update(competition_filters)
    issue = Competition2User.objects.filter(**issue_filters).first()
    if issue and (not lab.answer_flag):
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
            "task": create_var_text(hardcode, issue.user.last_name),
            "tasks": [task.task_id for task in issue.competition.tasks.all()]
        }
        if issue.level:
            response_data["variant"] = issue.level.level_number
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

        ans = Answers(lab=issue.competition.lab, user=issue.user, datetime=timezone.now())
        ans.save()
        return JsonResponse({'message': 'Task finished'})
