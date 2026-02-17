"""
Тесты отображения оценки студенту
"""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from interface.models import (
    Lab,
    Competition,
    TeamCompetition,
    User,
    Competition2User,
    Team,
    TeamCompetition2Team,
)


class MyGradeAPITestCase(TestCase):
    """Тесты API my_grade — студенту показывается его оценка."""

    def setUp(self):
        self.client = APIClient()
        self.lab = Lab.objects.create(
            name="Test Lab",
            platform="NO",
            slug="test-lab-grade",
            description="",
            answer_flag=None,
            NodesData=[],
            ConnectorsData=[],
            Connectors2CloudData=[],
            NetworksData=[],
        )

    def test_my_grade_returns_grade_for_individual_competition(self):
        """Студент видит оценку по обычному соревнованию."""
        comp = Competition.objects.create(
            slug="grade-individual",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=self.lab,
        )
        user = User.objects.create_user(
            username="student1",
            password="testpass",
            first_name="Иван",
            last_name="Петров",
        )
        Competition2User.objects.create(
            competition=comp,
            user=user,
            joined=True,
            grade=5,
        )
        self.client.force_authenticate(user=user)
        url = reverse("interface_api:my_grade", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("grade", data)
        self.assertEqual(data["grade"], 5)

    def test_my_grade_returns_none_when_no_grade(self):
        """Если оценка не выставлена, возвращается null."""
        comp = Competition.objects.create(
            slug="grade-none",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=self.lab,
        )
        user = User.objects.create_user(
            username="student2",
            password="testpass",
            first_name="Мария",
            last_name="Сидорова",
        )
        Competition2User.objects.create(
            competition=comp,
            user=user,
            joined=True,
            grade=None,
        )
        self.client.force_authenticate(user=user)
        url = reverse("interface_api:my_grade", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("grade", data)
        self.assertIsNone(data["grade"])

    def test_my_grade_returns_grade_for_team_competition(self):
        """Студент в командном соревновании видит оценку команды."""
        comp = TeamCompetition.objects.create(
            slug="grade-team",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=self.lab,
        )
        team = Team.objects.create(name="Team A", slug="team-a-grade")
        user = User.objects.create_user(
            username="teamstudent",
            password="testpass",
            first_name="Олег",
            last_name="Козлов",
        )
        team.users.add(user)
        TeamCompetition2Team.objects.create(
            competition=comp,
            team=team,
            joined=True,
            grade=4,
        )
        self.client.force_authenticate(user=user)
        url = reverse("interface_api:my_grade", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("grade", data)
        self.assertEqual(data["grade"], 4)


class MyGradeRegressionTestCase(TestCase):
    """
    Регресс: для лабы оценка берётся из Competition2User — студент видит свою оценку. 
    """

    def setUp(self):
        self.client = APIClient()
        self.lab = Lab.objects.create(
            name="Regression Lab",
            platform="NO",
            slug="regression-lab",
            description="",
            answer_flag=None,
            NodesData=[],
            ConnectorsData=[],
            Connectors2CloudData=[],
            NetworksData=[],
        )

    def test_individual_competition_grade_from_competition2user(self):
        """
        Регресс: по slug лабы my_grade возвращает оценку из Competition2User.
        """
        slug = "only-individual-comp"
        comp = Competition.objects.create(
            slug=slug,
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=self.lab,
        )
        user = User.objects.create_user(
            username="regression_student",
            password="testpass",
            first_name="Регресс",
            last_name="Студент",
        )
        Competition2User.objects.create(
            competition=comp,
            user=user,
            joined=True,
            grade=5,
        )
        self.client.force_authenticate(user=user)
        url = reverse("interface_api:my_grade", kwargs={"slug": slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["grade"], 5, "Оценка должна браться из Competition2User")


class SaveGradesAndMyGradeTestCase(TestCase):
    """Сохранение оценок (в т.ч. лаба без заданий — get_or_create) и отображение студенту."""

    def setUp(self):
        self.client = APIClient()
        self.lab = Lab.objects.create(
            name="Lab No Tasks",
            platform="NO",
            slug="lab-no-tasks",
            description="",
            answer_flag="FLAG",
            NodesData=[],
            ConnectorsData=[],
            Connectors2CloudData=[],
            NetworksData=[],
        )
        self.comp = Competition.objects.create(
            slug="no-tasks-comp-grades",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=self.lab,
        )
        self.student = User.objects.create_user(
            username="nostudent",
            password="testpass",
            first_name="Нет",
            last_name="Заданий",
        )
        self.staff = User.objects.create_user(
            username="staff_grader",
            password="testpass",
            first_name="Staff",
            last_name="User",
            is_staff=True,
        )

    def test_save_grades_creates_competition2user_when_missing(self):
        """
        Лаба без заданий: записи Competition2User может не быть.
        save_grades создаёт её (get_or_create) и выставляет оценку; my_grade потом возвращает её.
        """
        self.assertFalse(
            Competition2User.objects.filter(
                competition=self.comp, user=self.student
            ).exists()
        )
        url_save = reverse("interface_api:save_grades")
        payload = {
            "slug": self.comp.slug,
            "type": "competition",
            "grades": [
                {
                    "user_id": self.student.id,
                    "user_last_name": self.student.last_name,
                    "user_first_name": self.student.first_name,
                    "grade": 4,
                }
            ],
        }
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            url_save,
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("updated"), 1)

        c2u = Competition2User.objects.get(competition=self.comp, user=self.student)
        self.assertEqual(c2u.grade, 4)

        self.client.force_authenticate(user=self.student)
        url_grade = reverse("interface_api:my_grade", kwargs={"slug": self.comp.slug})
        resp_grade = self.client.get(url_grade)
        self.assertEqual(resp_grade.status_code, 200)
        self.assertEqual(resp_grade.json()["grade"], 4)
