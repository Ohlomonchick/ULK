from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
import logging
from interface.models import *
from interface.forms import LabAnswerForm

from django.contrib.auth import login, authenticate
from interface.forms import SignUpForm, ChangePasswordForm
from django.shortcuts import render, redirect
from django.utils import timezone

from interface.serializers import *
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from django.http.response import JsonResponse
import json


class LabDetailView(DetailView):
    model = Lab

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context = LabDetailView.set_submitted(context, self.request)
        return context

    @staticmethod
    def set_submitted(context, request):
        context["form"] = LabAnswerForm()
        context["submitted"] = False
        lab = context["object"]
        if request.user.is_authenticated:
            now = timezone.now()
            issuedLab = IssuedLabs.objects.filter(lab=context["object"], user=request.user, end_date__gte = now, date_of_appointment__lte = now ).exclude(done = True).first()
            comps = Competition.objects.filter(lab=context["object"], start__lte=now, finish__gte = now).first()
            if comps:
                answers = Answers.objects.filter(lab=context["object"],user=request.user, datetime__lte = comps.finish, datetime__gte = comps.start).first()
            if issuedLab or comps and (answers is None):
                answer = request.GET.get("answer_flag")
                if answer:
                    if answer == lab.answer_flag:
                        context["submitted"] = True
                        answer_object = Answers(lab=lab, user=request.user, datetime=timezone.now())
                        if issuedLab:
                            issuedLab.done = True
                            issuedLab.save()
                        answer_object.save()
                    else:
                        context["form"].fields["answer_flag"].label = "Неверный флаг!"
            else:
                context["submitted"] = True
        return context


class LabListView(ListView):
    model = Lab

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.request.user.is_superuser:
            labs = []
            issues = IssuedLabs.objects.filter(user=self.request.user).exclude(done=True)
            for issue in issues:
                labs.append(issue.lab)
            labs_set = set(labs)
            object_list = labs_set
            context["object_list"] = object_list
        logging.debug(context)
        return context


class CompetitionListView(ListView):
    model = Competition

    def get_queryset(self):
        queryset = []
        current_time = timezone.now()
        if self.request.user.is_authenticated:
            queryset = Competition.objects.order_by("-start").all()
            if not self.request.user.is_staff:
                queryset = queryset.filter(
                    platoons__in=[self.request.user.platoon],
                    start__lte=current_time,
                    finish__gte=current_time
                )
        return queryset


class CompetitionDetailView(DetailView):
    model = Competition

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["available"] = True
        if not self.request.user.is_staff:
            if timezone.now() < context["object"].start or timezone.now() > context["object"].finish:
                context["available"] = False
                return context

        competition = context["object"]
        context["object"] = competition.lab
        context = LabDetailView.set_submitted(context, self.request)

        if self.request.user.is_staff:
            solutions = Answers.objects.filter(
                lab=competition.lab,
                user__platoon__in=competition.platoons.all(), 
                datetime__lte=competition.finish,
                datetime__gte=competition.start
            ).order_by('datetime').values()
            pos = 1
            for solution in solutions:
                user = User.objects.get(pk=solution["user_id"])
                solution["user"] = user
                solution["pos"] = str(pos)
                pos += 1

            context["solutions"] = solutions

            if not str(competition.participants).isnumeric() or int(competition.participants) == 0:
                context["progress"] = 100
            else:
                context["progress"] = len(solutions) / int(competition.participants)

        context["object"] = competition
        context["delta"] = CompetitionDetailView.get_timer(context["object"])

        return context

    @staticmethod
    def get_timer(competition):
        if competition.finish <= timezone.now():
            delta = 0
        else:
            delta = (competition.finish - timezone.now())
            delta = delta.seconds + delta.days * 24 * 60 * 60

        seconds = delta % 60
        delta //= 60
        minutes = delta % 60
        hours = delta // 60

        out = {"hours": hours, "minutes": minutes, "seconds": seconds}
        for key, value in out.items():
            n_value = str(value)
            n_value = (2 - len(n_value)) * "0" + n_value
            out[key] = n_value
        return out


class PlatoonDetailView(DetailView):
    model = Platoon
    pk_url_kwarg = 'id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_list = User.objects.filter(platoon = context["platoon"]).exclude(username = "admin")
        context["user_list"] = user_list
        competitions ={}
        comps = Competition.objects.filter(platoons = context["platoon"])
        for comp in comps:
            if (comp.finish - timezone.now()).seconds < 0:
                competitions[comp] = False
            else: 
                competitions[comp] = True
        context["competitions"] = competitions
        logging.debug(context)
        logging.debug(competitions)
        return context


class PlatoonListView(ListView):
    model = Platoon

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        platoons_progress = {}
        for platoon in context["object_list"]:
            platoons_progress[platoon] = {"total":0, "submitted":0, "progress":0}
            user_list = User.objects.filter(platoon = platoon).exclude(username = "admin")
            for user in user_list:
                platoons_progress[platoon]["total"] += len(IssuedLabs.objects.filter(user = user))
                platoons_progress[platoon]["submitted"] += len(IssuedLabs.objects.filter(user = user).exclude(done = False))
            if platoons_progress[platoon]["total"] == 0:
                platoons_progress[platoon]["progress"] = 100
            else:
                platoons_progress[platoon]["progress"] += int((platoons_progress[platoon]["submitted"] / platoons_progress[platoon]["total"]) * 100)
        context["object_list"] = platoons_progress
        logging.debug(context)
        return context


