from collections import defaultdict
import datetime

from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from interface.models import *
from interface.forms import LabAnswerForm

from django.contrib.auth import login, authenticate
from interface.forms import SignUpForm, ChangePasswordForm
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from interface.eveFunctions import pf_login, logout, change_user_password

from interface.serializers import *
from rest_framework import viewsets

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class LabDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Lab
    slug_url_kwarg = 'slug'
    
    def test_func(self):
        # Allow only admin users
        return self.request.user.is_staff
    
    def get_queryset(self):
        """
        Фильтруем queryset по slug и lab_type из URL
        """
        queryset = super().get_queryset()
        slug = self.kwargs.get('slug')
        lab_type = self.kwargs.get('lab_type')
        
        return queryset.filter(slug=slug, lab_type=lab_type)


class LabListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Lab

    def test_func(self):
        # Allow only admin users
        return self.request.user.is_staff

    def get_queryset(self):
        queryset = Lab.objects.all()
        program = self.request.GET.get("program")
        if program:
            queryset = queryset.filter(program=program)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        labs = self.get_queryset().order_by('slug', 'lab_type')
        lab_bundles = []
        bundle_dict = {}
        for lab in labs:
            slug = lab.slug
            if slug not in bundle_dict:
                bundle_dict[slug] = {LabType.HW: None, LabType.PZ: None, LabType.EXAM: None}
            bundle_dict[slug][lab.lab_type] = lab
        for slug, labs_by_type in bundle_dict.items():
            lab_bundles.append({
                "name": [lab.name for lab in labs_by_type.values() if lab is not None][0],
                "slug": slug,
                "labs": labs_by_type,
                "cover": [lab.cover for lab in labs_by_type.values() if lab is not None and lab.cover is not None][0]
            })
        context['lab_bundles'] = lab_bundles
        return context


class CompetitionListView(LoginRequiredMixin, ListView):  # pragma: no cover
    model = Competition
    template_name = 'interface/competition_list.html'
    context_object_name = 'competitions'

    def get_queryset(self):
        queryset = Competition.objects.order_by("-start").filter(finish__gt=timezone.now())
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                competition_users__user=self.request.user
            )
        return queryset.exclude(teamcompetition__isnull=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        competitions = context["competitions"]
        kkz_groups = defaultdict(list)

        for comp in competitions:
            if comp.kkz:
                kkz_groups[comp.kkz].append(comp)

        context["kkz_groups"] = dict(kkz_groups)

        return context


class CompetitionHistoryListView(CompetitionListView):  # pragma: no cover
    template_name = "interface/competition_history_list.html"

    def get_queryset(self):
        queryset = Competition.objects.order_by("-start").filter(finish__lte=timezone.now())
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                competition_users__user=self.request.user
            )
        return queryset


class TeamCompetitionListView(CompetitionListView):  # pragma: no cover
    template_name = "interface/team_competition_list.html"
    model = TeamCompetition

    def get_queryset(self):
        queryset = TeamCompetition.objects.order_by("-start").filter(finish__gt=timezone.now())
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(competition_users__user=self.request.user) |
                Q(competition_teams__team__users=self.request.user)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_team_list'] = True
        return context


class CompetitionDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Competition
    template_name = 'interface/competition_detail.html'

    def test_func(self):
        competition = self.get_object()
        if self.request.user.is_staff:
            return True
        return competition.start <= timezone.now() <= (competition.finish + datetime.timedelta(minutes=10))

    def set_submitted(self, context):
        context["form"] = LabAnswerForm()
        context["submitted"] = False
        lab = self.object.lab

        if self.request.user.is_authenticated:
            competition = context["object"]
            context["available"] = competition.finish > timezone.now()
            context["issue"] = competition
            
            if not self.request.user.is_staff and competition.finish <= timezone.now():
                competition.lab.description = ''
            
            answers = Answers.objects.filter(
                lab=competition.lab,
                user=self.request.user,
                lab_task=None,
                datetime__lte=competition.finish,
                datetime__gte=competition.start
            ).first()
            
            if answers is None:
                answer = self.request.GET.get("answer_flag")
                if answer:
                    if answer == lab.answer_flag:
                        print('USER: ', self.request.user)
                        competition2user = Competition2User.objects.get(
                            competition=competition,
                            user=self.request.user
                        )
                        competition2user.done = True
                        context["done"] = True
                        competition2user.save()
                        context["submitted"] = True
                        answer_object = Answers(lab=lab, user=self.request.user, datetime=timezone.now())
                        answer_object.save()
                    else:
                        context["form"].fields["answer_flag"].label = "Неверный флаг!"
            else:
                context["submitted"] = True

        if context['submitted']:
            context['available'] = False

        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        competition = context["object"]
        context = self.set_submitted(context)

        if self.request.user.is_staff:
            solutions = Answers.objects.filter(
                lab=competition.lab,
                user__platoon__in=competition.platoons.all(),
                datetime__lte=competition.finish,
                datetime__gte=competition.start
            ).order_by('datetime').values()
            context["solutions"] = solutions

        if self.request.user.is_authenticated:
            try:
                competition2user = Competition2User.objects.get(competition=competition, user=self.request.user)
                assigned_tasks = competition2user.tasks.all()
                for task in assigned_tasks:
                    if Answers.objects.filter(
                        lab=competition.lab,
                        user=self.request.user,
                        lab_task=task,
                        datetime__lte=competition.finish,
                        datetime__gte=competition.start
                    ).exists():
                        task.done = True
            except Competition2User.DoesNotExist:
                if self.request.user.is_staff:
                    assigned_tasks = competition.tasks.all()
                else:
                    assigned_tasks = []

            context["assigned_tasks"] = assigned_tasks

        context["object"] = competition
        context["button"] = (timezone.now() - competition.start).total_seconds() < 0

        return context


class TeamCompetitionDetailView(CompetitionDetailView):
    model = TeamCompetition
    template_name = "interface/competition_detail.html"

    def set_submitted(self, context):
        """
        Extends parent's set_submitted() to support team participants.
        If the user is part of a team in the competition, use the team branch;
        otherwise, fallback to the single-user branch.
        """
        user = self.request.user
        competition = self.object

        # Try to find a team record in which the user is a member.
        self.team_relation = competition.competition_teams.filter(team__users=user).first()

        if self.team_relation:
            lab = competition.lab
            context["available"] = competition.finish > timezone.now()
            # Check if an answer from this team already exists.
            team_answer = Answers.objects.filter(
                lab=lab,
                team=self.team_relation.team,
                lab_task=None,
                datetime__lte=competition.finish,
                datetime__gte=competition.start
            ).first()

            if team_answer:
                context["submitted"] = True
            else:
                # Look for answer flag from GET parameters.
                answer_flag = self.request.GET.get("answer_flag")
                if answer_flag:
                    if answer_flag == lab.answer_flag:
                        # Create an Answer with the team field set.
                        answer_object = Answers(lab=lab, team=self.team_relation.team, datetime=timezone.now())
                        answer_object.save()
                        context["submitted"] = True
                    else:
                        # Optionally, you can change the form field label to notify about an incorrect flag.
                        context["form"].fields["answer_flag"].label = "Неверный флаг!"
        else:
            # Fallback: use the parent implementation (for single user participation)
            context = super().set_submitted(context)

        if context.get("submitted"):
            context["available"] = False

        return context

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context = self.set_submitted(context)
        if context.get("assigned_tasks", []) == [] and self.team_relation:
            context["assigned_tasks"] = self.team_relation.tasks.all()
        context["is_team_competition"] = True

        return context


