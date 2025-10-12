import random
import json
from typing import List
from datetime import timedelta

from django import forms
from durationwidget.widgets import TimeDurationWidget
from django.utils import timezone

from interface.utils import get_pnet_password
from interface.elastic_utils import create_elastic_user
from .models import (
    LabType,
    User,
    Competition,
    LabLevel,
    LabTask,
    Competition2User,
    KkzLab,
    Kkz,
    KkzPreview,
    Lab,
    Platoon,
    TeamCompetition,
    Team,
    TeamCompetition2Team,
    LearningYear,
)
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from interface.pnet_session_manager import ensure_admin_pnet_session, with_pnet_session_if_needed
from django.contrib.admin.widgets import FilteredSelectMultiple
from django_select2 import forms as s2forms
from .config import *


class TeamWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = [
        "name__icontains",
        "slug__icontains",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'data-minimum-input-length': 0,
            'data-allow-clear': 'true',
        })


class UserWidget(s2forms.ModelSelect2MultipleWidget):
    search_fields = [
        "username__icontains",
        "first_name__icontains",
        "last_name__icontains",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.attrs.update({
            'data-minimum-input-length': 0,
            'data-allow-clear': 'true',
        })


class LabAnswerForm(forms.Form):
    answer_flag = forms.CharField(label="Флаг:", widget=forms.TextInput(attrs={'class': 'input', 'type': 'text'}))


class SignUpForm(forms.ModelForm):  # pragma: no cover
    password = forms.CharField(widget=forms.PasswordInput(), label = "Пароль")
    class Meta:
        fields = ["first_name", "last_name", "platoon"]
        model = User

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        platoons = Platoon.objects.all().order_by('number')
        choices = []
        for platoon in platoons:
            if platoon.number == 0:
                choices.append((platoon.id, "Вход без взвода"))
            else:
                choices.append((platoon.id, f"Взвод {platoon.number}"))

        self.fields['platoon'].choices = choices
        self.fields['platoon'].required = False
        for name in self.fields.keys():
            self.fields[name].widget.attrs['autocomplete'] = 'off'


class ChangePasswordForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput(), label = " Новый пароль")
    password2 = forms.CharField(widget=forms.PasswordInput(), label = "Повторите пароль")


class CustomUserCreationForm(UserCreationForm):  # pragma: no cover
    password1 = forms.CharField(
        label='Пароль', required=False, widget=forms.PasswordInput,
        help_text='Пароль по умолчанию "test.test", но вы можете задать свой пароль'
    )
    password2 = forms.CharField(label='Повторите пароль', required=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        for name in self.fields.keys():
            self.fields[name].widget.attrs['autocomplete'] = 'off'
        platoons = Platoon.objects.all().order_by('number')
        choices = []
        for platoon in platoons:
            if platoon.number == 0:
                choices.append((platoon.id, "Пользователь без взвода"))
            else:
                choices.append((platoon.id, f"Взвод {platoon.number}"))
        self.fields['platoon'].choices = choices

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "platoon")

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if not password:
            password = "test.test"  # Set your default password here
        user.set_password(password)
        user.pnet_password = get_pnet_password(password)
        if commit:
            user.save()

        if not user.username:
            user.username = user.last_name + "_" + user.first_name
        user.save()
        pnet_session = ensure_admin_pnet_session()
        with pnet_session:
            pnet_session.create_directory(get_pnet_base_dir(), user.username)
            pnet_session.create_user(user.pnet_login, user.pnet_password)

        # Создаем пользователя в Elasticsearch
        try:
            elastic_result = create_elastic_user(
                username=user.pnet_login,  # pnet_login
                password=user.pnet_password,  # pnet_password
                index="suricata-*"  # Можно настроить через конфигурацию
            )
            if elastic_result != 'created':
                # Логируем ошибку, но не прерываем создание пользователя
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to create Elasticsearch user {user.username}: {elastic_result}")
        except Exception as e:
            # Логируем ошибку, но не прерываем создание пользователя
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Exception while creating Elasticsearch user {user.username}: {e}")

        return user

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не совпадают")

        return password2


