from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from interface.models import User, Lab, Competition, Competition2User, Answers, LabLevel, Team, TeamCompetition2Team, \
    TeamCompetition
from interface.api_utils import get_issue
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase, APIClient
import json


class GetIssueTests(TestCase):
    def setUp(self):
        # Common test data
        self.user = User.objects.create(username='testuser', pnet_login='pnetlogin')
        self.lab = Lab.objects.create(name='Chemistry Lab', answer_flag=None)

        # For demonstration, create a competition and link it with user
        self.competition = Competition.objects.create(
            lab=self.lab,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        self.issue = Competition2User.objects.create(
            competition=self.competition,
            user=self.user
        )

        # We might vary `competition_filters` in different tests
        self.competition_filters = {'competition__finish__gt': timezone.now()}

    def test_get_issue_missing_username_and_pnet_login(self):
        """
        Should return (None, JsonResponse) with 400 status if username/pnet_login not provided.
        """
        data = {'lab': 'Chemistry Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        self.assertIsNone(issue)
        self.assertIsInstance(error_response, JsonResponse)
        self.assertEqual(error_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertJSONEqual(
            error_response.content,
            {"message": "Wrong request format"}
        )

    def test_get_issue_missing_lab_and_lab_slug(self):
        """
        Should return (None, JsonResponse) with 400 if lab or lab_slug not provided.
        """
        data = {'username': 'testuser'}
        issue, error_response = get_issue(data, self.competition_filters)
        self.assertIsNone(issue)
        self.assertIsInstance(error_response, JsonResponse)
        self.assertEqual(error_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertJSONEqual(
            error_response.content,
            {"message": "Wrong request format"}
        )

    def test_get_issue_user_does_not_exist(self):
        """
        Should return (None, 404) if user does not exist.
        """
        data = {'username': 'nonexisting', 'lab': 'Chemistry Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        self.assertIsNone(issue)
        self.assertEqual(error_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertJSONEqual(
            error_response.content,
            {"message": "User or lab does not exist"}
        )

    def test_get_issue_lab_does_not_exist(self):
        """
        Should return (None, 404) if lab does not exist.
        """
        data = {'username': 'testuser', 'lab': 'Wrong Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        self.assertIsNone(issue)
        self.assertEqual(error_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertJSONEqual(
            error_response.content,
            {"message": "No such issue"}
        )

    def test_get_issue_issue_does_not_exist(self):
        """
        If no Competition2User is found, return (None, 404).
        """
        # We'll pass a competition filter that definitely won't match
        data = {'username': 'testuser', 'lab': 'Chemistry Lab'}
        issue, error_response = get_issue(data, {'competition__finish__lt': timezone.now()})
        self.assertIsNone(issue)
        self.assertEqual(error_response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertJSONEqual(
            error_response.content,
            {"message": "No such issue"}
        )

    def test_get_issue_success(self):
        """
        Should return (issue, None) if everything is valid and lab.answer_flag=False.
        """
        data = {'username': 'testuser', 'lab': 'Chemistry Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertEqual(issue.id, self.issue.id)


class TeamGetIssueTests(TestCase):
    def setUp(self):
        # Create a user, lab, competition, team, and link them.
        self.user = User.objects.create(username='teamuser', pnet_login='teamlogin')
        self.lab = Lab.objects.create(name='Biology Lab', answer_flag='flag')
        self.competition = TeamCompetition.objects.create(
            lab=self.lab,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        self.team = Team.objects.create(name='Team Alpha')
        self.team.users.add(self.user)
        self.issue = TeamCompetition2Team.objects.create(
            competition=self.competition,
            team=self.team
        )
        self.competition_filters = {'competition__finish__gt': timezone.now()}

    def test_get_issue_team_success(self):
        """
        Should return a team issue if the user belongs to a team in the competition.
        """
        data = {'username': 'teamuser', 'lab': 'Biology Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertTrue(hasattr(issue, 'team'))
        self.assertEqual(issue.team, self.team)


class StartLabViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create(username='testuser', pnet_login='pnetlogin', last_name='Doe')
        self.lab = Lab.objects.create(name='Chemistry Lab', answer_flag='flag')
        self.competition = Competition.objects.create(
            lab=self.lab,
            start=timezone.now(),
            finish=timezone.now() + timezone.timedelta(days=1)
        )
        self.issue = Competition2User.objects.create(
            competition=self.competition,
            user=self.user
        )

        self.url = reverse('interface_api:start-lab')

    def test_start_lab_with_valid_data(self):
        """
        If valid data is sent, we expect a 200 response and the correct JSON structure.
        """
        self.issue.level = LabLevel.objects.create(level_number=1, lab=self.lab)
        self.issue.save()

        request_data = {
            "username": "testuser",
            "lab": "Chemistry Lab"
        }
        response = self.client.generic(
            method='GET',
            path=self.url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("variant", data)
        self.assertIn("task", data)
        self.assertIn("tasks", data)
        self.assertIn("flag", data)
        self.assertIn("type", data)

        # Ensure these are what we expect
        self.assertEqual(data["variant"], self.issue.level.level_number)
        self.assertEqual(data["flag"], self.lab.answer_flag)
        self.assertEqual(data["type"], self.lab.lab_type)
        self.assertIsInstance(data["tasks"], list)

    def test_start_lab_with_invalid_data(self):
        """
        If invalid data is sent, we expect an error response (400 or 404).
        """
        request_data = {
            "username": "",  # missing username/pnet_login
            "lab": ""
        }
        response = self.client.generic(
            method='GET',
            path=self.url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertIn(response.status_code, [400, 404])
        data = json.loads(response.content)
        self.assertIn("message", data)

    def test_start_lab_no_such_issue(self):
        """
        If there's no matching Competition2User, expect 404 with error message.
        """
        # Provide a lab that doesn't match
        request_data = {
            "username": "testuser",
            "lab": "NonExistingLab"
        }
        response = self.client.generic(
            method='GET',
            path=self.url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data["message"], "No such issue")  # or "No such issue"


class StartLabViewTeamTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='testuser', pnet_login='pnetlogin', last_name='Doe')
        self.lab = Lab.objects.create(name='Chemistry Lab', answer_flag='flag')
        self.competition = TeamCompetition.objects.create(
            lab=self.lab,
            start=timezone.now(),
            finish=timezone.now() + timezone.timedelta(days=1)
        )
        # Create a Competition2User issue (might be created by default)
        self.issue = Competition2User.objects.create(
            competition=self.competition,
            user=self.user
        )
        # Create a team and assign it to the issue via a TeamCompetition2Team record.
        self.team = Team.objects.create(name="Team Beta")
        self.team.users.add(self.user)
        self.team_issue = TeamCompetition2Team.objects.create(
            competition=self.competition,
            team=self.team
        )
        self.url = reverse('interface_api:start-lab')

    def test_start_lab_with_team(self):
        """
        Should return team details in the JSON response if the issue is a team issue.
        """
        request_data = {"username": "testuser", "lab": "Chemistry Lab"}
        response = self.client.generic(
            method='GET',
            path=self.url,
            data=json.dumps(request_data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn("team", data)
        self.assertIn("type", data)
        self.assertEqual(data["team"], [self.user.pnet_login])
        self.assertEqual(data["type"], self.lab.lab_type)


class EndLabViewTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create(username='testuser', pnet_login='pnetlogin')
        self.lab = Lab.objects.create(name='Chemistry Lab', answer_flag=None)
        self.competition = Competition.objects.create(
            lab=self.lab,
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(days=1)
        )
        self.issue = Competition2User.objects.create(
            competition=self.competition,
            user=self.user
        )
        self.url = reverse('interface_api:end-lab')

    def test_end_lab_successful(self):
        """
        If valid data is sent, we expect to create an Answers object and return success message.
        """
        request_data = {
            "username": "testuser",
            "lab": "Chemistry Lab"
        }
        response = self.client.post(self.url, request_data, format='json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["message"], "Task finished")
        # Check that an Answers object was created
        self.assertTrue(Answers.objects.filter(user=self.user, lab=self.lab).exists())

    def test_end_lab_missing_fields(self):
        """
        If missing fields, we expect an error response.
        """
        request_data = {
            "username": "",
            "lab": ""
        }
        response = self.client.post(self.url, request_data, format='json')
        self.assertIn(response.status_code, [400, 404])
        data = json.loads(response.content)
        self.assertIn("message", data)


class EndLabViewTeamTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='testuser', pnet_login='pnetlogin')
        self.lab = Lab.objects.create(name='Chemistry Lab', answer_flag=None)
        self.competition = TeamCompetition.objects.create(
            lab=self.lab,
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(days=1)
        )
        # Instead of a Competition2User issue, create a team issue.
        self.team = Team.objects.create(name="Team Gamma")
        self.team.users.add(self.user)
        self.issue = TeamCompetition2Team.objects.create(
            competition=self.competition,
            team=self.team
        )
        self.url = reverse('interface_api:end-lab')

    def test_end_lab_team_successful(self):
        """
        Should create an Answers object linked to the team if the issue is a team issue.
        """
        request_data = {"username": "testuser", "lab": "Chemistry Lab"}
        response = self.client.post(self.url, request_data, format='json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["message"], "Task finished")
        # Verify that an Answers object was created with the team field set.
        self.assertTrue(Answers.objects.filter(team=self.team, lab=self.lab).exists())


class LabTypePriorityTests(TestCase):
    """
    Тесты для проверки сортировки по приоритету lab_type:
    EXAM < PZ < COMPETITION < HW
    """
    
    def setUp(self):
        # Создаем пользователя
        self.user = User.objects.create(username='priorityuser', pnet_login='prioritylogin')
        
        # Создаем лабораторные работы с одинаковым именем, но разными типами
        self.lab_exam = Lab.objects.create(
            name='Same Name Lab', 
            lab_type='EXAM',
            answer_flag='exam_flag'
        )
        self.lab_pz = Lab.objects.create(
            name='Same Name Lab', 
            lab_type='PZ',
            answer_flag='pz_flag'
        )
        self.lab_competition = Lab.objects.create(
            name='Same Name Lab', 
            lab_type='COMPETITION',
            answer_flag='competition_flag'
        )
        self.lab_hw = Lab.objects.create(
            name='Same Name Lab', 
            lab_type='HW',
            answer_flag='hw_flag'
        )
        
        # Создаем соревнования для каждой лабораторной работы
        self.competition_exam = Competition.objects.create(
            lab=self.lab_exam,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        self.competition_pz = Competition.objects.create(
            lab=self.lab_pz,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        self.competition_competition = Competition.objects.create(
            lab=self.lab_competition,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        self.competition_hw = Competition.objects.create(
            lab=self.lab_hw,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        
        # Создаем записи Competition2User для всех соревнований
        self.issue_exam = Competition2User.objects.create(
            competition=self.competition_exam,
            user=self.user
        )
        self.issue_pz = Competition2User.objects.create(
            competition=self.competition_pz,
            user=self.user
        )
        self.issue_competition = Competition2User.objects.create(
            competition=self.competition_competition,
            user=self.user
        )
        self.issue_hw = Competition2User.objects.create(
            competition=self.competition_hw,
            user=self.user
        )
        
        self.competition_filters = {'competition__finish__gt': timezone.now()}

    def test_priority_exam_over_others(self):
        """
        При наличии всех типов лабораторных работ должен выбираться EXAM
        """
        data = {'username': 'priorityuser', 'lab': 'Same Name Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertEqual(issue.competition.lab.lab_type, 'EXAM')
        self.assertEqual(issue.competition.lab.answer_flag, 'exam_flag')

    def test_priority_pz_over_competition_and_hw(self):
        """
        При отсутствии EXAM должен выбираться PZ
        """
        # Удаляем запись для EXAM
        self.issue_exam.delete()
        
        data = {'username': 'priorityuser', 'lab': 'Same Name Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertEqual(issue.competition.lab.lab_type, 'PZ')
        self.assertEqual(issue.competition.lab.answer_flag, 'pz_flag')

    def test_priority_competition_over_hw(self):
        """
        При отсутствии EXAM и PZ должен выбираться COMPETITION
        """
        # Удаляем записи для EXAM и PZ
        self.issue_exam.delete()
        self.issue_pz.delete()
        
        data = {'username': 'priorityuser', 'lab': 'Same Name Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertEqual(issue.competition.lab.lab_type, 'COMPETITION')
        self.assertEqual(issue.competition.lab.answer_flag, 'competition_flag')

    def test_priority_hw_last(self):
        """
        При отсутствии всех других типов должен выбираться HW
        """
        # Удаляем записи для EXAM, PZ и COMPETITION
        self.issue_exam.delete()
        self.issue_pz.delete()
        self.issue_competition.delete()
        
        data = {'username': 'priorityuser', 'lab': 'Same Name Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertEqual(issue.competition.lab.lab_type, 'HW')
        self.assertEqual(issue.competition.lab.answer_flag, 'hw_flag')

    def test_priority_with_team_competitions(self):
        """
        Проверяем приоритет с командными соревнованиями
        """
        # Создаем команду
        self.team = Team.objects.create(name='Priority Team')
        self.team.users.add(self.user)
        
        # Создаем командные соревнования
        self.team_competition_exam = TeamCompetition.objects.create(
            lab=self.lab_exam,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        self.team_competition_pz = TeamCompetition.objects.create(
            lab=self.lab_pz,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        
        # Создаем записи TeamCompetition2Team
        self.team_issue_exam = TeamCompetition2Team.objects.create(
            competition=self.team_competition_exam,
            team=self.team
        )
        self.team_issue_pz = TeamCompetition2Team.objects.create(
            competition=self.team_competition_pz,
            team=self.team
        )
        
        # Тестируем приоритет EXAM над PZ в командных соревнованиях
        data = {'username': 'priorityuser', 'lab': 'Same Name Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertTrue(hasattr(issue, 'team'))
        self.assertEqual(issue.competition.lab.lab_type, 'EXAM')

    def test_priority_mixed_team_individual_same_name(self):
        """
        Проверяем приоритет между командными и индивидуальными соревнованиями 
        с одинаковым именем лаборатории
        """
        # Создаем команду
        self.team = Team.objects.create(name='Mixed Priority Team')
        self.team.users.add(self.user)
        
        # Создаем командные соревнования для существующих лабораторий
        self.competition_exam_team = TeamCompetition.objects.create(
            lab=self.lab_exam,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        self.competition_pz_team = TeamCompetition.objects.create(
            lab=self.lab_pz,
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2)
        )
        
        # Создаем записи для командных соревнований
        self.issue_exam_team = TeamCompetition2Team.objects.create(
            competition=self.competition_exam_team,
            team=self.team
        )
        self.issue_pz_team = TeamCompetition2Team.objects.create(
            competition=self.competition_pz_team,
            team=self.team
        )
        
        # Тестируем: должен выбрать командное EXAM (командные имеют приоритет над индивидуальными)
        data = {'username': 'priorityuser', 'lab': 'Same Name Lab'}
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertTrue(hasattr(issue, 'team'))
        self.assertEqual(issue.competition.lab.lab_type, 'EXAM')
        self.assertEqual(issue.competition.lab.answer_flag, 'exam_flag')
        
        # Удаляем командное EXAM, должен выбрать командное PZ
        self.issue_exam_team.delete()
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertTrue(hasattr(issue, 'team'))
        self.assertEqual(issue.competition.lab.lab_type, 'PZ')
        self.assertEqual(issue.competition.lab.answer_flag, 'pz_flag')
        
        # Удаляем командное PZ, должен выбрать индивидуальное EXAM
        self.issue_pz_team.delete()
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertFalse(hasattr(issue, 'team'))
        self.assertEqual(issue.competition.lab.lab_type, 'EXAM')
        self.assertEqual(issue.competition.lab.answer_flag, 'exam_flag')
        
        # Удаляем индивидуальное EXAM, должен выбрать индивидуальное PZ
        self.issue_exam.delete()
        issue, error_response = get_issue(data, self.competition_filters)
        
        self.assertIsNotNone(issue)
        self.assertIsNone(error_response)
        self.assertFalse(hasattr(issue, 'team'))
        self.assertEqual(issue.competition.lab.lab_type, 'PZ')
        self.assertEqual(issue.competition.lab.answer_flag, 'pz_flag')
