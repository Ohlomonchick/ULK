from collections import defaultdict
import datetime
from time import sleep

from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from interface.config import get_web_url
from interface.models import *
from interface.forms import LabAnswerForm, SimpleCompetitionForm

from django.contrib.auth import login, authenticate
from interface.forms import SignUpForm, ChangePasswordForm
from django.shortcuts import render, redirect
from django.utils import timezone

from interface.pnet_session_manager import ensure_admin_pnet_session
from interface.serializers import *
from rest_framework import viewsets

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from interface.utils import get_kibana_url, get_pnet_password


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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = SimpleCompetitionForm(request.POST, lab=self.object)
        if form.is_valid():
            competition = form.create_competition()
            sleep(2)
            return redirect('interface:competition-detail', slug=competition.slug)
        context = self.get_context_data(object=self.object)
        context["simple_form"] = form
        return render(request, self.get_template_names(), context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Provide empty form by default
        context["simple_form"] = SimpleCompetitionForm(lab=self.object)
        context["platoons"] = Platoon.objects.filter(learning_year__in=self.object.learning_years, number__gt=0)
        return context


class LabListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Lab

    def test_func(self):
        # Allow only admin users
        return self.request.user.is_staff

    def get_queryset(self):
        # Return all labs for all programs
        return Lab.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        labs = self.get_queryset().order_by('slug', 'lab_type')
        
        # Group labs by program
        programs_data = {}
        for program_value, program_label in LabProgram.choices:
            program_labs = labs.filter(program=program_value)
            bundle_dict = {}
            
            for lab in program_labs:
                slug = lab.slug
                if slug not in bundle_dict:
                    bundle_dict[slug] = {LabType.HW: None, LabType.EXAM: None, LabType.PZ: None}
                bundle_dict[slug][lab.lab_type] = lab
            
            lab_bundles = []
            for slug, labs_by_type in bundle_dict.items():
                available_labs = [lab for lab in labs_by_type.values() if lab is not None]
                if available_labs:
                    covers_with_images = [lab.cover for lab in available_labs if lab.cover]
                    lab_bundles.append({
                        "name": available_labs[0].name,
                        "slug": slug,
                        "labs": labs_by_type,
                        "cover": covers_with_images[0] if covers_with_images else None
                    })
            
            programs_data[program_value] = {
                "label": program_label,
                "bundles": lab_bundles
            }
        
        context['programs_data'] = programs_data
        context['initial_program'] = self.request.GET.get("program", LabProgram.choices[0][0] if LabProgram.choices else None)
        
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
        context["button_start_now"] = (timezone.now() - competition.start).total_seconds() < 0
        context["button_end_now"] = not context["button_start_now"] and (competition.finish - timezone.now()).total_seconds() > 0
        context["button_resume"] = not context["button_start_now"] and not context["button_end_now"]

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
        platoon_id = request.POST.get('platoon')
        if platoon_id:
            platoon = Platoon.objects.get(id=int(platoon_id))
            form.platoon = platoon
        else:
            platoon = None
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
            user.pnet_password = get_pnet_password(request.POST.get('password1'))
            user.save()
            login(request, user)

            session_manager = ensure_admin_pnet_session()
            with session_manager:             
                session_manager.change_user_password(user.pnet_login, user.pnet_password)

            return redirect('/cyberpolygon/competitions')
        else:
            form = ChangePasswordForm()
    else:
        form = ChangePasswordForm()
    return render(request, 'registration/change_password.html', {'form': form})


class AnswerAPIView(viewsets.ModelViewSet):
    queryset = Answers.objects.all()
    serializer_class = AnswerSerializer

def utils_console(request, slug, node_name):
    # Получаем username из параметра запроса, если не передан - используем текущего пользователя
    username = request.GET.get('username', request.user.username)
    
    data = {
        'lab_slug': slug,
        'username': username,
    }
    issue, error_response = get_issue(
        data,
        {'competition__finish__gt': timezone.now()}
    )
    
    if error_response:
        return error_response
    
    return render(request, 'interface/utils_console.html', {'competition': issue.competition, 'node_name': node_name, 'username': username})


def kibana_dashboard(request, slug):
    return render(request, 'interface/kibana_dashboard.html', {'slug': slug, 'kibana_url': get_kibana_url()})
