import random

from django import forms
from durationwidget.widgets import TimeDurationWidget
from django.utils import timezone
from .models import (
    LabType,
    User,
    Competition,
    LabLevel,
    LabTask,
    Competition2User,
    KkzLab,
    Kkz,
    Lab,
    Platoon,
    TeamCompetition,
    Team,
    TeamCompetition2Team,
    LearningYear,
)
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from interface.eveFunctions import pf_login, logout, create_user, create_directory
from django.contrib.admin.widgets import FilteredSelectMultiple
from .config import *


class LabAnswerForm(forms.Form):
    answer_flag = forms.CharField(label="Флаг:", widget=forms.TextInput(attrs={'class': 'input', 'type': 'text'}))


class SignUpForm(forms.ModelForm):  # pragma: no cover
    password = forms.CharField(widget=forms.PasswordInput(), label = "Пароль")
    class Meta:
        fields = ["first_name", "last_name", "platoon"]
        model = User

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['platoon'].queryset = Platoon.objects.filter(number__gt=0)
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

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "platoon")

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if not password:
            password = "test.test"  # Set your default password here
        user.set_password(password)
        if commit:
            user.save()

        if not user.username:
            user.username = user.last_name + "_" + user.first_name
        user.save()
        url = get_pnet_url()
        Login = 'pnet_scripts'
        Pass = 'eve'
        cookie, xsrf = pf_login(url, Login, Pass)
        create_directory(url, get_pnet_base_dir(), user.username, cookie)
        create_user(url, user.username, password, '1', cookie)
        logout(url)

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
        all_users = self.get_all_users(instance)
        existing_user_ids = instance.competition_users.values_list('user_id', flat=True)

        for user in all_users:
            if user.id not in existing_user_ids:
                competition2user, created = Competition2User.objects.update_or_create(
                    competition=instance,
                    user=user,
                    level=instance.level,
                )

                if created:
                    tasks = list(instance.tasks.all() or instance.lab.options.all())
                    assigned_tasks = random.sample(tasks, min(instance.num_tasks, len(tasks)))
                    competition2user.tasks.set(assigned_tasks)

        all_users_ids = set(all_users.values_list('pk', flat=True))
        for user_id in existing_user_ids:
            if user_id not in all_users_ids:
                Competition2User.objects.get(competition=instance, user_id=user_id).delete()

        return instance


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


## Simplified: use TimeDurationWidget instead of custom MultiWidget/Field
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

    def __init__(self, *args, **kwargs):
        self.lab = kwargs.pop("lab", None)
        super().__init__(*args, **kwargs)
        # Limit tasks to the current lab
        if self.lab is not None:
            qs = LabTask.objects.filter(lab=self.lab)
            self.fields["tasks"].queryset = qs
            # Preselect all tasks by default
            self.fields["tasks"].initial = list(qs.values_list("pk", flat=True))
            # Prefill duration from lab.default_duration (timedelta)
            if self.lab.default_duration:
                self.fields["duration"].initial = self.lab.default_duration

    def create_competition(self):
        if self.lab is None:
            raise ValidationError("Лабораторная работа не указана")

        selected_tasks = list(self.cleaned_data.get("tasks") or [])

        # Build platoon ids: only real platoons (number > 0), optionally filtered by lab.learning_years
        years = self.lab.learning_years or []
        platoons_qs = Platoon.objects.filter(number__gt=0)
        if years:
            platoons_qs = platoons_qs.filter(learning_year__in=years)
        platoon_ids = list(platoons_qs.values_list("pk", flat=True))

        data = {
            "lab": str(self.lab.pk),
            "start": timezone.now(),
            "finish": timezone.now() + self.cleaned_data["duration"],
            "num_tasks": len(selected_tasks) if selected_tasks else 1,
            "platoons": [str(pk) for pk in platoon_ids],
            # pass tasks so CompetitionForm saves them before assigning to users
            "tasks": [str(task.pk) for task in selected_tasks],
        }


        form = CompetitionForm(data=data)
        if form.is_valid():
            competition = form.save(commit=True)
            return competition
        else:
            # Propagate errors into our simple form
            for field, errors in form.errors.items():
                for err in errors:
                    self.add_error(field if field in self.fields else None, err)
            print("self.errors: --------- ", self.errors)
            raise ValidationError("Форма некорректна")