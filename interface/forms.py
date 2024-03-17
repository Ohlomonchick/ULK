from django import forms
from .models import User

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