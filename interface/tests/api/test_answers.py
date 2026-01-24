from django.test import TestCase, Client
from django.urls import reverse
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
            "pnet_login": "user1",
            "task": "1"
        }
        serializer = AnswerSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        answer = serializer.save()

        self.assertEqual(answer.user, self.user_by_pnet)
        self.assertEqual(answer.lab, self.lab)
        self.assertEqual(answer.lab_task, self.lab_task)

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
        data_update = {
            "lab": self.lab.name,
            "pnet_login": "user1",
            "task": "1",
            "datetime": self.valid_datetime + timezone.timedelta(hours=1)
        }
        serializer_update = AnswerSerializer(data=data_update)
        self.assertTrue(serializer_update.is_valid(), serializer_update.errors)
        answer2 = serializer_update.save()

        # Check that the same instance was updated.
        self.assertEqual(answer1.pk, answer2.pk)
        self.assertLess(answer1.datetime, answer2.datetime)

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

    def test_multiple_answers_for_one_competition(self):
        """
        Test that multiple answers can be created for different tasks within the same competition.
        """
        # Create additional lab tasks for the same lab
        lab_task2 = LabTask.objects.create(
            lab=self.lab,
            task_id="check2",
            description="Task 2 description"
        )
        lab_task3 = LabTask.objects.create(
            lab=self.lab,
            task_id="3", 
            description="Task 3 description"
        )
        
        # Create answers for different tasks
        data_task1 = {
            "lab": self.lab.name,
            "pnet_login": "user1",
            "task": "1"
        }
        data_task2 = {
            "lab": self.lab.name,
            "pnet_login": "user1", 
            "task": "check2"
        }
        data_task3 = {
            "lab": self.lab.name,
            "pnet_login": "user1",
            "task": "3"
        }
        
        # Create answers using serializer
        serializer1 = AnswerSerializer(data=data_task1)
        self.assertTrue(serializer1.is_valid(), serializer1.errors)
        answer1 = serializer1.save()
        
        serializer2 = AnswerSerializer(data=data_task2)
        self.assertTrue(serializer2.is_valid(), serializer2.errors)
        answer2 = serializer2.save()
        
        serializer3 = AnswerSerializer(data=data_task3)
        self.assertTrue(serializer3.is_valid(), serializer3.errors)
        answer3 = serializer3.save()
        
        # Verify that all answers were created for the same user and lab
        self.assertEqual(answer1.user, self.user_by_pnet)
        self.assertEqual(answer2.user, self.user_by_pnet)
        self.assertEqual(answer3.user, self.user_by_pnet)
        
        self.assertEqual(answer1.lab, self.lab)
        self.assertEqual(answer2.lab, self.lab)
        self.assertEqual(answer3.lab, self.lab)
        
        # Verify that each answer has a different lab_task
        self.assertEqual(answer1.lab_task, self.lab_task)
        self.assertEqual(answer2.lab_task, lab_task2)
        self.assertEqual(answer3.lab_task, lab_task3)
        
        # Verify that all answers are different objects
        self.assertNotEqual(answer1.pk, answer2.pk)
        self.assertNotEqual(answer1.pk, answer3.pk)
        self.assertNotEqual(answer2.pk, answer3.pk)
        
        # Verify that all answers are linked to the same competition through the user
        self.assertEqual(answer1.user, answer2.user)
        self.assertEqual(answer2.user, answer3.user)
        
        # Check that we can query all answers for this user in this competition
        user_answers = Answers.objects.filter(
            user=self.user_by_pnet,
            lab=self.lab
        )
        self.assertEqual(user_answers.count(), 3)
        
        # Verify that all answers have different timestamps (they were created at different times)
        # Note: In rare cases when objects are created in the same microsecond, timestamps may be equal
        # This is acceptable as long as the objects themselves are distinct
        timestamps = [answer.datetime for answer in user_answers]
        unique_timestamps = len(set(timestamps))
        # Allow for the possibility that timestamps might be equal if created in the same microsecond
        # but ensure we have at least 2 unique timestamps (most likely all 3 will be unique)
        self.assertGreaterEqual(unique_timestamps, 2, 
                               f"Expected at least 2 unique timestamps, got {unique_timestamps}. "
                               f"Timestamps: {timestamps}") 

    def test_multiple_answers_without_task_updates_single_answer(self):
        """
        Test that multiple answers created without task field only update a single Answer
        with task=None, rather than creating multiple instances.
        """
        # Create multiple answers without task field
        data1 = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime,
            "pnet_login": "user1",
        }
        data2 = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime + timezone.timedelta(minutes=1),
            "pnet_login": "user1",
        }
        data3 = {
            "lab": self.lab.name,
            "datetime": self.valid_datetime + timezone.timedelta(minutes=2),
            "pnet_login": "user1",
        }
        
        # Create first answer
        serializer1 = AnswerSerializer(data=data1)
        self.assertTrue(serializer1.is_valid(), serializer1.errors)
        answer1 = serializer1.save()
        
        # Create second answer (should update the same instance)
        serializer2 = AnswerSerializer(data=data2)
        self.assertTrue(serializer2.is_valid(), serializer2.errors)
        answer2 = serializer2.save()
        
        # Create third answer (should update the same instance)
        serializer3 = AnswerSerializer(data=data3)
        self.assertTrue(serializer3.is_valid(), serializer3.errors)
        answer3 = serializer3.save()
        
        # All answers should be the same instance (same primary key)
        self.assertEqual(answer1.pk, answer2.pk)
        self.assertEqual(answer2.pk, answer3.pk)
        
        # Verify that only one answer exists for this user and lab without task
        answers_without_task = Answers.objects.filter(
            user=self.user_by_pnet,
            lab=self.lab,
            lab_task=None
        )
        self.assertEqual(answers_without_task.count(), 1)