class CompetitionForm(forms.ModelForm):
    class Meta:
        # Exclude fields that should be auto-handled or managed elsewhere
        exclude = ('participants', 'slug', 'deleted', 'kkz')
        model = Competition

    def __init__(self, *args, **kwargs):
        super(CompetitionForm, self).__init__(*args, **kwargs)
        self.fields['start'].widget.attrs['autocomplete'] = 'off'
        self.fields['finish'].widget.attrs['autocomplete'] = 'off'
        self.fields['platoons'].queryset = Platoon.objects.filter(number__gt=0)
        self.fields['non_platoon_users'].help_text = \
            'Вы можете добавить студентов к взводам. Или создать экзамен только для отдельных студентов.'
        self.fields['tasks'].help_text = \
            'Вы можете выбрать набор заданий, которые будут распределены случайно. Если оставить пустым, то выберутся все задания.'
        self.fields['num_tasks'].help_text = \
            'Вы можете выбрать, какое количество заданий из выбранных будут распределены случайно.'

        if self.instance and hasattr(self.instance, 'lab') and self.instance.lab is not None:
            # Filter options to those belonging to the selected lab
            self.fields['tasks'].queryset = LabTask.objects.filter(lab=self.instance.lab)
            self.fields['level'].queryset = LabLevel.objects.filter(lab=self.instance.lab)

    def save(self, commit=True):
        instance = super(CompetitionForm, self).save(commit=False)
        instance.save()

        if 'platoons' in self.cleaned_data:
            instance.platoons.set(self.cleaned_data['platoons'])
        if 'tasks' in self.cleaned_data:
            instance.tasks.set(self.cleaned_data['tasks'])
        if 'non_platoon_users' in self.cleaned_data:
            instance.non_platoon_users.set(self.cleaned_data['non_platoon_users'])

        instance.participants = len(self.get_all_users(instance))
        instance.save()

        self.handle_competition_users(instance)
        return instance

    def get_all_users(self, instance):
        all_users = User.objects.filter(platoon__in=instance.platoons.all()) | instance.non_platoon_users.all()
        return all_users

    def handle_competition_users(self, instance):
        import time
        import logging

        logger = logging.getLogger(__name__)
        start_time = time.time()

        all_users = self.get_all_users(instance)
        existing_user_ids = instance.competition_users.values_list('user_id', flat=True)
        new_users = [user for user in all_users if user.id not in existing_user_ids]

        if new_users:
            logger.info(f"Starting lab creation for {len(new_users)} users in competition {instance.slug}")
            with_pnet_session_if_needed(instance.lab, lambda: self._create_competition_users(instance, new_users))

            total_time = time.time() - start_time
            logger.info(f"Completed lab creation for {len(new_users)} users in {total_time:.2f} seconds (avg: {total_time/len(new_users):.2f}s per user)")

        # Удаляем пользователей, которых больше нет в списке
        all_users_ids = set(all_users.values_list('pk', flat=True))
        def _delete_users_operation():
            for user_id in existing_user_ids:
                if user_id not in all_users_ids:
                    Competition2User.objects.get(competition=instance, user_id=user_id).delete()

        with_pnet_session_if_needed(instance.lab, _delete_users_operation)

        return instance

    def _create_competition_users(self, instance, users: List[User]):
        """
        Последовательное создание Competition2User записей.
        """
        def _create_single_competition_user(user):
            """Создание одной записи Competition2User"""

            competition2user, created = Competition2User.objects.update_or_create(
                competition=instance,
                user=user,
                level=instance.level,
            )

            if created:
                tasks = list(instance.tasks.all() or instance.lab.options.all())
                assigned_tasks = random.sample(tasks, min(instance.num_tasks, len(tasks)))
                competition2user.tasks.set(assigned_tasks)

            return competition2user

        created_competition_users = []

        for user in users:
            created_competition_users.append(_create_single_competition_user(user))

        return created_competition_users


