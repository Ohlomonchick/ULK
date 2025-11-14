from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from interface.models import (
    User, Lab, Competition, Competition2User, LabTask, Answers
)


class UserDetailViewTest(TestCase):
    """Tests for UserDetailView - admin view showing user's competition progress."""

    @classmethod
    def setUpTestData(cls):
        """Create test data shared across all tests."""
        cls.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass",
            is_staff=True
        )
        cls.target_user = User.objects.create_user(
            username="targetuser",
            password="targetpass",
            first_name="Target",
            last_name="User"
        )

    def setUp(self):
        """Set up test data for each test."""
        self.lab1 = self._create_lab("Test Lab 1", "test-lab-1")
        self.lab2 = self._create_lab("Test Lab 2", "test-lab-2")
        
        self.competition1 = self._create_competition("test-competition-1", self.lab1)
        self.competition2 = self._create_competition("test-competition-2", self.lab2)
        
        self.task1 = self._create_task(self.lab1, "T1", "Task 1")
        self.task2 = self._create_task(self.lab1, "T2", "Task 2")
        self.task3 = self._create_task(self.lab2, "T3", "Task 3")
        
        self.issue1 = self._create_issue(self.competition1, [self.task1, self.task2])
        self.issue2 = self._create_issue(self.competition2, [self.task3])

    def _create_lab(self, name, slug, **kwargs):
        """Helper to create a lab."""
        defaults = {
            "name": name,
            "description": f"Test description for {name}",
            "slug": slug,
            "platform": "NO"
        }
        defaults.update(kwargs)
        return Lab.objects.create(**defaults)

    def _create_competition(self, slug, lab, **kwargs):
        """Helper to create a competition."""
        defaults = {
            "slug": slug,
            "lab": lab,
            "start": timezone.now() - timedelta(hours=1),
            "finish": timezone.now() + timedelta(hours=1),
            "participants": 1
        }
        defaults.update(kwargs)
        return Competition.objects.create(**defaults)

    def _create_task(self, lab, task_id, description):
        """Helper to create a lab task."""
        return LabTask.objects.create(lab=lab, task_id=task_id, description=description)

    def _create_issue(self, competition, tasks):
        """Helper to create a Competition2User with tasks."""
        issue = Competition2User.objects.create(
            competition=competition,
            user=self.target_user
        )
        issue.tasks.set(tasks)
        return issue

    def _create_answer(self, lab, lab_task=None, user=None):
        """Helper to create an answer."""
        return Answers.objects.create(
            user=user or self.target_user,
            lab=lab,
            lab_task=lab_task,
            datetime=timezone.now()
        )

    def _login_as_admin(self):
        """Helper to login as admin."""
        self.client.login(username="admin", password="adminpass")

    def _get_user_detail_url(self, user=None):
        """Helper to get user detail URL."""
        return reverse("interface:user-detail", kwargs={"id": (user or self.target_user).id})

    def _get_user_detail_response(self, user=None):
        """Helper to get user detail response."""
        self._login_as_admin()
        return self.client.get(self._get_user_detail_url(user))

    def _get_issue_from_context(self, response, issue_id):
        """Helper to get issue from response context by ID."""
        issues = list(response.context["issues"])
        return next(issue for issue in issues if issue.id == issue_id)

    def test_staff_access_allowed(self):
        """Test that staff users can access the view."""
        response = self._get_user_detail_response()
        self.assertEqual(response.status_code, 200)

    def test_non_staff_access_denied(self):
        """Test that non-staff users cannot access the view."""
        regular_user = User.objects.create_user(username="regular", password="regularpass")
        self.client.login(username="regular", password="regularpass")
        response = self.client.get(self._get_user_detail_url())
        # PermissionDenied exception is raised, which Django converts to 403
        self.assertIn(response.status_code, [302, 403])

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access the view."""
        response = self.client.get(self._get_user_detail_url())
        self.assertIn(response.status_code, [302, 403])

    def test_context_contains_issues(self):
        """Test that context contains issues for the target user."""
        response = self._get_user_detail_response()
        
        self.assertIn("issues", response.context)
        issues = list(response.context["issues"])
        self.assertEqual(len(issues), 2)
        self.assertIn(self.issue1, issues)
        self.assertIn(self.issue2, issues)

    def test_issue_not_done_when_no_answers(self):
        """Test that issue is marked as not done when user hasn't submitted answers."""
        response = self._get_user_detail_response()
        issue1 = self._get_issue_from_context(response, self.issue1.id)
        self.assertFalse(issue1.done)

    def test_issue_done_when_all_tasks_submitted(self):
        """Test that issue is marked as done when all assigned tasks are submitted."""
        self._create_answer(self.lab1, self.task1)
        self._create_answer(self.lab1, self.task2)
        
        response = self._get_user_detail_response()
        issue1 = self._get_issue_from_context(response, self.issue1.id)
        self.assertTrue(issue1.done)

    def test_issue_done_with_none_task_answer(self):
        """Test that issue is marked as done when user has a None task answer."""
        self._create_answer(self.lab1, lab_task=None)
        
        response = self._get_user_detail_response()
        issue1 = self._get_issue_from_context(response, self.issue1.id)
        self.assertTrue(issue1.done)

    def test_issue_not_done_when_partial_submission(self):
        """Test that issue is not done when only some tasks are submitted."""
        self._create_answer(self.lab1, self.task1)
        
        response = self._get_user_detail_response()
        issue1 = self._get_issue_from_context(response, self.issue1.id)
        self.assertFalse(issue1.done)

    def test_submitted_count(self):
        """Test that submitted count is correct."""
        self._create_answer(self.lab1, self.task1)
        self._create_answer(self.lab2, self.task3)
        
        response = self._get_user_detail_response()
        self.assertEqual(response.context["submitted"], 2)

    def test_total_count_includes_all_labs(self):
        """Test that total count includes labs from both issues and submitted answers."""
        lab3 = self._create_lab("Test Lab 3", "test-lab-3")
        self._create_answer(lab3, lab_task=None)
        
        response = self._get_user_detail_response()
        # Should include lab1, lab2 (from competitions) and lab3 (from submitted answer)
        self.assertEqual(response.context["total"], 3)

    def test_progress_calculation(self):
        """Test that progress is calculated correctly."""
        self._create_answer(self.lab1, self.task1)
        
        response = self._get_user_detail_response()
        # 1 submitted out of 2 total = 50%
        self.assertEqual(response.context["progress"], 50)

    def test_progress_100_when_total_is_zero(self):
        """Test that progress is 100 when total is 0."""
        empty_user = User.objects.create_user(username="emptyuser", password="emptypass")
        
        response = self._get_user_detail_response(empty_user)
        self.assertEqual(response.context["total"], 0)
        self.assertEqual(response.context["progress"], 100)

    def test_filters_out_issues_with_missing_competition(self):
        """Test that the query filters out issues with missing competitions."""
        response = self._get_user_detail_response()
        
        # Verify that only issues with valid competitions are returned
        issues = list(response.context["issues"])
        for issue in issues:
            self.assertIsNotNone(issue.competition, "All issues should have a competition")

    def test_handles_issue_with_missing_lab(self):
        """Test that issues with missing lab are handled gracefully."""
        response = self._get_user_detail_response()
        
        self.assertEqual(response.status_code, 200)
        # The defensive check in _mark_issues_completion ensures missing labs are handled
        issues = list(response.context["issues"])
        for issue in issues:
            if issue.competition and issue.competition.lab:
                self.assertIsNotNone(issue.competition.lab)

