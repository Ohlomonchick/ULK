import logging
import random
import json
from collections import defaultdict
from itertools import groupby
from typing import List
from datetime import timedelta

from django import forms
from durationwidget.widgets import TimeDurationWidget
from django.utils import timezone

from interface.utils import get_pnet_password, generate_usb_device_ids, show_iframe_for_admin
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
    MyAttachment,
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
    password = forms.CharField(widget=forms.PasswordInput(), label = "Пароль", help_text="Пароль по умолчанию test.test")
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
                index=f"*{user.pnet_login}*"  # Можно настроить через конфигурацию
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


class LabTaskInlineForm(forms.ModelForm):
    task_type = forms.CharField(
        required=False,
        widget=forms.Select(attrs={'class': 'task-type-dynamic-select'})
    )

    class Meta:
        model = LabTask
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.task_type_id:
            self.fields['task_type'].initial = str(self.instance.task_type_id)
            self.fields['task_type'].widget.choices = [
                (str(self.instance.task_type_id), self.instance.task_type.name)
            ]
        else:
            self.fields['task_type'].widget.choices = [('', '---------')]

    def clean_task_type(self):
        data = self.cleaned_data.get('task_type')
        if not data or data == '':
            return None
        return data

    def _post_clean(self):
        task_type_value = self.cleaned_data.pop('task_type', None)
        super()._post_clean()

        if task_type_value is not None:
            self.cleaned_data['task_type'] = task_type_value

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
            'Вы можете добавить студентов к взводам. Или создать работу только для отдельных студентов.'
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

        # Ожидаем завершения задач развертывания флагов
        self._wait_for_flag_deployment(instance)

        return instance

    def _wait_for_flag_deployment(self, instance, timeout: float = 60.0):
        """
        Ожидает завершения задач развертывания флагов для соревнования.
        Если есть ошибки, добавляет их в форму.
        """
        from interface.flag_deployment import get_flag_deployment_queue, TaskStatus

        queue = get_flag_deployment_queue()
        tasks = queue.get_tasks_by_competition(instance.slug)

        if not tasks:
            return

        task_ids = [task.task_id for task in tasks]
        results = queue.wait_for_tasks(task_ids, timeout=timeout)

        failed_tasks = [
            task for task in results.values()
            if task.status == TaskStatus.FAILED
        ]

        if failed_tasks:
            error_messages = [
                f"Ошибка развертывания флагов для {task.instance_type} (ID: {task.instance_id}): {task.error}"
                for task in failed_tasks
            ]
            error_message = "; ".join(error_messages)
            raise ValidationError(
                f"Не удалось развернуть флаги для некоторых участников: {error_message}"
            )

    def get_all_users(self, instance):
        all_users = User.objects.filter(platoon__in=instance.platoons.all()) | instance.non_platoon_users.all()
        return all_users.distinct()

    def _get_new_participants(self, instance):
        all_users = self.get_all_users(instance)
        existing_user_ids = set(instance.competition_users.values_list('user_id', flat=True))
        return [user for user in all_users if user.id not in existing_user_ids]

    def _get_total_new_participants_count(self, instance):
        """Возвращает общее количество новых участников. Переопределяется в TeamCompetitionForm."""
        return len(self._get_new_participants(instance))

    def handle_competition_users(self, instance):
        import time
        import logging

        logger = logging.getLogger(__name__)
        start_time = time.time()

        new_users = self._get_new_participants(instance)

        if new_users:
            # Генерируем USB IDs и передаем их как параметр
            total = len(new_users)
            usb_ids_distribution = generate_usb_device_ids(total)

            logger.info(f"Starting lab creation for {len(new_users)} users in competition {instance.slug}")
            logger.info(f"USB IDs distribution: {usb_ids_distribution}")

            def _create_users():
                if show_iframe_for_admin(instance, hasattr(instance, 'teamcompetition')):
                    self._create_admin_competition_users(instance)
                return self._create_competition_users(instance, new_users, usb_ids_distribution)

            with_pnet_session_if_needed(instance.lab, _create_users)

            total_time = time.time() - start_time
            logger.info(f"Completed lab creation for {len(new_users)} users in {total_time:.2f} seconds (avg: {total_time/len(new_users):.2f}s per user)")

        self._delete_removed_users(instance)
        return instance

    def _create_competition_users(self, instance, users: List[User], usb_ids_distribution: List[List[int]]):
        """
        Создание Competition2User записей с USB IDs из распределения.

        Примечание: users уже должны быть дедублицированы в _get_new_participants,
        поэтому дополнительная дедубликация здесь не требуется.
        """
        import logging
        logger = logging.getLogger(__name__)

        for idx, user in enumerate(users):
            usb_ids = usb_ids_distribution[idx] if idx < len(usb_ids_distribution) else []
            logger.info(f"User {idx + 1}/{len(users)} ({user.username}, id={user.id}): got USB IDs {usb_ids}")

            deploy_meta = {'usb_device_ids': usb_ids}

            competition2user, created = Competition2User.objects.update_or_create(
                competition=instance,
                user=user,
                level=instance.level,
                defaults={'deploy_meta': deploy_meta}
            )

            if created and not getattr(instance, 'kkz_id', None):
                tasks = list(instance.tasks.all() or instance.lab.options.all())
                assigned_tasks = random.sample(tasks, min(instance.num_tasks, len(tasks)))
                competition2user.tasks.set(assigned_tasks)
            else:
                if not competition2user.deploy_meta:
                    competition2user.deploy_meta = {}
                competition2user.deploy_meta['usb_device_ids'] = usb_ids
                competition2user.save(update_fields=['deploy_meta'])

    def _create_admin_competition_users(self, instance):
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Creating admin competition users for {instance.slug}")
        for user in User.objects.filter(is_superuser=True):
            Competition2User.objects.update_or_create(
                competition=instance,
                user=user,
                level=instance.level
            )

    def _delete_removed_users(self, instance):
        """Удаляет пользователей, которых больше нет в списке."""
        all_users = self.get_all_users(instance) | User.objects.filter(is_superuser=True).all().distinct()
        all_users_ids = set(all_users.values_list('pk', flat=True))
        existing_user_ids = instance.competition_users.values_list('user_id', flat=True)

        def _delete_operation():
            for user_id in existing_user_ids:
                if user_id not in all_users_ids:
                    Competition2User.objects.get(competition=instance, user_id=user_id).delete()

        with_pnet_session_if_needed(instance.lab, _delete_operation)


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

            if 'labs' in self.cleaned_data and 'tasks' in self.cleaned_data:
                labs = self.cleaned_data['labs']
                tasks = self.cleaned_data['tasks']

                labs_info = []
                for lab in labs:
                    lab_tasks = list(tasks) if tasks else LabTask.objects.filter(lab=lab)
                    labs_info.append({
                        'lab': lab,
                        'lab_id': lab.id,
                        'tasks': lab_tasks,
                        'task_ids': [t.id for t in lab_tasks],
                        'num_to_assign': len(lab_tasks)
                    })

                _create_kkz_competitions(kkz, labs_info)

        return kkz

