from email.utils import format_datetime

from django.core.cache import cache
from django.utils.timezone import make_naive
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta, datetime

from slugify import slugify

from .models import Competition, LabLevel, Lab, LabTask, Answers, User
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


@api_view(['GET'])
def get_solutions(request, slug):
    competition = get_object_or_404(Competition, slug=slug)
    solutions = Answers.objects.filter(
        Q(user__platoon__in=competition.platoons.all()) | Q(user__in=competition.non_platoon_users.all()),
        lab=competition.lab,
        datetime__lte=competition.finish,
        datetime__gte=competition.start
    ).order_by('datetime').values()

    solutions_data = []
    pos = 1
    for solution in solutions:
        user = User.objects.get(pk=solution["user_id"])
        solutions_data.append({
            "pos": pos,
            "user_first_name": user.first_name,
            "user_last_name": user.last_name,
            "user_platoon": str(user.platoon),
            "spent": str(solution["datetime"] - competition.start).split(".")[0],
            "datetime": solution["datetime"].strftime("%d.%m.%Y %H:%M:%S")
        })
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