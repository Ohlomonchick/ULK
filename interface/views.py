from collections import defaultdict
import datetime
from time import sleep
import logging

from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from interface.config import get_web_url
from interface.models import *
from interface.forms import LabAnswerForm, SimpleCompetitionForm, SimpleKkzForm

from django.contrib.auth import login, authenticate
from interface.forms import SignUpForm, ChangePasswordForm
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import FormView, View
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django import forms

from interface.pnet_session_manager import ensure_admin_pnet_session
from interface.serializers import *
from rest_framework import viewsets

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from interface.utils import get_kibana_url, get_pnet_password, patch_lab_description
from django_summernote.utils import get_attachment_model, get_config

logger = logging.getLogger(__name__)


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

            if self.object.lab_type == LabType.COMPETITION:
                return redirect('interface:team-competition-detail', slug=competition.slug)
            else:
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


# noinspection PyUnresolvedReferences
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
                Q(competition_users__user=self.request.user) |
                Q(kkz__platoons=self.request.user.platoon) |
                Q(kkz__non_platoon_users=self.request.user)
            ).distinct()
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

    def set_submitted(self, context: dict, answer_filters: dict = None):
        context["form"] = LabAnswerForm()
        context["submitted"] = False
        lab = self.object.lab

        if answer_filters is None:
            answer_filters = {
                'user':self.request.user,
            }

        if self.request.user.is_authenticated:
            competition = context["object"]
            context["available"] = competition.finish > timezone.now()
            context["issue"] = competition

            if not self.request.user.is_staff and competition.finish <= timezone.now():
                competition.lab.description = ''

            answers = Answers.objects.filter(
                lab=competition.lab,
                lab_task=None,
                datetime__lte=competition.finish,
                datetime__gte=competition.start,
                **answer_filters
            ).first()

            if answers is None:
                answer = self.request.GET.get("answer_flag")
                if answer:
                    if answer == lab.answer_flag:
                        context["submitted"] = True
                        answer_object = Answers(lab=lab, datetime=timezone.now(), **answer_filters)
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
        base_ctx = build_competition_context(self.request, competition,
                                             is_team_competition=hasattr(competition, 'teamcompetition'))
        context.update(base_ctx)
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
                assigned_tasks = list(competition2user.tasks.all())
                for task in assigned_tasks:
                    if Answers.objects.filter(
                        lab=competition.lab,
                        user=self.request.user,
                        lab_task=task,
                        datetime__lte=competition.finish,
                        datetime__gte=competition.start
                    ).exists():
                        task.done = True
                    else:
                        task.done = False
            except Competition2User.DoesNotExist:
                if self.request.user.is_staff:
                    assigned_tasks = list(competition.tasks.all())
                    # Для супер-юзеров показываем статус всех заданий
                    for task in assigned_tasks:
                        task.done = False
                else:
                    assigned_tasks = []

            context["assigned_tasks"] = assigned_tasks

        patch_lab_description(context["object"], self.request.user)
        
        first_platoon = competition.platoons.all().first()
        context["platoon_number"] = first_platoon.number if first_platoon else None

        return context


class KkzDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Kkz
    template_name = 'interface/kkz_detail.html'
    context_object_name = 'kkz'
    pk_url_kwarg = 'pk'

    def test_func(self):
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        kkz = self.object
        competitions = Competition.objects.filter(kkz=kkz).select_related('lab').order_by('lab__name')

        labs_data = []
        total_possible = 0
        total_completed = 0

        for comp in competitions:
            comp_context = build_competition_context(self.request, comp, hasattr(comp, 'teamcompetition'))
            comp2users = Competition2User.objects.filter(competition=comp)
            total_possible += sum(cu.tasks.count() for cu in comp2users)
            total_completed += Answers.objects.filter(
                lab=comp.lab,
                user__in=kkz.get_users(),
                datetime__gte=kkz.start,
                datetime__lte=kkz.finish
            ).count()

            assigned_tasks = []
            if kkz.unified_tasks:
                if comp2users.exists():
                    all_user_task_sets = [
                        set(comp2user.tasks.values_list('id', flat=True))
                        for comp2user in comp2users
                    ]
                    
                    if all_user_task_sets:
                        # Находим пересечение - задания, которые есть у всех пользователей
                        common_task_ids = set.intersection(*all_user_task_sets)
                        if all(tasks_user == common_task_ids for tasks_user in all_user_task_sets):
                            assigned_tasks = list(LabTask.objects.filter(id__in=common_task_ids))
            else:
                assigned_tasks = list(comp.tasks.all())

            labs_data.append({
                'lab': comp.lab,
                'competition': comp,
                'assigned_tasks': assigned_tasks,
                'delta': comp_context['delta'],
                'button_start_now': comp_context['button_start_now'],
                'button_end_now': comp_context['button_end_now'],
                'button_resume': comp_context['button_resume'],
            })

        if labs_data:
            context['delta'] = labs_data[0]['delta']
            context['lab_data'] = labs_data[0]
        else:
            context['delta'] = {"hours": "00", "minutes": "00", "seconds": "00"}

        context['labs_data'] = labs_data
        context['now'] = timezone.now()
        context['max_progress'] = total_possible
        context['total_progress'] = total_completed
        
        first_platoon = kkz.platoons.all().first()
        context["platoon_number"] = first_platoon.number if first_platoon else None

        return context