def _create_kkz_competitions(kkz, labs_info, preview_assignments=None):
    """
    Общая логика создания Competition и Competition2User для ККЗ.
    """
    logger = logging.getLogger(__name__)
    users = list(kkz.get_users())
    created_competitions = {}

    for lab_data in labs_info:
        lab = lab_data["lab"]
        lab_id = lab_data.get("lab_id", lab.id)
        tasks = lab_data.get("tasks", [])
        task_ids = lab_data.get("task_ids", [t.id for t in tasks])

        kkz_lab, _ = KkzLab.objects.get_or_create(
            kkz=kkz,
            lab=lab,
            defaults={'num_tasks': len(tasks)}
        )
        if task_ids:
            kkz_lab.tasks.set(LabTask.objects.filter(id__in=task_ids))

        competition = Competition.objects.filter(lab=lab, kkz=kkz).first()

        if competition:
            if competition.start != kkz.start or competition.finish != kkz.finish:
                competition.start = kkz.start
                competition.finish = kkz.finish
                competition.save()
            competition.platoons.set(kkz.platoons.all())
            competition.non_platoon_users.set(kkz.non_platoon_users.all())
            logger.info(f"Updated existing competition for lab {lab.name} in KKZ {kkz.name}")
        else:
            competition_data = {
                'lab': lab.pk,
                'start': kkz.start,
                'finish': kkz.finish,
                'platoons': [p.pk for p in kkz.platoons.all()],
                'non_platoon_users': [u.pk for u in kkz.non_platoon_users.all()],
                'tasks': task_ids,
                'num_tasks': lab_data.get('num_to_assign', len(tasks))
            }

            competition_instance = Competition(kkz=kkz)
            comp_form = CompetitionForm(data=competition_data, instance=competition_instance)

            if comp_form.is_valid():
                competition = None

                def _save_competition():
                    nonlocal competition
                    competition = comp_form.save()

                with_pnet_session_if_needed(lab, _save_competition)

                if competition is None:
                    raise ValidationError(f"Не удалось создать соревнование для {lab.name}")

                logger.info(f"Created competition for lab {lab.name} in KKZ {kkz.name}")
            else:
                raise ValidationError(f"Ошибка создания соревнования для {lab.name}: {comp_form.errors}")

        competition.tasks.set(tasks)
        created_competitions[lab_id] = competition

    _assign_tasks_to_users(kkz, labs_info, created_competitions, users, preview_assignments)

    return created_competitions