class KkzForm(forms.ModelForm):  # pragma: no cover
    class Meta:
        model = Kkz
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(KkzForm, self).__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['autocomplete'] = 'off'
        self.fields['start'].widget.attrs['autocomplete'] = 'off'
        self.fields['finish'].widget.attrs['autocomplete'] = 'off'
        self.fields['platoons'].queryset = Platoon.objects.filter(number__gt=0)
        self.fields['non_platoon_users'].help_text =\
            'Вы можете добавить студентов к взводам. Или создать ККЗ только для отдельных студентов.'
        self.fields['unified_tasks'].help_text =\
            'Вы можете сделать задания одинаковыми для всех.'

    def save(self, commit=True):
        kkz = super().save(commit=False)

        if commit:
            kkz.save()
            self.save_m2m()

            for lab in self.cleaned_data['labs']:
                competition = Competition.objects.create(
                    start=self.cleaned_data['start'],
                    finish=self.cleaned_data['finish'],
                    lab=lab,
                    kkz=kkz
                )
                competition.platoons.set(self.cleaned_data['platoons'])
                competition.non_platoon_users.set(self.cleaned_data['non_platoon_users'])

        return kkz


class CustomFilteredSelectMultiple(FilteredSelectMultiple):
    def __init__(self, verbose_name, is_stacked, attrs=None, choices=()):
        super().__init__(verbose_name, is_stacked, attrs, choices)

    class Media:
        css = {
            'all': ('admin/css/kkz_custom.css',)
        }


class KkzLabInlineForm(forms.ModelForm):  # pragma: no cover
    assignments = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='{}'
    )

    class Meta:
        model = KkzLab
        fields = ['lab', 'tasks', 'num_tasks']
        widgets = {
            'tasks': CustomFilteredSelectMultiple("Задания", is_stacked=False),
        }

    def __init__(self, *args, **kwargs):
        super(KkzLabInlineForm, self).__init__(*args, **kwargs)
        self.fields['lab'].queryset = Lab.objects.filter(lab_type=LabType.EXAM)
        self.fields['tasks'].help_text = \
            'Вы можете выбрать набор заданий, которые будут распределены случайно. Если оставить пустым, то выберутся все задания.'
        self.fields['num_tasks'].help_text = \
            'Вы можете выбрать, какое количество заданий из выбранных будут распределены случайно.'
        if self.instance and self.instance.pk:
            self.fields['tasks'].queryset = LabTask.objects.filter(lab=self.instance.lab)
            previews = KkzPreview.objects.filter(
                kkz=self.instance.kkz,
                lab=self.instance.lab
            ).prefetch_related('tasks')

            assignments = {}
            for preview in previews:
                assignments[str(preview.user.id)] = [t.id for t in preview.tasks.all()]

            if assignments:
                self.initial['assignments'] = json.dumps(assignments)
                print(f"Loaded {len(assignments)} assignments for KkzLab {self.instance.pk}")


class Competition2UserInlineForm(forms.ModelForm):
    class Meta:
        model = Competition2User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.competition and self.instance.competition.lab:
            self.fields['tasks'].queryset = LabTask.objects.filter(lab=self.instance.competition.lab)
            self.fields['level'].queryset = LabLevel.objects.filter(lab=self.instance.competition.lab)
        else:
            self.fields['tasks'].queryset = LabTask.objects.none()
            self.fields['level'].queryset = LabLevel.objects.none()


class LabForm(forms.ModelForm):
    learning_years = forms.MultipleChoiceField(
        choices=LearningYear.choices,
        required=False,
        widget=forms.SelectMultiple,
        label='Годы обучения'
    )

    class Meta:
        model = Lab
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert stored integers to strings for the MultipleChoiceField initial
        current = self.instance.learning_years or []
        self.fields['learning_years'].initial = [str(v) for v in current]
        self.fields['learning_years'].help_text = 'Можно выбрать несколько значений.'
        self.fields['pnet_slug'].help_text = 'При создании сгенерируется автоматически.'

    def clean_learning_years(self):
        values = self.cleaned_data.get('learning_years') or []
        try:
            return [int(v) for v in values]
        except (TypeError, ValueError):
            return []