def build_competition_context(request, instance, is_team_competition=False):
    """
    Возвращает единый словарь контекста, который используют оба шаблона.
    """
    now = timezone.now()

    remaining = instance.finish - now if hasattr(instance, "finish") else timedelta(0)
    if remaining.total_seconds() < 0:
        remaining = timedelta(0)
    hours, rem = divmod(int(remaining.total_seconds()), 3600)
    minutes, seconds = divmod(rem, 60)

    button_start_now = (now - instance.start).total_seconds() < 0 if hasattr(instance, "start") else False
    button_end_now = not button_start_now and (instance.finish - now).total_seconds() > 0 if hasattr(instance, "finish") else False
    button_resume = not button_start_now and not button_end_now

    progress = getattr(instance, "progress", 0)
    max_progress = getattr(instance, "max_progress", 100)
    total_progress = getattr(instance, "total_progress", 0)
    total_tasks = getattr(instance, "num_tasks", 0) or 0

    return {
        "object": instance,
        "delta": {"hours": f"{hours:02d}", "minutes": f"{minutes:02d}", "seconds": f"{seconds:02d}"},
        "button_start_now": button_start_now,
        "button_end_now": button_end_now,
        "button_resume": button_resume,
        "available": getattr(instance, "finish", now) > now,
        "progress": progress,
        "max_progress": max_progress,
        "total_progress": total_progress,
        "total_tasks": total_tasks,
        "is_team_competition": is_team_competition,
    }


class TeamCompetitionDetailView(CompetitionDetailView):
    model = TeamCompetition
    template_name = "interface/competition_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        competition = self.object

        # Try to find a team record in which the user is a member.
        self.team_relation = competition.competition_teams.filter(team__users=self.request.user).first()
        if self.team_relation:
            answer_filters = {'team':self.team_relation.team}
        else:
            answer_filters = {'user':self.request.user}

        context = self.set_submitted(context, answer_filters)
        if context.get("assigned_tasks", []) == [] and self.team_relation:
            context["assigned_tasks"] = self.team_relation.tasks.all()
        context["is_team_competition"] = True

        return context


class CreateKkzView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Общая страница создания ККЗ (выбор взвода)"""
    template_name = 'interface/kkz_simpleform.html'
    form_class = SimpleKkzForm

    def test_func(self):
        return self.request.user.is_staff

    def form_valid(self, form):
        kkz = form.create_kkz()
        sleep(5)
        return redirect('interface:kkz-detail', pk=kkz.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['creating_from_lab'] = False
        return context


class CreateKkzFromLabView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Создание ККЗ из конкретной лабы"""
    template_name = 'interface/kkz_simpleform.html'
    form_class = SimpleKkzForm

    def test_func(self):
        return self.request.user.is_staff

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Получаем лабу из URL
        slug = self.kwargs.get('slug')
        lab_type = self.kwargs.get('lab_type')
        lab = get_object_or_404(Lab, slug=slug, lab_type=lab_type)
        kwargs['lab'] = lab
        return kwargs

    def form_valid(self, form):
        kkz = form.create_kkz()
        sleep(5)
        return redirect('interface:kkz-detail', pk=kkz.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slug = self.kwargs.get('slug')
        lab_type = self.kwargs.get('lab_type')
        lab = get_object_or_404(Lab, slug=slug, lab_type=lab_type)
        context['lab'] = lab
        context['creating_from_lab'] = True
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


class UserDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):  # pragma: no cover
    model = User
    pk_url_kwarg = 'id'

    def test_func(self):
        """Allow only admin users to access this view."""
        return self.request.user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = context["object"]
        
        issues = self._get_user_issues(user)
        self._mark_issues_completion(issues, user)
        
        # Count issues (not unique labs) - total should be number of assigned works
        issues_list = list(issues)
        context["issues"] = issues_list
        context["total"] = len(issues_list)
        
        # Count unique labs with submitted answers (old behavior)
        submitted_labs = self._get_submitted_labs(user)
        submitted_lab_ids = set(submitted_labs.values_list('lab', flat=True))
        context["submitted"] = len(submitted_lab_ids)
        
        # Also include submitted labs that are not in any competition issue
        issue_lab_ids = {
            issue.competition.lab.id
            for issue in issues_list
            if issue.competition and issue.competition.lab
        }
        additional_labs = submitted_lab_ids - issue_lab_ids
        if additional_labs:
            # Add labs with submissions that are not in any competition issue to total
            context["total"] += len(additional_labs)
        
        context["progress"] = self._calculate_progress(context["submitted"], context["total"])
        
        logging.debug(context)
        return context

    def _get_user_issues(self, user):
        """Get all Competition2User objects for the user, excluding those with missing competitions."""
        return Competition2User.objects.filter(
            user=user,
            competition__isnull=False
        ).select_related('competition', 'competition__lab').prefetch_related('tasks')

    def _mark_issues_completion(self, issues, user):
        """Mark each issue as done or not based on task completion status."""
        for issue in issues:
            if not issue.competition or not issue.competition.lab:
                continue
            
            issue.done = self._is_issue_completed(issue, user)

    def _is_issue_completed(self, issue, user):
        """Check if an issue is completed based on task submissions."""
        assigned_tasks = issue.tasks.count()
        submitted_tasks = Answers.objects.filter(
            user=user,
            lab_task__in=issue.tasks.all()
        ).count()
        
        has_none_task_answer = Answers.objects.filter(
            user=user,
            lab=issue.competition.lab,
            lab_task=None
        ).exists()
        
        return has_none_task_answer or (submitted_tasks == assigned_tasks and submitted_tasks > 0)

    def _get_submitted_labs(self, user):
        """Get distinct labs for which the user has submitted answers."""
        return Answers.objects.filter(user=user).values("lab").distinct()

    def _calculate_progress(self, submitted_count, total_count):
        """Calculate progress percentage. Returns 100 if total is 0."""
        if total_count == 0:
            return 100
        return int((submitted_count / total_count) * 100)


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


