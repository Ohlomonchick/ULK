from email.utils import format_datetime

from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
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
            'seconds': seconds
        })
    except Competition.DoesNotExist:
        return Response({'error': 'Competition not found'}, status=404)


@api_view(['GET'])
def get_solutions(request, slug):
    competition = get_object_or_404(Competition, slug=slug)
    solutions = Answers.objects.filter(
        lab=competition.lab,
        user__platoon__in=competition.platoons.all(),
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