class TeamCompetitionForm(CompetitionForm):
    teams = forms.ModelMultipleChoiceField(
        queryset=Team.objects.all(),
        required=False,
        widget=forms.SelectMultiple,
        label="Команды"
    )

    class Meta(CompetitionForm.Meta):
        model = TeamCompetition
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lab'].queryset = Lab.objects.filter(lab_type=LabType.COMPETITION)
        self.fields['non_platoon_users'].help_text = \
            'Вы можете добавить студентов к взводам. Или создать соревнование только для отдельных студентов.'
        self.fields['teams'].help_text = \
            'Если пользователь добавлен отдельно от команды, он всё равно будет принимать участие в составе команды.'

    def get_all_users(self, instance):
        all_users = User.objects.filter(platoon__in=instance.platoons.all()) | instance.non_platoon_users.all()
        team_user_ids = User.objects.filter(team__in=self.cleaned_data["teams"]).values_list("id", flat=True)
        all_users = all_users.exclude(id__in=team_user_ids)
        return all_users

    def save(self, commit=True):
        """
        This calls CompetitionForm's save() logic first,
        so you reuse all that field assignment and M2M logic.
        """
        instance = super().save(commit=False)
        if commit:
            instance.save()

        teams = self.cleaned_data.get('teams', [])
        # Clear any existing through-relations.
        instance.teams.clear()

        for team in teams:
            through_instance = TeamCompetition2Team(
                competition=instance,
                team=team
            )
            through_instance.save()

        return instance


class SimpleCompetitionForm(forms.Form):
    duration = forms.DurationField(
        label="Время на работу",
        widget=TimeDurationWidget(
            show_days=True,
            show_hours=True,
            show_minutes=True,
            show_seconds=False,
            attrs={'class': 'input is-small', 'style': 'width: 6rem;'}
        )
    )
    tasks = forms.ModelMultipleChoiceField(
        label="Задания",
        queryset=LabTask.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )
    level = forms.ModelChoiceField(
        label="Вариант",
        queryset=LabLevel.objects.none(),
        required=False,
        empty_label=None,
        widget=forms.RadioSelect()
    )

    def __init__(self, *args, **kwargs):
        self.lab = kwargs.pop("lab", None)
        super().__init__(*args, **kwargs)

        if not self.lab:
            return

        self._setup_tasks_field()
        self._setup_level_field()
        self._setup_duration_field()

        if self.lab.lab_type == LabType.COMPETITION:
            self._add_competition_fields()

    def _setup_tasks_field(self):
        """Configure tasks field for the current lab"""
        qs = LabTask.objects.filter(lab=self.lab)
        self.fields["tasks"].queryset = qs
        self.fields["tasks"].initial = list(qs.values_list("pk", flat=True))

    def _setup_level_field(self):
        """Configure level field for the current lab"""
        qs = LabLevel.objects.filter(lab=self.lab)
        self.fields["level"].queryset = qs
        # Если есть уровни, выбираем первый по умолчанию
        if qs.exists():
            self.fields["level"].initial = qs.first()

    def _setup_duration_field(self):
        """Configure duration field with lab's default"""
        if self.lab.default_duration:
            self.fields["duration"].initial = self.lab.default_duration

    def _add_competition_fields(self):
        """Add teams and users fields for competition labs"""
        self.fields["teams"] = forms.ModelMultipleChoiceField(
            label="Команды",
            queryset=Team.objects.all(),
            required=False,
            widget=TeamWidget,
            help_text="Выберите команды для участия в соревновании"
        )
        self.fields["users"] = forms.ModelMultipleChoiceField(
            label="Отдельные пользователи",
            queryset=User.objects.filter(platoon__number__gt=0) if self.lab.lab_type != LabType.COMPETITION else User.objects.all(),
            required=False,
            widget=UserWidget,
            help_text="Выберите отдельных пользователей для участия в соревновании"
        )

    def create_competition(self):
        if not self.lab:
            raise ValidationError("Лабораторная работа не указана")

        selected_tasks = list(self.cleaned_data.get("tasks") or [])
        base_data = self._build_base_competition_data(selected_tasks)

        if self.lab.lab_type == LabType.COMPETITION:
            form = self._create_team_competition_form(base_data)
        else:
            form = CompetitionForm(data=base_data)

        return self._process_form(form)

    def _build_base_competition_data(self, selected_tasks):
        """Build common competition data"""
        platoon_ids = self._get_target_platoon_ids()
        selected_level = self.cleaned_data.get("level")

        data = {
            "lab": str(self.lab.pk),
            "start": timezone.now(),
            "finish": timezone.now() + self.cleaned_data["duration"],
            "num_tasks": len(selected_tasks) if selected_tasks else 1,
            "platoons": [str(pk) for pk in platoon_ids],
            "tasks": [str(task.pk) for task in selected_tasks],
        }

        # Добавляем уровень, если он выбран
        if selected_level:
            data["level"] = str(selected_level.pk)

        return data

    def _get_target_platoon_ids(self):
        """Get platoon IDs filtered by learning years"""
        if self.lab.lab_type == LabType.COMPETITION:
            return []

        years = self.lab.learning_years or []
        platoons_qs = Platoon.objects.filter(number__gt=0)
        platoons_qs = platoons_qs.filter(learning_year__in=years)
        return list(platoons_qs.values_list("pk", flat=True))

    def _create_team_competition_form(self, base_data):
        """Create TeamCompetitionForm with additional competition-specific data"""
        selected_teams = list(self.cleaned_data.get("teams") or [])
        selected_users = list(self.cleaned_data.get("users") or [])

        competition_data = {
            **base_data,
            "teams": [str(team.pk) for team in selected_teams],
            "non_platoon_users": [str(user.pk) for user in selected_users],
        }

        return TeamCompetitionForm(data=competition_data)

    def _process_form(self, form):
        """Process the form and handle errors"""
        if form.is_valid():
            return form.save(commit=True)

        # Propagate errors into our simple form
        for field, errors in form.errors.items():
            for err in errors:
                self.add_error(field if field in self.fields else None, err)

        raise ValidationError("Форма некорректна")


