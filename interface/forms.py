from django import forms
from .models import User, Competition
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm


class LabAnswerForm(forms.Form):
    answer_flag = forms.CharField(label="Флаг:", widget=forms.TextInput(attrs={'class': 'input', 'type': 'text'}))


class SignUpForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(), label = "Пароль")
    class Meta:
        fields = ["first_name", "last_name", "platoon"]
        model = User


class ChangePasswordForm(forms.Form):
    password1 = forms.CharField(widget=forms.PasswordInput(), label = " Новый пароль")
    password2 = forms.CharField(widget=forms.PasswordInput(), label = "Повторите пароль")


class CustomUserCreationForm(UserCreationForm):
    password1 = forms.CharField(label='Пароль', required=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Повторите пароль', required=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].required = False
        self.fields['password2'].required = False

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "platoon")

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password1")
        if password:
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


class CompetitionForm(forms.ModelForm):
    class Meta:
        fields = '__all__'
        model = Competition

    def save(self, commit=True):
        instance = super(CompetitionForm, self).save(commit=False)
        instance.save()

        if 'platoons' in self.cleaned_data:
            instance.platoons.set(self.cleaned_data['platoons'])

            # Re-save the instance if additional fields like participants need to be updated
        instance.participants = User.objects.filter(platoon__in=instance.platoons.all()).count()
        instance.save()

        return instance