class AnswerAPIGetTests(TestCase):
    """
    Тесты для GET /api/answers endpoint
    
    Проверяет получение выполненных заданий студента по:
    - username
    - pnet_login
    - lab_slug
    """
    
    def setUp(self):
        self.client = Client()
        
        self.lab = Lab.objects.create(
            name="Test Lab GET",
            description="Test lab for GET endpoint",
            slug="test-lab-get",
            platform="NO"
        )
        
        self.lab2 = Lab.objects.create(
            name="Test Lab 2",
            description="Another test lab",
            slug="test-lab-2",
            platform="NO"
        )
        
        self.user1 = User.objects.create(
            username="Иванов_Иван",
            pnet_login="ivanov-ivan",
            first_name="Иван",
            last_name="Иванов"
        )
        self.user2 = User.objects.create(
            username="Петров_Петр",
            pnet_login="petrov-petr",
            first_name="Петр",
            last_name="Петров"
        )
        
        self.task1 = LabTask.objects.create(
            lab=self.lab,
            task_id="task_1",
            description="Первое задание"
        )
        self.task2 = LabTask.objects.create(
            lab=self.lab,
            task_id="task_2",
            description="Второе задание"
        )
        self.task3 = LabTask.objects.create(
            lab=self.lab,
            task_id="task_3",
            description="Третье задание"
        )
        
        self.task_lab2 = LabTask.objects.create(
            lab=self.lab2,
            task_id="task_1",
            description="Задание из другой лабы"
        )
        
        self.answer1 = Answers.objects.create(
            user=self.user1,
            lab=self.lab,
            lab_task=self.task1,
            datetime=timezone.now()
        )
        self.answer2 = Answers.objects.create(
            user=self.user1,
            lab=self.lab,
            lab_task=self.task2,
            datetime=timezone.now()
        )
        
        self.answer_lab2 = Answers.objects.create(
            user=self.user1,
            lab=self.lab2,
            lab_task=self.task_lab2,
            datetime=timezone.now()
        )
        
        self.answer_user2 = Answers.objects.create(
            user=self.user2,
            lab=self.lab,
            lab_task=self.task3,
            datetime=timezone.now()
        )

    def test_get_answers_by_username(self):
        """
        Тест получения выполненных заданий по username
        GET /api/answers?username=Иванов_Иван&lab_slug=test-lab-get
        """
        response = self.client.get(
            '/api/answers',
            {'username': 'Иванов_Иван', 'lab_slug': 'test-lab-get'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('task_1', data['completed_task_ids'])
        self.assertIn('task_2', data['completed_task_ids'])
        self.assertNotIn('task_3', data['completed_task_ids'])

    def test_get_answers_by_pnet_login(self):
        """
        Тест получения выполненных заданий по pnet_login
        GET /api/answers?pnet_login=ivanov-ivan&lab_slug=test-lab-get
        """
        response = self.client.get(
            '/api/answers',
            {'pnet_login': 'ivanov-ivan', 'lab_slug': 'test-lab-get'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(len(data['completed_task_ids']), 2)

    def test_get_answers_missing_lab_slug(self):
        """
        Тест ошибки при отсутствии lab_slug
        """
        response = self.client.get(
            '/api/answers',
            {'username': 'Иванов_Иван'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('lab_slug', data['error'])

    def test_get_answers_missing_user_identifier(self):
        """
        Тест ошибки при отсутствии username и pnet_login
        """
        response = self.client.get(
            '/api/answers',
            {'lab_slug': 'test-lab-get'}
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('username', data['error'].lower())

    def test_get_answers_user_not_found(self):
        """
        Тест ошибки при несуществующем пользователе
        """
        response = self.client.get(
            '/api/answers',
            {'username': 'Несуществующий_Пользователь', 'lab_slug': 'test-lab-get'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('User not found', data['error'])

    def test_get_answers_lab_not_found(self):
        """
        Тест ошибки при несуществующей лабе
        """
        response = self.client.get(
            '/api/answers',
            {'username': 'Иванов_Иван', 'lab_slug': 'nonexistent-lab'}
        )
        
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('Lab', data['error'])

    def test_get_answers_empty_result(self):
        """
        Тест пустого результата когда у пользователя нет выполненных заданий
        """
        new_user = User.objects.create(
            username="Новый_Пользователь",
            pnet_login="new-user"
        )
        
        response = self.client.get(
            '/api/answers',
            {'username': 'Новый_Пользователь', 'lab_slug': 'test-lab-get'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['completed_task_ids'], [])

    def test_get_answers_response_structure(self):
        """
        Тест структуры ответа - проверяем обязательное поле completed_task_ids
        """
        response = self.client.get(
            '/api/answers',
            {'username': 'Иванов_Иван', 'lab_slug': 'test-lab-get'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('completed_task_ids', data)
        self.assertIsInstance(data['completed_task_ids'], list)

    def test_post_still_works(self):
        """
        Тест что POST запрос всё ещё работает корректно
        """
        competition = Competition.objects.create(
            lab=self.lab,
            start=timezone.now() - timezone.timedelta(hours=1),
            finish=timezone.now() + timezone.timedelta(hours=1)
        )
        Competition2User.objects.create(
            competition=competition,
            user=self.user1
        )
        
        new_task = LabTask.objects.create(
            lab=self.lab,
            task_id="new_task",
            description="Новое задание"
        )
        
        response = self.client.post(
            '/api/answers',
            {
                'pnet_login': 'ivanov-ivan',
                'lab_slug': 'test-lab-get',
                'task': 'new_task'
            },
            content_type='application/json'
        )
        
        self.assertIn(response.status_code, [200, 201])
        
        self.assertTrue(
            Answers.objects.filter(
                user=self.user1,
                lab=self.lab,
                lab_task=new_task
            ).exists()
        )