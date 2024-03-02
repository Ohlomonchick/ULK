from django import forms
from .models import User

class LabAnswerForm(forms.Form):
    answer_flag = forms.CharField(label="Флаг:", widget=forms.TextInput(attrs={'class': 'input', 'type': 'text'}))


class SignUpForm(forms.ModelForm):
    # platoon = forms.IntegerField(required=True, label='Взвод')

    class Meta:
        fields = ["name", "second_name", "platoon"]
        model = User

# class LabAssignForm(forms.Form):
#     lab = forms.