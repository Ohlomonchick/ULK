from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from interface.models import Answers, Competition, Competition2User, Lab, LabTask, User, Team, TeamCompetition, TeamCompetition2Team
from interface.serializers import AnswerSerializer


class AnswerSerializerTests(TestCase):
    def setUp(self):
        # Create a sample lab.
        self.lab = Lab.objects.create(
            name="Test Lab",
            description="Test lab description",
            answer_flag="flag",
            slug="test-lab",
            platform="NO"
        )
        self.exam = Competition.objects.create(
            lab=self.lab,
            start=timezone.now(),
            finish=timezone.now() + timezone.timedelta(hours=3)
        )
        # Create users.
        self.user_by_pnet = User.objects.create(username="User1", pnet_login="user1")
        self.user_by_username = User.objects.create(username="User2", pnet_login="user2")
        # Create a lab task for the lab.
        self.lab_task = LabTask.objects.create(
            lab=self.lab,
            task_id="1",
            description="Task 1 description"
        )
        # A common datetime for tests.
        self.valid_datetime = timezone.now()
        
        # Create Competition2User objects linking users to the competition
        self.competition2user = Competition2User.objects.create(
            competition=self.exam,
            user=self.user_by_pnet
        )
        self.competition2user2 = Competition2User.objects.create(
            competition=self.exam,
            user=self.user_by_username
        )

    def test_validation_fails_without_user_info(self):
        """
        Serializer should raise an error when neither pnet_login nor user is provided.
        """
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "Either pnet_login or username must be provided."
        )

    def test_create_with_pnet_login(self):
        """
        Creating an Answer using pnet_login should successfully find the user
        and assign the corresponding lab_task.
        """
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "pnet_login": "user1",
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer = serializer.save()

        self.assertEqual(answer.user, self.user_by_pnet)
        self.assertEqual(answer.lab, self.lab)
        self.assertEqual(answer.lab_task, self.lab_task)
        self.assertEqual(answer.datetime, self.valid_datetime)

    def test_create_with_username(self):
        """
        Creating an Answer using a username (that directly exists on the User model)
        should locate the correct user.
        """
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "user": "User2",
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer = serializer.save()
        self.assertEqual(answer.user, self.user_by_username)

    def test_create_with_username_fallback(self):
        """
        If the provided username does not match any User.username but does match a User.pnet_login,
        then the fallback logic should correctly retrieve that user.
        """
        # Create a user whose pnet_login is 'fallback' but whose username is different.
        fallback_user = User.objects.create(username="Fallback", pnet_login="fallback")
        # Create a Competition2User for the fallback user
        Competition2User.objects.create(
            competition=self.exam,
            user=fallback_user
        )
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "user": "fallback",  # This does not match any username but matches pnet_login.
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer = serializer.save()
        self.assertEqual(answer.user, fallback_user)

    def test_invalid_lab_task(self):
        """
        When a non-existent task number is provided, the serializer should raise a ValidationError.
        """
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "pnet_login": "user1",
            "task": 9999  # This task does not exist.
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(ValidationError) as context:
            serializer.save()
        self.assertIn("non_field_errors", context.exception.detail)
        self.assertEqual(
            context.exception.detail["non_field_errors"][0],
            "Lab doesn't have task with such number."
        )

    def test_create_without_task(self):
        """
        When the task field is omitted, lab_task should be None.
        """
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "pnet_login": "user1",
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer = serializer.save()
        self.assertIsNone(answer.lab_task)

    def test_user_does_not_exist(self):
        """
        If the provided pnet_login does not match any user, a ValidationError should be raised.
        """
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "pnet_login": "nonexistent",
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertFalse(serializer.is_valid(), serializer.errors)
        self.assertIn("non_field_errors", serializer.errors)
        self.assertEqual(
            serializer.errors["non_field_errors"][0],
            "User with the provided credentials does not exist."
        )

    def test_update_existing_answer(self):
        """
        When an Answer already exists with the same user, lab, and lab_task,
        calling save() again should update the existing instance (using update_or_create).
        """
        # First creation.
        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "pnet_login": "user1",
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer1 = serializer.save()

        # Update with a new datetime.
        new_datetime = self.valid_datetime + timezone.timedelta(days=1)
        data_update = {
            "lab": self.lab.name,
            "datetime": new_datetime,
            "pnet_login": "user1",
            "task": "1"
        }
        serializer_update = AnswerSerializer(data=data_update)
        self.assertTrue(serializer_update.is_valid(), serializer_update.errors)
        answer2 = serializer_update.save()

        # Check that the same instance was updated.
        self.assertEqual(answer1.pk, answer2.pk)
        self.assertEqual(answer2.datetime, new_datetime)

    def test_create_with_lab_slug(self):
        """
        Test that providing a lab_slug instead of a lab name correctly looks up the Lab instance.
        """
        data = {
            "lab_slug": self.lab.slug,
            "datetime": self.valid_datetime,
            "pnet_login": "user1",
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer = serializer.save()
        self.assertEqual(answer.lab, self.lab)

    def test_create_with_team(self):
        """
        Test that when the user is a member of a team in an ongoing competition,
        the Answer is created with the team instead of the user.
        """
        # Create a Team instance and add user1 as a member.
        team = Team.objects.create(name="Team A")
        team.users.add(self.user_by_pnet)

        # Create an ongoing TeamCompetition for self.lab.
        now = timezone.now()
        competition = TeamCompetition.objects.create(
            slug="comp-1",
            start=now - timezone.timedelta(days=1),
            finish=now + timezone.timedelta(days=1),
            lab=self.lab
        )
        # Create a through model instance linking team and competition.
        team_comp = TeamCompetition2Team.objects.create(
            competition=competition,
            team=team,
            deleted=False
        )
        # Associate the lab task with the team competition (if needed).
        team_comp.tasks.add(self.lab_task)

        data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "pnet_login": "user1",
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer = serializer.save()
        # The answer should be associated with the team, not the user.
        self.assertEqual(answer.team, team)
        self.assertIsNone(answer.user)

    def test_api_answers_post_request(self):
        """
        Test that POST request to /api/answers endpoint works correctly.
        """
        from django.urls import reverse
        from rest_framework.test import APIClient
        from rest_framework import status
        import json
        
        client = APIClient()
        
        # Test data for POST request
        post_data = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime.isoformat(),
            "pnet_login": "user1",
            "task": "1"
        }
        
        # Make POST request to /api/answers
        url = reverse('interface_api:answer-list')
        response = client.post(url, post_data, format='json')
        
        # Check that the request was successful
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify that an Answers object was created
        answer = Answers.objects.filter(
            user=self.user_by_pnet,
            lab=self.lab,
            lab_task=self.lab_task
        ).first()
        
        self.assertIsNotNone(answer)
        self.assertEqual(answer.user, self.user_by_pnet)
        self.assertEqual(answer.lab, self.lab)
        self.assertEqual(answer.lab_task, self.lab_task)

    