class SimpleKkzForm(forms.Form):
    name = forms.CharField(
        label="Название ККЗ",
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'input'})
    )

    platoon = forms.ModelChoiceField(
        label="Взвод",
        queryset=Platoon.objects.filter(number__gt=0),
        widget=forms.Select(attrs={
            'class': 'select',
            'id': 'id_platoon'
        })
    )

    duration = forms.DurationField(
        label="Длительность",
        initial=timedelta(hours=2),
        widget=TimeDurationWidget(
            show_days=False,
            show_hours=True,
            show_minutes=True,
            show_seconds=False,
            attrs={'class': 'input is-small', 'style': 'width: 6rem;'}
        )
    )

    unified_tasks = forms.BooleanField(
        label="Единые задания для всех студентов",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'checkbox'})
    )

    labs_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='[]'
    )

    def __init__(self, *args, **kwargs):
        self.lab = kwargs.pop("lab", None)
        self.platoon_id = kwargs.pop("platoon_id", None)
        super().__init__(*args, **kwargs)

        if self.lab:
            years = self.lab.learning_years or []
            self.fields["platoon"].queryset = Platoon.objects.filter(
                number__gt=0,
                learning_year__in=years
            )

            if self.fields["platoon"].queryset.count() == 1:
                self.fields["platoon"].initial = self.fields["platoon"].queryset.first()

        if self.platoon_id:
            self.fields["platoon"].initial = self.platoon_id

    def clean_labs_data(self):
        data = self.cleaned_data.get('labs_data', '[]')
        try:
            labs_data = json.loads(data)
            included_labs = [lab for lab in labs_data if lab.get('included', True)]
            if not included_labs:
                raise ValidationError("Необходимо выбрать хотя бы одну лабораторную работу")
            return labs_data
        except json.JSONDecodeError:
            raise ValidationError("Некорректный формат данных лаб")

    def create_kkz(self):
        platoon = self.cleaned_data["platoon"]
        duration = self.cleaned_data["duration"]
        labs_data = self.cleaned_data["labs_data"]
        max_tasks_limit = None
        if labs_data and len(labs_data) > 0:
            max_tasks_limit = labs_data[0].get('max_tasks_limit')

        kkz = Kkz.objects.create(
            name=self.cleaned_data["name"],
            start=timezone.now(),
            finish=timezone.now() + duration,
            unified_tasks=self.cleaned_data["unified_tasks"]
        )

        kkz.platoons.add(platoon)
        users = list(kkz.get_users())

        if not users:
            kkz.delete()
            raise ValidationError("Во взводе нет пользователей")

        all_available_tasks = []
        labs_info = []

        for lab_info in labs_data:
            if not lab_info.get('included', True):
                continue

            lab_id = lab_info['lab_id']
            task_ids = lab_info.get('task_ids', [])

            try:
                lab = Lab.objects.get(id=lab_id)
            except Lab.DoesNotExist:
                continue

            if task_ids:
                tasks = list(LabTask.objects.filter(id__in=task_ids))
            else:
                tasks = list(LabTask.objects.filter(lab=lab))

            all_available_tasks.extend(tasks)
            labs_info.append({
                'lab': lab,
                'task_ids': task_ids,
                'tasks': tasks
            })

        if max_tasks_limit and max_tasks_limit > 0:
            total_tasks_to_assign = min(max_tasks_limit, len(all_available_tasks))
        else:
            total_tasks_to_assign = len(all_available_tasks)

        for lab_data in labs_info:
            lab = lab_data['lab']
            task_ids = lab_data['task_ids']

            kkz_lab = KkzLab.objects.create(
                kkz=kkz,
                lab=lab,
                num_tasks=len(lab_data['tasks'])
            )

            if task_ids:
                kkz_lab.tasks.set(LabTask.objects.filter(id__in=task_ids))

            competition = Competition.objects.create(
                lab=lab,
                start=kkz.start,
                finish=kkz.finish,
                kkz=kkz,
                num_tasks=len(lab_data['tasks'])
            )
            competition.platoons.add(platoon)

        if kkz.unified_tasks:
            picked = random.sample(all_available_tasks, min(total_tasks_to_assign, len(all_available_tasks)))

            for user in users:
                tasks_by_lab = {}
                for task in picked:
                    if task.lab_id not in tasks_by_lab:
                        tasks_by_lab[task.lab_id] = []
                    tasks_by_lab[task.lab_id].append(task)

                for lab_id, tasks in tasks_by_lab.items():
                    lab = Lab.objects.get(id=lab_id)

                    preview = KkzPreview.objects.create(
                        kkz=kkz,
                        lab=lab,
                        user=user
                    )
                    preview.tasks.set(tasks)

                    competition = Competition.objects.get(kkz=kkz, lab=lab)
                    comp2user, _ = Competition2User.objects.get_or_create(
                        competition=competition,
                        user=user
                    )
                    comp2user.tasks.set(tasks)
        else:
            for user in users:
                user_tasks = random.sample(all_available_tasks, min(total_tasks_to_assign, len(all_available_tasks)))
                tasks_by_lab = {}
                for task in user_tasks:
                    if task.lab_id not in tasks_by_lab:
                        tasks_by_lab[task.lab_id] = []
                    tasks_by_lab[task.lab_id].append(task)

                for lab_id, tasks in tasks_by_lab.items():
                    lab = Lab.objects.get(id=lab_id)

                    preview = KkzPreview.objects.create(
                        kkz=kkz,
                        lab=lab,
                        user=user
                    )
                    preview.tasks.set(tasks)

                    competition = Competition.objects.get(kkz=kkz, lab=lab)
                    comp2user, _ = Competition2User.objects.get_or_create(
                        competition=competition,
                        user=user
                    )
                    comp2user.tasks.set(tasks)

        return kkz