def _assign_tasks_to_users(kkz, labs_info, competitions, users, preview_assignments=None):
    """
    Назначает задания пользователям для ККЗ.
    """
    logger = logging.getLogger(__name__)

    max_tasks_limit = None
    if labs_info and len(labs_info) > 0:
        max_tasks_limit = labs_info[0].get("max_tasks_limit")

    all_available_tasks = []
    for lab_info in labs_info:
        all_available_tasks.extend(lab_info.get('tasks', []))

    if max_tasks_limit and max_tasks_limit > 0:
        total_tasks_to_assign = min(max_tasks_limit, len(all_available_tasks))
    else:
        total_tasks_to_assign = len(all_available_tasks)

    assignments_by_user = {}
    if preview_assignments:
        logger.info(f"Using preview_assignments for KKZ {kkz.name}: {len(users)} users, {len(labs_info)} labs")
    elif kkz.unified_tasks:
        if len(all_available_tasks) >= total_tasks_to_assign:
            unified_picks = random.sample(all_available_tasks, total_tasks_to_assign)
        else:
            unified_picks = list(all_available_tasks)

        logger.info(f"Assigning unified tasks for KKZ {kkz.name}: {len(unified_picks)} tasks to {len(users)} users")
        for user in users:
            assignments_by_user[str(user.id)] = unified_picks
    else:
        logger.info(f"Assigning individual tasks for KKZ {kkz.name}: {total_tasks_to_assign} tasks per user, {len(users)} users")
        for user in users:
            if len(all_available_tasks) >= total_tasks_to_assign:
                picks = random.sample(all_available_tasks, total_tasks_to_assign)
            else:
                picks = list(all_available_tasks)
            assignments_by_user[str(user.id)] = picks


    for lab_info in labs_info:
        lab = lab_info['lab']
        lab_id = lab_info.get('lab_id', lab.id)
        competition = competitions.get(lab_id)

        if not competition:
            continue

        def _create_previews(li=lab_info, comp=competition):
            _create_previews_for_lab(kkz, li, comp, users, preview_assignments, assignments_by_user)

        with_pnet_session_if_needed(lab, _create_previews)


