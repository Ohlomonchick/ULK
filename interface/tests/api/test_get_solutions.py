from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import timedelta

from interface.models import (
    Competition, Platoon, User, Lab, LabTask, Answers
)


class GetSolutionsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_no_tasks(self):
        """
        Competition with zero tasks
        1) Create a Competition with zero tasks.
        2) Assign some users to that competition (some in platoons, some in non-platoon).
        3) Create Answers for only some of them.
        4) Check that we get back exactly one solution per user who has at least one Answer.
        5) Check ordering by raw_datetime and pos from 1..N.
        """
        # -- 1. Create Lab and Competition (with no tasks) --
        lab = Lab.objects.create(name="Test Lab No Tasks", platform="PN")
        comp = Competition.objects.create(
            slug="no-tasks-comp",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=lab,
            participants=0  # We'll update it manually or let your logic do so
        )
        # No tasks added => comp.tasks.count() == 0

        # -- 2. Create Platoon, Users, and link them to the Competition --
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

        # -- 3. Create some Answers for a subset of these users --
        # E.g., create answers for 2 platoon users and 1 non-platoon user
        # We'll vary the datetime so we can test ordering
        now = timezone.now()
        Answers.objects.create(
            user=platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=30)  # earliest
        )
        Answers.objects.create(
            user=platoon_users[1],
            lab=lab,
            datetime=now - timedelta(minutes=10)
        )
        Answers.objects.create(
            user=non_platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=5)  # latest among these 3
        )
        # Note: no answers for platoon_users[2] or non_platoon_users[1]

        # Expected users with solutions: 3 total answers => 3 distinct users answered

        # -- 4. Call get_solutions endpoint --
        url = reverse("get_solutions", kwargs={"slug": comp.slug})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        solutions = data["solutions"]

        # Verify correct number of solutions: should be 3
        self.assertEqual(
            len(solutions),
            3,
            f"Expected 3 solutions for 3 users who submitted answers. Got {len(solutions)}."
        )

        # -- 5. Check ordering by raw_datetime and positions from 1..N --
        # The solutions should be sorted ascending by "raw_datetime"
        # We inserted them in order of 30 min ago, 10 min ago, 5 min ago
        # So it should come in that ascending order
        # We'll confirm the position is 1..3
        for i, sol in enumerate(solutions, start=1):
            self.assertEqual(sol["pos"], i, "Positions must be consecutive starting at 1")
        # Additionally, we can do a direct check on the order of raw_datetime
        raw_datetimes = [sol["raw_datetime"] for sol in solutions]
        self.assertTrue(
            all(raw_datetimes[i] <= raw_datetimes[i + 1] for i in range(len(raw_datetimes) - 1)),
            "Solutions must be sorted ascending by raw_datetime."
        )

    def test_with_tasks(self):
        """
        Competition WITH tasks
        1) Create a Competition WITH tasks (>0).
        2) Only users who have the same number of Answers as the number of tasks appear.
        3) Check final solutions list size & ordering by raw_datetime.
        """
        # -- 1. Create Lab, tasks, and Competition --
        lab = Lab.objects.create(name="Test Lab With Tasks", platform="NO")
        task1 = LabTask.objects.create(lab=lab, task_id="Task1")
        task2 = LabTask.objects.create(lab=lab, task_id="Task2")

        comp = Competition.objects.create(
            slug="with-tasks-comp",
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=1),
            lab=lab,
            participants=0
        )
        comp.tasks.set([task1, task2])  # so tasks.count() == 2

        # -- 2. Create some users in platoon, some non-platoon --
        platoon = Platoon.objects.create(number=2)
        comp.platoons.add(platoon)

        # 3 platoon users
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

        # 2 non-platoon
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

        # -- 3. Create Answers so that some users complete all tasks, and some don't --
        # We'll consider tasks_to_complete = 2
        # The code in get_solutions basically increments "score" for each answer, and once a user
        # reaches 2 answers, that user is appended to solutions_data.
        now = timezone.now()

        # Let's have platoon_users[0] do 2 answers
        Answers.objects.create(
            user=platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=30)
        )
        Answers.objects.create(
            user=platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=29)
        )

        # platoon_users[1] has only 1 answer => no final solution
        Answers.objects.create(
            user=platoon_users[1],
            lab=lab,
            datetime=now - timedelta(minutes=20)
        )

        # non_platoon_users[0] has 2 answers => final solution
        Answers.objects.create(
            user=non_platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=10)
        )
        Answers.objects.create(
            user=non_platoon_users[0],
            lab=lab,
            datetime=now - timedelta(minutes=9)
        )

        # no answers for platoon_users[2] or non_platoon_users[1]

        # Users who should appear in final solutions: platoon_users[0], non_platoon_users[0]
        # => total 2 solutions

        # -- 4. Call get_solutions endpoint --
        url = reverse("get_solutions", kwargs={"slug": comp.slug})
        response = self.client.get(url, format="json")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        solutions = data["solutions"]

        # -- Verify only the 2 users with 2 answers appear --
        self.assertEqual(
            len(solutions),
            2,
            f"Expected exactly 2 solutions for 2 users who completed 2 tasks. Got {len(solutions)}."
        )

        # Check ordering by raw_datetime
        # By default, the user with earlier last answer is platoon_users[0] (29 min ago).
        # The other user is non_platoon_users[0] (9 min ago).
        # But note the final "raw_datetime" that gets appended is the last answer read for that user
        # The code processes answers in order by user, but then we do `solutions_data.sort(...)`
        # So we can simply check it sorts by the final answer's datetime:
        # platoon_users[0] final answer datetime is -29 minutes (the second answer).
        # non_platoon_users[0] final answer is -9 minutes. => 1) platoon_users[0], 2) non_platoon_users[0]

        raw_datetimes = [sol["raw_datetime"] for sol in solutions]
        self.assertTrue(
            raw_datetimes[0] <= raw_datetimes[1],
            "Solutions must be sorted ascending by raw_datetime."
        )

        # Check position is 1..2
        for i, sol in enumerate(solutions, start=1):
            self.assertEqual(sol["pos"], i, f"Solution pos should be {i}, got {sol['pos']}")
