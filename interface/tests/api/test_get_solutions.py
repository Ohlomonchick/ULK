from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from interface.models import (
    Competition, TeamCompetition, Platoon, User, Lab, LabTask, Answers,
    Competition2User, TeamCompetition2Team, Team
)


class GetSolutionsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_no_tasks_competition(self):
        """
        Competition with zero tasks.
        - Create a Competition with no tasks.
        - Add some users (some in platoons, some in non_platoon).
        - Create Answers for only a subset.
        - Verify that each user with an answer appears with progress = 1.
        - Check that the solutions are ordered by raw_datetime ascending,
          positions are consecutive and the JSON contains correct progress totals.
        """
        lab = Lab.objects.create(
            name="Test Lab No Tasks",
            platform="PN",
            slug="lab-no-tasks",
            description="desc",
            answer_flag="FLAG",
            NodesData=[], ConnectorsData=[], Connectors2CloudData=[], NetworksData=[]
        )
        comp = Competition.objects.create(
            slug="no-tasks-comp",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=lab,
            participants=5  # assume 5 participants for calculation
        )
        # No tasks added => comp.tasks.count() == 0
        platoon = Platoon.objects.create(number=1)
        comp.platoons.add(platoon)

        # Create 3 platoon users
        platoon_users = []
        for i in range(3):
            u = User.objects.create_user(
                username=f"platoon_user_{i}",
                password="testpass",
                platoon=platoon,
                first_name=f"Platoon{i}",
                last_name="User"
            )
            platoon_users.append(u)

        # Create 2 non-platoon users
        non_platoon_users = []
        for i in range(2):
            u = User.objects.create_user(
                username=f"nop_user_{i}",
                password="testpass",
                first_name=f"NoPlatoon{i}",
                last_name="User"
            )
            non_platoon_users.append(u)

        comp.non_platoon_users.add(*non_platoon_users)
        comp.save()

        now = timezone.now()
        # Create Answers for 2 platoon users and 1 non-platoon user.
        Answers.objects.create(
            user=platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=30)
        )
        Answers.objects.create(
            user=platoon_users[1],
            lab=lab,
            datetime=now - timedelta(minutes=10)
        )
        Answers.objects.create(
            user=non_platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=5)
        )

        url = reverse("interface_api:get_solutions", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        solutions = data["solutions"]

        # Expect 5 distinct solutions (2 with zero progress).
        self.assertEqual(len(solutions), len(platoon_users) + len(non_platoon_users))
        # Positions must be 1,2,3.
        for i, sol in enumerate(solutions, start=1):
            self.assertEqual(sol["pos"], i)
        # Check that solutions are sorted ascending by raw_datetime.
        raw_datetimes = [sol["raw_datetime"] for sol in solutions]
        self.assertTrue(
            all(raw_datetimes[i] <= raw_datetimes[i + 1] for i in range(len(raw_datetimes) - 1) if raw_datetimes[i+1] is not None),
            "Solutions must be sorted ascending by raw_datetime."
        )
        # Since no tasks, each solution should have progress 1 or 0
        for sol in solutions:
            self.assertTrue(sol["progress"] == 1 or sol["progress"] == 0)
        # For no tasks, max_total_progress equals participants.
        self.assertEqual(data["max_total_progress"], comp.participants)
        # Total progress equals number of solutions (1 each).
        self.assertEqual(data["total_progress"], 3)
        # total_tasks != 1 is only added if > 0.
        self.assertEqual(data["total_tasks"], 1)

    def test_with_tasks_competition(self):
        """
        Competition WITH tasks.
        - Create a Competition with 2 LabTasks.
        - Create Answers for several users; each answer counts toward progress.
        - Verify that progress is correctly calculated,
          max_total_progress equals participants * total_tasks,
          and the solutions are sorted by progress descending then raw_datetime.
        """
        lab = Lab.objects.create(
            name="Test Lab With Tasks",
            platform="NO",
            slug="lab-with-tasks",
            description="desc",
            answer_flag="FLAG",
            NodesData=[], ConnectorsData=[], Connectors2CloudData=[], NetworksData=[]
        )
        task1 = LabTask.objects.create(lab=lab, task_id="Task1", description="desc1")
        task2 = LabTask.objects.create(lab=lab, task_id="Task2", description="desc2")

        comp = Competition.objects.create(
            slug="with-tasks-comp",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=lab,
            participants=5,
            num_tasks=2
        )
        comp.tasks.set([task1, task2])  # total_tasks = 2

        platoon = Platoon.objects.create(number=2)
        comp.platoons.add(platoon)

        # Create 3 platoon users and 2 non-platoon users.
        platoon_users = []
        for i in range(3):
            u = User.objects.create_user(
                username=f"platoon_user_{i}",
                password="testpass",
                platoon=platoon,
                first_name=f"Platoon{i}",
                last_name="User"
            )
            platoon_users.append(u)
            issue = Competition2User.objects.create(competition=comp, user=u)
            issue.tasks.add(task1, task2)
        non_platoon_users = []
        for i in range(2):
            u = User.objects.create_user(
                username=f"nop_user_{i}",
                password="testpass",
                first_name=f"NoPlatoon{i}",
                last_name="User"
            )
            non_platoon_users.append(u)
            issue = Competition2User.objects.create(competition=comp, user=u)
            issue.tasks.add(task1, task2)
            

        comp.non_platoon_users.add(*non_platoon_users)
        comp.save()

        now = timezone.now()
        # Create Answers:
        # platoon_users[0] gets 2 answers (progress 2)
        Answers.objects.create(user=platoon_users[0], lab=lab, datetime=now - timedelta(minutes=30))
        Answers.objects.create(user=platoon_users[0], lab=lab, datetime=now - timedelta(minutes=29))
        # platoon_users[1] gets 1 answer (progress 1)
        Answers.objects.create(user=platoon_users[1], lab=lab, datetime=now - timedelta(minutes=20))
        # non_platoon_users[0] gets 2 answers (progress 2)
        Answers.objects.create(user=non_platoon_users[0], lab=lab, datetime=now - timedelta(minutes=10))
        Answers.objects.create(user=non_platoon_users[0], lab=lab, datetime=now - timedelta(minutes=9))

        url = reverse("interface_api:get_solutions", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        solutions = data["solutions"]

        # Expect 5 solutions (for all users, 2 not ).
        self.assertEqual(len(solutions), len(platoon_users) + len(non_platoon_users))
        # Check progress values.
        for sol in solutions:
            if sol["user_first_name"] == "Platoon0":
                self.assertEqual(sol["progress"], 2)
            elif sol["user_first_name"] == "Platoon1":
                self.assertEqual(sol["progress"], 1)
            elif sol["user_first_name"] == "NoPlatoon0":
                self.assertEqual(sol["progress"], 2)
        # Sorting: solutions should be sorted by progress descending.
        progress_values = [sol["progress"] for sol in solutions]
        self.assertTrue(
            progress_values[0] >= progress_values[1] and progress_values[1] >= progress_values[2],
            "Solutions must be sorted by progress descending."
        )
        # Positions must be assigned sequentially.
        for i, sol in enumerate(solutions, start=1):
            self.assertEqual(sol["pos"], i)
        # max_total_progress should equal participants * total_tasks.
        self.assertEqual(data["max_total_progress"], comp.participants * 2)
        # total_tasks must be included.
        self.assertEqual(data["total_tasks"], 2)
        # total_progress equals sum of individual progress values.
        expected_total_progress = 2 + 1 + 2
        self.assertEqual(data["total_progress"], expected_total_progress)

    def test_team_competition_individual_fallback(self):
        """
        For a TeamCompetition, if a user participates individually (fallback),
        the view should use the Competition2User branch.
        Verify that the solution does NOT include a team_name and progress is counted correctly.
        """
        lab = Lab.objects.create(
            name="Team Fallback Lab",
            platform="NO",
            slug="lab-team-fallback",
            description="desc",
            answer_flag="FLAG",
            NodesData=[], ConnectorsData=[], Connectors2CloudData=[], NetworksData=[]
        )
        comp = TeamCompetition.objects.create(
            slug="team-comp-individual-fallback",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=lab,
            participants=5
        )
        # Set up individual fallback.
        individual_user = User.objects.create_user(
            username="individual", password="testpass",
            first_name="Individual", last_name="User"
        )
        comp.non_platoon_users.add(individual_user)
        Competition2User.objects.create(competition=comp, user=individual_user)

        now = timezone.now()
        Answers.objects.create(user=individual_user, lab=lab, datetime=now - timedelta(minutes=15))

        url = reverse("interface_api:get_solutions", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        solutions = data["solutions"]

        # Expect one solution.
        self.assertEqual(len(solutions), 1)
        sol = solutions[0]
        # Should not include team_name.
        self.assertEqual(sol["team_name"], "")
        self.assertEqual(sol["progress"], 1)
        self.assertEqual(data["max_total_progress"], comp.participants)
        self.assertEqual(data["total_progress"], 1)
        self.assertEqual(data["total_tasks"], 1)

    def test_team_competition_team(self):
        """
        For a TeamCompetition with team answers:
        - Create a team and add a user.
        - Create team Answers.
        - Verify that the solution for the team member includes team_name and progress equals the number of team answers.
        """
        lab = Lab.objects.create(
            name="Team Lab",
            platform="NO",
            slug="lab-team",
            description="desc",
            answer_flag="FLAG",
            NodesData=[], ConnectorsData=[], Connectors2CloudData=[], NetworksData=[]
        )
        comp = TeamCompetition.objects.create(
            slug="team-comp-team",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=lab,
            participants=5
        )
        # Create a team and add a user.
        team = Team.objects.create(name="Alpha Team")
        team_user = User.objects.create_user(
            username="teamuser", password="testpass",
            first_name="Team", last_name="User"
        )
        team.users.add(team_user)
        # Link team to competition.
        TeamCompetition2Team.objects.create(competition=comp, team=team)

        now = timezone.now()
        Answers.objects.create(team=team, lab=lab, datetime=now - timedelta(minutes=20))

        url = reverse("interface_api:get_solutions", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        solutions = data["solutions"]

        # For team, expect one solution per team member.
        self.assertEqual(len(solutions), 1)
        sol = solutions[0]
        self.assertEqual(sol["progress"], 1)    # Because two answers count as 1 if lab has no tasks
        self.assertIn("team_name", sol)
        self.assertEqual(sol["team_name"], "Alpha Team")
        self.assertEqual(data["max_total_progress"], comp.participants)
        self.assertEqual(data["total_progress"], 1)
        self.assertEqual(data["total_tasks"], 1)

    def test_sorting_mixed_individual_and_team(self):
        """
        Create a mixed scenario with both individual and team solutions.
        Verify that sorting is done by progress descending and then by raw_datetime ascending.
        """
        lab = Lab.objects.create(
            name="Mixed Lab",
            platform="NO",
            slug="lab-mixed",
            description="desc",
            answer_flag="FLAG",
            NodesData=[], ConnectorsData=[], Connectors2CloudData=[], NetworksData=[]
        )
        comp = TeamCompetition.objects.create(
            slug="mixed-comp",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=lab,
            participants=10
        )
        # Set up an individual fallback user.
        indiv = User.objects.create_user(
            username="indiv", password="testpass",
            first_name="Indiv", last_name="User"
        )
        comp.non_platoon_users.add(indiv)
        Competition2User.objects.create(competition=comp, user=indiv)
        # Create a team and add a user.
        team = Team.objects.create(name="Beta Team")
        team_user = User.objects.create_user(
            username="teamuser2", password="testpass",
            first_name="Team2", last_name="User"
        )
        team.users.add(team_user)
        TeamCompetition2Team.objects.create(competition=comp, team=team)
        now = timezone.now()
        # Create answers: individual gets 1 answer; team gets 1 answer.
        Answers.objects.create(user=indiv, lab=lab, datetime=now - timedelta(minutes=40))
        Answers.objects.create(team=team, lab=lab, datetime=now - timedelta(minutes=30))

        url = reverse("interface_api:get_solutions", kwargs={"slug": comp.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        solutions = data["solutions"]

        # Expect 2 solutions: one individual (progress=1) and one team.
        self.assertEqual(len(solutions), 2)
        # Sorted by progress descending: team solution first.
        self.assertEqual(solutions[0]["progress"], 1)
        self.assertEqual(solutions[1]["progress"], 1)
        # Positions must be assigned as 1 and 2.
        self.assertEqual(solutions[0]["pos"], 1)
        self.assertEqual(solutions[1]["pos"], 2)
        self.assertEqual(solutions[0]["team_name"], "")     # user was first
        self.assertEqual(solutions[1]["team_name"], "Beta Team")
        self.assertEqual(data["total_progress"], 2)
