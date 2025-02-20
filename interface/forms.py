from django import forms
from .models import (User, Competition, LabLevel, LabTask, Competition2User,
                     Platoon, TeamCompetition, Team, TeamCompetition2Team)
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm
from interface.eveFunctions import pf_login, logout, create_user, create_directory
from .config import *


class LabAnswerForm(forms.Form):
    answer_flag = forms.CharField(label="Флаг:", widget=forms.TextInput(attrs={'class': 'input', 'type': 'text'}))


class SignUpForm(forms.ModelForm):
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


class CustomUserCreationForm(UserCreationForm):
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
        exclude = ('participants',)
        model = Competition

    def __init__(self, *args, **kwargs):
        super(CompetitionForm, self).__init__(*args, **kwargs)
        self.fields['start'].widget.attrs['autocomplete'] = 'off'
        self.fields['finish'].widget.attrs['autocomplete'] = 'off'
        self.fields['platoons'].queryset = Platoon.objects.filter(number__gt=0)
        self.fields['non_platoon_users'].help_text =\
            'Вы можете добавить студентов к взводам. Или создать экзамен только для отдельных студентов.'

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

        instance.participants = User.objects.filter(platoon__in=instance.platoons.all()).count()
        instance.save()

        all_users = User.objects.filter(platoon__in=instance.platoons.all()) | instance.non_platoon_users.all()
        existing_user_ids = instance.competition_users.values_list('user_id', flat=True)

        for user in all_users:
            if user.id not in existing_user_ids:
                Competition2User.objects.create(
                    competition=instance,
                    user=user,
                    level=instance.level
                )

        all_users_ids = set(all_users.values_list('pk', flat=True))
        for user_id in existing_user_ids:
            if user_id not in all_users_ids:
                Competition2User.objects.get(competition=instance, user_id=user_id).delete()

        return instance


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
        self.fields['teams'].help_text = \
            'Если пользователь добавлен отдельно от команды, он всё равно будет принимать участие в составе команды.'

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