def _create_previews_for_lab(kkz, lab_entry, competition, users, preview_assignments, assignments_by_user):
    """
    Создает KkzPreview и назначает задания в Competition2User для одной лабы.
    """
    logger = logging.getLogger(__name__)
    lab = lab_entry["lab"]
    lab_id = lab_entry.get("lab_id", lab.id)

    for user in users:
        user_id_str = str(user.id)

        if preview_assignments:
            tasks_for_user = []
            preview_for_lab = preview_assignments.get(str(lab_id), preview_assignments.get(lab_id, {}))
            if user_id_str in preview_for_lab:
                task_ids_for_user = preview_for_lab[user_id_str]
                tasks_for_user = list(LabTask.objects.filter(id__in=task_ids_for_user))
        else:
            user_tasks = assignments_by_user.get(user_id_str, [])
            tasks_for_user = [t for t in user_tasks if t.lab_id == lab_id]

        if tasks_for_user:
            preview, _ = KkzPreview.objects.get_or_create(
                kkz=kkz,
                lab=lab,
                user=user
            )
            preview.tasks.set(tasks_for_user)

            try:
                comp2user = Competition2User.objects.get(competition=competition, user=user)
                comp2user.tasks.set(tasks_for_user)
            except Competition2User.DoesNotExist:
                logger.warning(f"Competition2User not found for user {user.id} in competition {competition.id}")



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
        if 'lab_elements_color' in self.fields:
            self.fields['lab_elements_color'].widget = forms.TextInput(attrs={'type': 'color'})
            if self.instance and self.instance.lab_elements_color:
                self.fields['lab_elements_color'].initial = self.instance.lab_elements_color
            self.fields['lab_elements_color'].help_text = 'Цвет подложки и инпутов формы.'

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
        team_user_ids = User.objects.filter(team__in=self.cleaned_data.get("teams", [])).values_list("id", flat=True)
        return all_users.exclude(id__in=team_user_ids).distinct()

    def _get_new_teams(self, instance):
        teams = self.cleaned_data.get('teams', [])
        existing_team_ids = set(TeamCompetition2Team.objects.filter(competition=instance).values_list('team_id', flat=True))
        return [team for team in teams if team.id not in existing_team_ids]

    def _get_total_new_participants_count(self, instance):
        """Возвращает общее количество новых участников (пользователи + команды)."""
        return len(self._get_new_participants(instance)) + len(self._get_new_teams(instance))

    def handle_competition_users(self, instance):
        """Обрабатывает создание пользователей и команд с общим распределением USB IDs."""
        import time
        import logging

        logger = logging.getLogger(__name__)
        start_time = time.time()

        new_users = self._get_new_participants(instance)
        new_teams = self._get_new_teams(instance)
        total_new = len(new_users) + len(new_teams)

        if total_new > 0:
            # Генерируем один общий набор USB IDs для всех участников
            usb_ids_distribution = generate_usb_device_ids(total_new)

            # Распределяем: сначала пользователям, потом командам
            users_usb_ids = usb_ids_distribution[:len(new_users)]
            teams_usb_ids = usb_ids_distribution[len(new_users):]

            logger.info(f"Starting lab creation for {total_new} participants in competition {instance.slug}")
            logger.info(f"USB IDs distribution: users={len(users_usb_ids)}, teams={len(teams_usb_ids)}")

            # Сначала создаем пользователей
            if new_users:
                def _create_users():
                    return self._create_competition_users(instance, new_users, users_usb_ids)

                with_pnet_session_if_needed(instance.lab, _create_users)

            # Затем создаем команды (используют оставшиеся USB IDs)
            if new_teams:
                def _create_teams():
                    return self._create_competition_teams(instance, new_teams, teams_usb_ids)

                with_pnet_session_if_needed(instance.lab, _create_teams)

            total_time = time.time() - start_time
            logger.info(f"Completed lab creation for {total_new} participants in {total_time:.2f} seconds")

        self._delete_removed_users(instance)
        self._delete_removed_teams(instance)
        return instance

    def _create_competition_teams(self, instance, teams: List[Team], usb_ids_distribution: List[List[int]]):
        """
        Создание TeamCompetition2Team записей с USB IDs из распределения.

        Примечание: teams уже должны быть дедублицированы в _get_new_teams,
        поэтому дополнительная дедубликация здесь не требуется.
        """
        import logging
        logger = logging.getLogger(__name__)

        for idx, team in enumerate(teams):
            usb_ids = usb_ids_distribution[idx] if idx < len(usb_ids_distribution) else []
            logger.info(f"Team {idx + 1}/{len(teams)} ({team.name}, id={team.id}): got USB IDs {usb_ids}")

            deploy_meta = {'usb_device_ids': usb_ids}

            team_competition2team, created = TeamCompetition2Team.objects.update_or_create(
                competition=instance,
                team=team,
                defaults={'deploy_meta': deploy_meta}
            )

            if created:
                tasks = list(instance.tasks.all() or instance.lab.options.all())
                team_competition2team.tasks.set(tasks)
            else:
                if not team_competition2team.deploy_meta:
                    team_competition2team.deploy_meta = {}
                team_competition2team.deploy_meta['usb_device_ids'] = usb_ids
                team_competition2team.save(update_fields=['deploy_meta'])

    def _delete_removed_teams(self, instance):
        """Удаляет команды, которых больше нет в списке."""
        teams = self.cleaned_data.get('teams', [])
        team_ids = set(teams.values_list('id', flat=True))
        existing_team_records = TeamCompetition2Team.objects.filter(competition=instance)

        def _delete_operation():
            for team_record in existing_team_records:
                if team_record.team_id not in team_ids:
                    team_record.delete()

        with_pnet_session_if_needed(instance.lab, _delete_operation)


