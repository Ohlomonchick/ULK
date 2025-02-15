from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from interface.models import User, Lab, Competition, Competition2User, Answers, LabLevel
from interface.api import get_issue
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
            {"message": "User or lab does not exist"}
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

        # Ensure these are what we expect
        self.assertEqual(data["variant"], self.issue.level.level_number)
        self.assertEqual(data["flag"], self.lab.answer_flag)
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
        self.assertEqual(data["message"], "User or lab does not exist")  # or "No such issue"


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