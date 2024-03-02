from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
import logging
from interface.models import *
from interface.forms import LabAnswerForm

from django.contrib.auth import login, authenticate
from interface.forms import SignUpForm
from django.shortcuts import render, redirect
from django.utils import timezone


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
            answered = Answers.objects.filter(lab=lab, user=request.user).first()
            if answered is None:
                answer = request.GET.get("answer_flag")
                if answer:
                    if answer == lab.answer_flag:
                        context["submitted"] = True
                        answer_object = Answers(lab=lab, user=request.user, datetime=timezone.now())
                        answer_object.save()
                    else:
                        context["form"].fields["answer_flag"].label = "Неверный флаг!"
            else:
                context["submitted"] = True
        return context


class LabListView(ListView):
    model = Lab


class CompetitionListView(ListView):
    model = Competition

    def get_queryset(self):
        queryset = []
        if self.request.user.is_authenticated:
            queryset = Competition.objects.all().filter(platoons__in=[self.request.user.platoon])
        return queryset


class CompetitionDetailView(DetailView):
    model = Competition

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["available"] = True

        if timezone.now() < context["object"].start or timezone.now() > context["object"].finish:
            context["available"] = False
            return context

        competition = context["object"]
        context["object"] = competition.lab
        context = LabDetailView.set_submitted(context, self.request)

        context["object"] = competition

        context["delta"] = CompetitionDetailView.get_timer(context["object"])

        return context

    @staticmethod
    def get_timer(competition):
        delta = (competition.finish - timezone.now()).seconds
        seconds = delta % 60
        delta //= 60
        minutes = delta % 60
        hours = delta // 60

        return {"hours": hours, "minutes": minutes, "seconds": seconds}



class PlatoonDetailView(DetailView):
    model = Platoon
    pk_url_kwarg = 'id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_list = User.objects.filter(platoon = context["platoon"]).exclude(username = "admin")
        context["user_list"] = user_list
        logging.debug(context)
        return context


class PlatoonListView(ListView):
    model = Platoon


class UserDetailView(DetailView):
    model = User
    pk_url_kwarg = 'id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = User.objects.filter(username = "admin").first()
        logging.debug(context)
        logging.debug(context["object"].username)
        return context


def registration(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        platoon = int(request.POST.get('platoon'))
        if not Platoon.objects.filter(id = platoon).exists():
            Platoon.objects.create(id = platoon)
        platoon = Platoon.objects.get(id = platoon)
        form.platoon = platoon
        if form.is_valid():
            usname = request.POST.get('name') + " " + request.POST.get('second_name')
            if User.objects.filter(username = usname).exists():
                user = User.objects.get(username = usname)
            else:
                user = form.save(commit = False)
                user.username = usname
                user = form.save()
            authenticate(user)
            login(request, user)
            return redirect('/cyberpolygon/')
    else:
        form = SignUpForm()
    return render(request, 'registration/reg_user.html', {'form': form})