class PlatoonDetailView(LoginRequiredMixin, DetailView, UserPassesTestMixin):  # pragma: no cover
    model = Platoon
    pk_url_kwarg = 'id'

    def test_func(self):
        # Allow only admin users
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        user_list = User.objects.filter(platoon=context["platoon"]).exclude(username="admin")
        context["user_list"] = user_list
        competitions = {}
        comps = Competition.objects.filter(platoons=context["platoon"])
        for comp in comps:
            if (comp.finish - timezone.now()).seconds < 0:
                competitions[comp] = False
            else:
                competitions[comp] = True
        context["competitions"] = competitions
        logging.debug(context)
        logging.debug(competitions)
        return context


class PlatoonListView(LoginRequiredMixin, ListView, UserPassesTestMixin):  # pragma: no cover
    model = Platoon

    def test_func(self):
        # Allow only admin users
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        platoons_progress = {}
        for platoon in context["object_list"]:
            if platoon.number != 0:
                platoons_progress[platoon] = PlatoonListView.get_platoon_progress(platoon)

        context["object_list"] = platoons_progress
        logging.debug(context)
        return context

    @staticmethod
    def get_platoon_progress(platoon):
        progress_dict = {"total": 0, "submitted": 0, "progress": 0}
        user_list = User.objects.filter(platoon=platoon).exclude(username="admin")
        for user in user_list:
            progress_dict["total"] += Competition2User.objects.filter(user=user).count()
            progress_dict["submitted"] += (
                Answers.objects.filter(user=user)
                .values("lab")
                .distinct()
                .count()
            )
        if progress_dict["total"] == 0:
            progress_dict["progress"] = 0
        else:
            progress_dict["progress"] += int((progress_dict["submitted"] / progress_dict["total"]) * 100)

        return progress_dict


class UserDetailView(LoginRequiredMixin, DetailView, UserPassesTestMixin):  # pragma: no cover
    model = User
    pk_url_kwarg = 'id'

    def test_func(self):
        # Allow only admin users
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = User.objects.filter(username="admin").first()
        issues = Competition2User.objects.filter(user=context["object"])
        object_list = issues
        context["object_list"] = object_list
        total = len(issues)
        context["total"] = total
        context["submitted"] = (
            Answers.objects.filter(user=context["object"])
            .values("lab")
            .distinct()
            .count()
        )
        if total == 0:
            progress = 100
        else:
            progress = int((context["submitted"] / total) * 100)
        context["progress"] = progress
        logging.debug(context)
        return context


def registration(request):  # pragma: no cover
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        platoon = int(request.POST.get('platoon'))
        platoon = Platoon.objects.get(id=platoon)
        form.platoon = platoon
        if form.is_valid():
            usname = request.POST.get('last_name') + "_" + request.POST.get('first_name')
            passwd = request.POST.get('password')
            user = authenticate(username=usname, password=passwd)
            if user:
                if user.platoon == platoon:
                    login(request, user)
                    if passwd == "test.test":
                        return redirect('change_password')
                    return redirect('interface:competition-list')
                else:
                    form.add_error("platoon", "В этом взводе нет такого пользователя")
            else:
                form.add_error("password", "Неправильный логин или пароль")
    else:
        form = SignUpForm()
    return render(request, 'registration/reg_user.html', {'form': form})


def change_password(request):  # pragma: no cover
    if request.method == 'POST':
        form = ChangePasswordForm(request.POST)
        if request.POST.get('password1') == request.POST.get('password2') and request.POST.get('password1') != "":
            user = request.user
            user.set_password(request.POST.get('password1'))
            user.save()
            login(request, user)
            url = "http://172.18.4.160"
            Login = 'pnet_scripts'
            Pass = 'eve'
            cookie, xsrf = pf_login(url, Login, Pass)
            change_user_password(url, cookie, xsrf, user.pnet_login, request.POST.get('password1'))
            logout(url)
            return redirect('/cyberpolygon/competitions')
        else:
            form = ChangePasswordForm()
    else:
        form = ChangePasswordForm()
    return render(request, 'registration/change_password.html', {'form': form})


class AnswerAPIView(LoginRequiredMixin, viewsets.ModelViewSet):
    queryset = Answers.objects.all()
    serializer_class = AnswerSerializer
