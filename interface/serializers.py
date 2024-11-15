from rest_framework import serializers
from interface.models import Answers, LabLevel, LabTask


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answers
        fields = ("user", "lab", "datetime")


class LabLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabLevel
        fields = ['id', 'level_number', 'description']


class LabTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTask
        fields = ['id', 'task_id', 'description']