# noinspection PyUnresolvedReferences
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


# Кастомная форма для загрузки файлов (не только изображений)
class CustomUploadForm(forms.Form):
    file = forms.FileField(required=True)


# Кастомный view для загрузки файлов в summernote (поддерживает не только изображения)
class CustomSummernoteUploadAttachment(UserPassesTestMixin, View):
    def test_func(self):
        return get_config()['test_func_upload_view'](self.request)

    def __init__(self):
        super().__init__()
        self.config = get_config()

    @method_decorator(xframe_options_sameorigin)
    def dispatch(self, *args, **kwargs):
        return super(CustomSummernoteUploadAttachment, self).dispatch(*args, **kwargs)

    def get(self, request, *args, **kwargs):
        return JsonResponse({
            'status': 'false',
            'message': _('Only POST method is allowed'),
        }, status=400)

    def post(self, request, *args, **kwargs):
        authenticated = request.user.is_authenticated

        if self.config['disable_attachment']:
            logger.error(
                'User<%s:%s> tried to use disabled attachment module.',
                getattr(request.user, 'pk', None),
                request.user
            )
            return JsonResponse({
                'status': 'false',
                'message': _('Attachment module is disabled'),
            }, status=403)

        if self.config['attachment_require_authentication'] and \
                not authenticated:
            return JsonResponse({
                'status': 'false',
                'message': _('Only authenticated users are allowed'),
            }, status=403)

        if not request.FILES.getlist('files'):
            return JsonResponse({
                'status': 'false',
                'message': _('No files were requested'),
            }, status=400)

        # remove unnecessary CSRF token, if found
        kwargs = request.POST.copy()
        kwargs.pop('csrfmiddlewaretoken', None)

        # Валидация файлов с помощью FileField вместо ImageField
        for file in request.FILES.getlist('files'):
            form = CustomUploadForm(
                files={
                    'file': file,
                }
            )
            if not form.is_valid():
                logger.error(
                    'User<%s:%s> tried to upload invalid file.',
                    getattr(request.user, 'pk', None),
                    request.user
                )

                return JsonResponse(
                    {
                        'status': 'false',
                        'message': ''.join(form.errors['file']),
                    },
                    status=400
                )

        try:
            attachments = []

            for file in request.FILES.getlist('files'):

                # create instance of appropriate attachment class
                klass = get_attachment_model()
                attachment = klass()
                attachment.file = file

                if file.size > self.config['attachment_filesize_limit']:
                    return JsonResponse({
                        'status': 'false',
                        'message': _('File size exceeds the limit allowed and cannot be saved'),
                    }, status=400)

                # calling save method with attachment parameters as kwargs
                attachment.save(**kwargs)

                # choose relative/absolute url by config
                attachment.url = attachment.file.url

                if self.config['attachment_absolute_uri']:
                    attachment.url = request.build_absolute_uri(attachment.url)

                attachments.append(attachment)

            return HttpResponse(render_to_string('django_summernote/upload_attachment.json', {
                'attachments': attachments,
            }), content_type='application/json')
        except IOError:
            return JsonResponse({
                'status': 'false',
                'message': _('Failed to save attachment'),
            }, status=500)
