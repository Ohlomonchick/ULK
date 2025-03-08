from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from interface.models import (
    TeamCompetition,
    Lab,
    Answers,
    User,
    TeamCompetition2Team,
    Team, Competition2User, LabTask  # Assumes your Team model has a ManyToManyField named 'users'
)


class TeamCompetitionDetailViewTeamTest(TestCase):
    def setUp(self):
        # Create a user who is a team member.
        self.team_user = User.objects.create_user(username="teamuser", password="testpass")

        # Create a Lab with a known answer_flag.
        self.lab = Lab.objects.create(
            name="Test Lab Team",
            description="Test description",
            answer_flag="CORRECT_FLAG",
            slug="test-lab-team",
            platform="NO",
            NodesData=[],
            ConnectorsData=[],
            Connectors2CloudData=[],
            NetworksData=[]
        )

        # Create a TeamCompetition instance.
        self.competition = TeamCompetition.objects.create(
            slug="team-test-competition-detail-team",
            lab=self.lab,
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            participants=1
        )

        # Create a Team and add the team_user.
        self.team = Team.objects.create(name="Test Team")
        # Assuming the Team model has a ManyToManyField named 'users'
        self.team.users.add(self.team_user)

        # Link the team to the competition via the through model.
        self.team_comp_relation = TeamCompetition2Team.objects.create(
            competition=self.competition,
            team=self.team
        )

        # Create a LabTask and assign it to TeamCompetition2Team tasks.
        self.task = LabTask.objects.create(
            lab=self.lab,
            task_id="T2",
            description="Team Task description"
        )
        self.team_comp_relation.tasks.add(self.task)

    def test_team_view_no_answer(self):
        """
        For a team member who has not submitted an answer:
          - The view should show available = True and submitted = False.
        """
        self.client.login(username="teamuser", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("submitted", False))
        self.assertTrue(response.context.get("available", False))

    def test_team_view_correct_answer_flag(self):
        """
        When a team member submits the correct answer_flag:
          - An Answers record is created with the team field (and not the user field).
          - The view context shows submitted = True and available becomes False.
        """
        self.client.login(username="teamuser", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url, {"answer_flag": "CORRECT_FLAG"})
        self.assertEqual(response.status_code, 200)
        # Verify that an Answer record for the team was created.
        answer_exists = Answers.objects.filter(team=self.team, lab=self.lab).exists()
        self.assertTrue(answer_exists, "An Answers object should have been created for the team with a correct flag.")
        self.assertTrue(response.context.get("submitted", False))
        self.assertFalse(response.context.get("available", True))

    def test_team_view_preexisting_answer(self):
        """
        If an Answers record for the team exists before the view is loaded,
        the context should indicate submitted = True and available = False.
        """
        # Create an Answer record for the team.
        Answers.objects.create(team=self.team, lab=self.lab, datetime=timezone.now())
        self.client.login(username="teamuser", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("submitted", False))
        self.assertFalse(response.context.get("available", True))

    def test_assigned_tasks_team(self):
        self.client.login(username="teamuser", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        assigned_tasks = response.context.get("assigned_tasks", [])
        self.assertEqual(len(assigned_tasks), 1)


class TeamCompetitionDetailViewIndividualFallbackTest(TestCase):
    def setUp(self):
        # Create an individual user (not in any team)
        self.individual_user = User.objects.create_user(username="individual", password="testpass")

        # Create a Lab with required fields.
        self.lab = Lab.objects.create(
            name="Individual Fallback Lab",
            description="Lab for fallback test",
            answer_flag="CORRECT_FLAG",
            slug="individual-fallback-lab",
            platform="NO",
            NodesData=[],
            ConnectorsData=[],
            Connectors2CloudData=[],
            NetworksData=[]
        )

        # Create a TeamCompetition instance.
        self.competition = TeamCompetition.objects.create(
            slug="team-competition-individual-fallback",
            lab=self.lab,
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            participants=1
        )
        # Add the individual user to non_platoon_users and create a Competition2User record.
        self.competition.non_platoon_users.add(self.individual_user)
        Competition2User.objects.create(
            competition=self.competition,
            user=self.individual_user
        )

        # Create a LabTask and assign it to the Competition2User.
        self.task = LabTask.objects.create(
            lab=self.lab,
            task_id="T1",
            description="Individual Task"
        )
        comp2user = Competition2User.objects.get(competition=self.competition, user=self.individual_user)
        comp2user.tasks.add(self.task)

    def test_individual_fallback_no_answer(self):
        """
        If an individual user (not in a team) visits the team detail view without an answer flag,
        the fallback logic should mark 'submitted' = False and 'available' = True.
        """
        self.client.login(username="individual", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("submitted", False))
        self.assertTrue(response.context.get("available", False))

    def test_individual_fallback_correct_answer_flag(self):
        """
        When an individual user submits the correct answer flag at the team detail view,
        the fallback logic should create an Answer with the user field (not team) and set submitted=True.
        """
        self.client.login(username="individual", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url, {"answer_flag": "CORRECT_FLAG"})
        self.assertEqual(response.status_code, 200)
        # Verify that an Answer record is created with the user field.
        answer_exists = Answers.objects.filter(user=self.individual_user, lab=self.lab).exists()
        self.assertTrue(answer_exists, "Expected an Answer object for the individual user.")
        self.assertTrue(response.context.get("submitted", False))
        self.assertFalse(response.context.get("available", True))

    def test_individual_fallback_preexisting_answer(self):
        """
        If an Answer record for the individual exists before the view is loaded,
        fallback logic should set submitted=True and available=False.
        """
        Answers.objects.create(user=self.individual_user, lab=self.lab, datetime=timezone.now())
        self.client.login(username="individual", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context.get("submitted", False))
        self.assertFalse(response.context.get("available", True))

    def test_individual_fallback_assigned_tasks(self):
        """
        The view should populate assigned_tasks from the Competition2User record for individual fallback users.
        """
        self.client.login(username="individual", password="testpass")
        url = reverse("interface:team-competition-detail", kwargs={"slug": self.competition.slug})
        response = self.client.get(url)
        assigned_tasks = response.context.get("assigned_tasks", [])
        self.assertIn(self.task, assigned_tasks)
