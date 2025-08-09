from django.utils import timezone
from rest_framework import serializers
from interface.models import Answers, LabLevel, LabTask, User, Lab, TeamCompetition2Team
from .api_utils import get_issue


class AnswerSerializer(serializers.ModelSerializer):
    pnet_login = serializers.CharField(write_only=True, required=False)
    user = serializers.CharField(write_only=True, required=False)
    task = serializers.IntegerField(write_only=True, required=False)
    lab_slug = serializers.CharField(write_only=True, required=False)
    lab = serializers.CharField(required=False)

    class Meta:
        model = Answers
        fields = ("user", "lab", "datetime", "pnet_login", "task", "lab_slug")

    def validate(self, attrs):
        # Validate that either pnet_login or user is provided
        if not attrs.get('pnet_login') and not attrs.get('user'):
            raise serializers.ValidationError(
                {"non_field_errors": ["Either pnet_login or username must be provided."]}
            )
        # Validate that either lab (name) or lab_slug is provided.
        if not attrs.get('lab') and not attrs.get('lab_slug'):
            raise serializers.ValidationError(
                {"non_field_errors": ["Either lab or lab_slug must be provided."]}
            )


        attrs['username'] = attrs.get('user')
        issue, error_response = get_issue(attrs, {'competition__finish__gte': timezone.now(), 'competition__start__lte': timezone.now()})
        if error_response is None:
            attrs['issue'] = issue
        elif 'User or lab does not exist' in error_response.content.decode('utf-8'):
            raise serializers.ValidationError(
                {"non_field_errors": ["User with the provided credentials does not exist."]}
            )
        else:
            raise serializers.ValidationError(
                {"non_field_errors": ["Lab with the provided name/slug does not exist."]}
            )

        return attrs

    def create(self, validated_data):
        lab_task_number = validated_data.pop('task', None)
        issue = validated_data.pop('issue', None)
        lab_instance = issue.competition.lab
        
        if lab_task_number:
            try:
                task = LabTask.objects.get(lab=lab_instance, task_id=lab_task_number)
            except LabTask.DoesNotExist:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Lab doesn't have task with such number."]}
                )
        else:
            task = None

        # Create or update the Answers instance
        if isinstance(issue, TeamCompetition2Team):
            answers_instance, created = Answers.objects.update_or_create(
                team=issue.team,
                lab=lab_instance,
                lab_task=task,
                defaults={'datetime': validated_data.get('datetime')}
            )
        else:
            answers_instance, created = Answers.objects.update_or_create(
                user=issue.user,
                lab=lab_instance,
                lab_task=task,
                defaults={'datetime': validated_data.get('datetime')}
            )
        return answers_instance


class LabLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabLevel
        fields = ['id', 'level_number', 'description']


class LabTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTask
        fields = ['id', 'task_id', 'description']