class UserDetailView(DetailView):
    model = User
    pk_url_kwarg = 'id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = User.objects.filter(username = "admin").first()
        issues = IssuedLabs.objects.filter(user = context["object"])
        object_list = issues
        context["object_list"] = object_list
        total = len(issues)
        context["total"] = total
        submitted = len(IssuedLabs.objects.filter(user = context["object"]).exclude(done = False))
        context["submitted"] = submitted
        if total == 0:
            progress = 100
        else:
            progress = int((submitted / total) * 100)
        context["progress"] = progress
        logging.debug(context)
        return context


def registration(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        platoon = int(request.POST.get('platoon'))
        platoon = Platoon.objects.get(id = platoon)
        form.platoon = platoon
        if form.is_valid():
            usname = request.POST.get('last_name') + "_" + request.POST.get('first_name')
            passwd = request.POST.get('password')
            user = authenticate(username = usname, password = passwd)
            if user:
                if user.platoon == platoon:
                    login(request, user)
                    if passwd == "test.test":
                        return redirect('registration/change_password')
                    return redirect('/cyberpolygon/labs')
                else:
                    form = SignUpForm()    
            else:
                form = SignUpForm()
    else:
        form = SignUpForm()
    return render(request, 'registration/reg_user.html', {'form': form})


def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if request.POST.get('password1') == request.POST.get('password2') and request.POST.get('password1') != "":
            user = request.user
            user.set_password(request.POST.get('password1'))
            user.save()
            login(request, user)
            return redirect('/cyberpolygon/labs')
        else:
            form = ChangePasswordForm()
    else:
        form = ChangePasswordForm()
    return render(request, 'registration/change_password.html', {'form': form})

class AnswerAPIView(viewsets.ModelViewSet):
    queryset = Answers.objects.all()
    serializer_class = AnswerSerializer




# Хардкодный ответ (генерация потом)
hardcode = r"""/testdir/ 1 1 1 1 1 1 1 1 1 1
./ Горяиновd1 drwxrwxrwxm-- admin admin Секретно:Низкий:Нет:0x0
Горяиновd1/ Горяиновd2 drwxrwx---m-- admin admin Секретно:Низкий:Нет:0x0
Горяиновd1/ Горяиновf1 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0
Горяиновd1/ Горяиновf3 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0"""
# 

def create_var_text(text, second_name):
    new_var = rf"""/testdir/ 1 1 1 1 1 1 1 1 1 1
./ {second_name}d1 drwxrwxrwxm-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}d2 drwxrwx---m-- admin admin Секретно:Низкий:Нет:0x0
{second_name}1/ {second_name}f1 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0
{second_name}d1/ {second_name}f3 -rwx------m-- admin admin Секретно:Низкий:Нет:0x0"""
    return new_var

@api_view(['GET'])
def start_lab(request):
    if request.method == 'GET':
        logging.debug(request.body)
        data = json.loads(request.body.decode('utf-8'))
        username = data.get("username")
        lab_name = data.get("lab")
        if username and lab_name:
            user = User.objects.filter(username = username).first()
            lab = Lab.objects.filter(name = lab_name).first()
            logging.debug(lab)
            logging.debug(user)
            if user and lab:
                issue = IssuedLabs.objects.filter(lab_id = lab, user_id = user)
                if issue and not lab.answer_flag:
                    data = {
                        "variant":1,
                        "task": create_var_text(hardcode, user.last_name)
                    }
                    return JsonResponse(data)
                else:
                    return JsonResponse({'message': 'No such issue'}, status=status.HTTP_404_NOT_FOUND) 
            else:
                return JsonResponse({'message': 'User or lab does not exist'}, status=status.HTTP_404_NOT_FOUND) 
        else:
                return JsonResponse({'message': 'Wrong request format'}, status=status.HTTP_400_BAD_REQUEST) 


@api_view(['POST'])
def end_lab(request):
    if request.method == 'POST':
        logging.debug(request.body)
        data = json.loads(request.body.decode('utf-8'))
        username = data.get("username")
        lab_name = data.get("lab")
        if username and lab_name:
            user = User.objects.filter(username = username).first()
            lab = Lab.objects.filter(name = lab_name).first()
            if user and lab:
                issue = IssuedLabs.objects.filter(lab_id = lab, user_id = user).exclude(done = True).first()
                if issue and not lab.answer_flag and not issue.done:
                    ans = Answers(lab=lab, user=user, datetime=timezone.now())
                    ans.save()
                    issue.done = True
                    issue.save()
                    return JsonResponse({'message': 'Task finished'})
                else:
                    return JsonResponse({'message': 'No such issue'}, status=status.HTTP_404_NOT_FOUND) 
            else:
                return JsonResponse({'message': 'User or lab does not exist'}, status=status.HTTP_404_NOT_FOUND) 
        else:
                return JsonResponse({'message': 'Wrong request format'}, status=status.HTTP_400_BAD_REQUEST)