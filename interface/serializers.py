from rest_framework import serializers
from interface.models import Answers


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answers
        fields = ("user", "lab", "datetime")

