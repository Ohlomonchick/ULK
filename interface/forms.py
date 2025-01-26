from django import forms
from .models import User, Competition, LabLevel, LabTask, IssuedLabs, Platoon
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
import logging
from interface.eveFunctions import pf_login, create_lab, logout, create_all_lab_nodes_and_connectors
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
            default_password = "test.test"  # Set your default password here
            user.set_password(default_password)
        else:
            user.set_password(password)
        if commit:
            user.save()
        return user

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не совпадают")

        return password2


class IssuedLabForm(forms.ModelForm):
    class Meta:
        fields = '__all__'
        model = IssuedLabs

    def __init__(self, *args, **kwargs):
        super(IssuedLabForm, self).__init__(*args, **kwargs)
        self.fields['date_of_appointment'].widget.attrs['autocomplete'] = 'off'
        self.fields['end_date'].widget.attrs['autocomplete'] = 'off'

        if self.instance and hasattr(self.instance, 'lab') and self.instance.lab is not None:
            # Filter options to those belonging to the selected lab
            self.fields['tasks'].queryset = LabTask.objects.filter(lab=self.instance.lab)
            self.fields['level'].queryset = LabLevel.objects.filter(lab=self.instance.lab)


class CompetitionForm(forms.ModelForm):
    class Meta:
        exclude = ('participants',)
        model = Competition

    def __init__(self, *args, **kwargs):
        super(CompetitionForm, self).__init__(*args, **kwargs)
        self.fields['start'].widget.attrs['autocomplete'] = 'off'
        self.fields['finish'].widget.attrs['autocomplete'] = 'off'
        self.fields['platoons'].queryset = Platoon.objects.filter(number__gt=0)

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

        for user in instance.non_platoon_users.all():
            if user not in instance.issued_labs.all():
                issued_lab = IssuedLabs.objects.create(
                    lab=instance.lab, user=user, date_of_appointment=instance.start,
                    end_date=instance.finish, level=instance.level
                )
                instance.issued_labs.add(issued_lab)
                issued_lab.tasks.set(instance.tasks.all())

        to_remove = []
        for issued_lab in instance.issued_labs.all():
            if issued_lab.user not in instance.non_platoon_users.all():
                to_remove.append(issued_lab)
        instance.issued_labs.remove(*to_remove)

        if instance.lab.get_platform() == "PN":
            AllUsers = User.objects.filter(platoon_id__in=instance.platoons.all())
            Login = 'pnet_scripts'
            Pass = 'eve'
            if AllUsers:
                cookie, xsrf = pf_login(PNET_URL, Login, Pass)
                for user in AllUsers:
                    create_lab(PNET_URL, instance.lab.name, "", PNET_BASE_DIR, cookie, xsrf, user.username)
                    create_all_lab_nodes_and_connectors(PNET_URL, instance.lab, PNET_BASE_DIR, cookie, xsrf, user.username)
                logout(PNET_URL)

        return instance
