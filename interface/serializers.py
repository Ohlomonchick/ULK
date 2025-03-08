from django.utils import timezone
from rest_framework import serializers
from interface.models import Answers, LabLevel, LabTask, User, Lab, TeamCompetition2Team


class AnswerSerializer(serializers.ModelSerializer):
    pnet_login = serializers.CharField(write_only=True, required=False)
    user = serializers.CharField(write_only=True, required=False)
    task = serializers.IntegerField(write_only=True, required=False)
    lab_slug = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Answers
        fields = ("user", "lab", "datetime", "pnet_login", "task", "lab_slug")
        extra_kwargs = {
            'lab': {'required': False},
        }

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

        # If lab is not provided but lab_slug is, look up the Lab by slug.
        if not attrs.get('lab') and attrs.get('lab_slug'):
            try:
                lab_instance = Lab.objects.get(slug=attrs.get('lab_slug'))
            except Lab.DoesNotExist:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Lab with the provided slug does not exist."]}
                )
            attrs['lab'] = lab_instance
            # Remove lab_slug since it's no longer needed.
            attrs.pop('lab_slug')
        else:
            # If lab is provided as a string (i.e. lab name), convert it to a Lab instance.
            if isinstance(attrs['lab'], str):
                try:
                    lab_instance = Lab.objects.get(name=attrs['lab'])
                except Lab.DoesNotExist:
                    raise serializers.ValidationError(
                        {"non_field_errors": ["Lab with the provided name does not exist."]}
                    )
                attrs['lab'] = lab_instance

        return attrs

    def create(self, validated_data):
        # Extract pnet_login and username
        pnet_login = validated_data.pop('pnet_login', None)
        username = validated_data.pop('user', None)
        lab_task_number = validated_data.pop('task', None)
        lab_instance = validated_data['lab']
        # Find the user based on pnet_login or username
        try:
            if pnet_login:
                user = User.objects.get(pnet_login=pnet_login)
            elif username:
                try:
                    user = User.objects.get(username=username)
                except User.DoesNotExist:
                    user = User.objects.get(pnet_login=username)
            else:
                raise serializers.ValidationError(
                    {"non_field_errors": ["User could not be identified."]}
                )
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"non_field_errors": ["User with the provided credentials does not exist."]}
            )

        team_comp = TeamCompetition2Team.objects.filter(
            competition__lab=lab_instance,
            competition__start__lte=timezone.now(),
            competition__finish__gte=timezone.now(),
            team__users=user,
            deleted=False
        ).first()
        team = team_comp.team if team_comp else None

        task = None
        if lab_task_number:
            try:
                task = LabTask.objects.get(lab=lab_instance, task_id=lab_task_number)
            except LabTask.DoesNotExist:
                raise serializers.ValidationError(
                    {"non_field_errors": ["Lab doesn't have task with such number."]}
                )

        # Create or update the Answers instance
        if team:
            answers_instance, created = Answers.objects.update_or_create(
                team=team,
                lab=lab_instance,
                lab_task=task,
                defaults={'datetime': validated_data.get('datetime')}
            )
        else:
            answers_instance, created = Answers.objects.update_or_create(
                user=user,
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