class SimpleCompetitionForm(forms.Form):
    duration = forms.DurationField(
        label="Время на работу",
        widget=TimeDurationWidget(
            show_days=True,
            show_hours=True,
            show_minutes=True,
            show_seconds=True,
            attrs={'class': 'input', 'style': 'width: 4rem;'}
        )
    )
    tasks = forms.ModelMultipleChoiceField(
        label="Задания",
        queryset=LabTask.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'select2', 'style': 'width: 100%'})
    )
    level = forms.ModelChoiceField(
        label="Вариант",
        queryset=LabLevel.objects.none(),
        required=False,
        empty_label=None,
        widget=forms.RadioSelect()
    )
    task_type_counts = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='{}'
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
        tasks = LabTask.objects.filter(lab=self.lab).select_related('task_type').order_by('task_type__name', 'task_id')
        self.fields["tasks"].queryset = tasks

        grouped_choices = []

        def get_type_name(t):
            return t.task_type.name if t.task_type else "Без типа"

        tasks_list = list(tasks)
        tasks_list = sorted(tasks_list, key=get_type_name)

        for type_name, group in groupby(tasks_list, key=get_type_name):
            choices = [(str(t.id), f"{t.task_id if t.task_id else ''} {t.description[:50]}") for t in group]
            grouped_choices.append((type_name, choices))

        self.fields["tasks"].choices = grouped_choices

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

    def clean_task_type_counts(self):
        """Валидация JSON с количеством заданий по типам"""
        data = self.cleaned_data.get('task_type_counts', '{}')
        try:
            return json.loads(data) if data else {}
        except json.JSONDecodeError:
            raise ValidationError("Некорректный формат данных типов заданий")

    def select_tasks_by_type_counts(self, lab, task_type_counts):
        """
        Выбирает случайные задания согласно указанному количеству для каждого типа.
        """
        selected_tasks = []

        if isinstance(task_type_counts, list):
            counts_dict = {item['type_id']: item['count'] for item in task_type_counts}
        else:
            counts_dict = task_type_counts

        for type_id, count in counts_dict.items():
            if count <= 0:
                continue

            if type_id is None:
                available_tasks = list(LabTask.objects.filter(lab=lab, task_type__isnull=True))
            else:
                available_tasks = list(LabTask.objects.filter(lab=lab, task_type_id=type_id))

            selected = random.sample(available_tasks, min(count, len(available_tasks)))
            selected_tasks.extend(selected)

        return selected_tasks

    def create_competition(self):
        if not self.lab:
            raise ValidationError("Лабораторная работа не указана")

        task_type_counts = self.cleaned_data.get("task_type_counts", {})

        if task_type_counts:
            selected_tasks = self.select_tasks_by_type_counts(self.lab, task_type_counts)
        else:
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

    preview_assignments = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        initial='{}'
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
        preview_assignments_json = self.cleaned_data.get("preview_assignments", "{}")

        try:
            preview_assignments = json.loads(preview_assignments_json) if preview_assignments_json else {}
        except json.JSONDecodeError:
            preview_assignments = {}

        max_tasks_limit = None
        if labs_data and len(labs_data) > 0:
            max_tasks_limit = labs_data[0].get("max_tasks_limit")

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

        labs_info = []
        for lab_info in labs_data:
            if not lab_info.get("included", True):
                continue

            lab_id = lab_info["lab_id"]
            task_ids = lab_info.get("task_ids", [])
            num_to_assign = lab_info.get("num_tasks") or lab_info.get("num_to_assign") or len(task_ids) or 0

            try:
                lab = Lab.objects.get(id=lab_id)
            except Lab.DoesNotExist:
                continue

            if task_ids:
                tasks = list(LabTask.objects.filter(id__in=task_ids))
            else:
                tasks = list(LabTask.objects.filter(lab=lab))

            labs_info.append({
                "lab": lab,
                "lab_id": lab_id,
                "task_ids": task_ids,
                "tasks": tasks,
                "num_to_assign": int(num_to_assign),
                'max_tasks_limit': max_tasks_limit
            })

        logger = logging.getLogger(__name__)
        logger.info(
            "SimpleKkzForm.create_kkz: users_count=%s, labs_count=%s, preview_assignments_present=%s, unified=%s",
            len(users), len(labs_info), bool(preview_assignments), kkz.unified_tasks
        )

        _create_kkz_competitions(kkz, labs_info, preview_assignments)

        return kkz


# Кастомная форма для MyAttachment в админке (поддержка не только изображений)
class MyAttachmentAdminForm(forms.ModelForm):
    file = forms.FileField(required=True)

    class Meta:
        model = MyAttachment
        fields = '__all__'