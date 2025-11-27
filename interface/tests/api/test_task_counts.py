import json
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta

from interface.models import (
    Competition, TeamCompetition, Lab, LabTask, Platoon, User,
    Competition2User, TeamCompetition2Team, Team, Kkz, KkzLab
)
from interface.forms import CompetitionForm, TeamCompetitionForm, SimpleKkzForm


class TaskCountsTestCase(TransactionTestCase):
    """
    Тесты для проверки соответствия отображаемого количества заданий
    в таблице решений и реального количества выданных заданий
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.pnet_patch = patch("interface.pnet_session_manager.PNetSessionManager", MagicMock())
        cls.pnet_patch.start()

        cls.flag_patch = patch("interface.models.get_flag_deployment_queue", return_value=MagicMock())
        cls.flag_patch.start()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        cls.pnet_patch.stop()
        cls.flag_patch.stop()

    def setUp(self):
        self.lab = Lab.objects.create(
            name="Test Lab",
            platform="NO",
            lab_type="EXAM",
            learning_years=[1]
        )

        self.tasks = []
        for i in range(5):
            task = LabTask.objects.create(
                lab=self.lab,
                task_id=f"Task_{i + 1}",
                description=f"Test task {i + 1}"
            )
            self.tasks.append(task)

        self.platoon = Platoon.objects.create(
            number=1,
            learning_year=1
        )

        self.users = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"user_{i}",
                password="testpass",
                first_name=f"User_{i}",
                last_name="Test",
                platoon=self.platoon,
                pnet_login=f"pnet_user_{i}",
                pnet_password="pnetpass123"
            )
            self.users.append(user)

    def test_competition_max_tasks_equals_assigned_tasks(self):
        """
        Проверяет, что max_tasks в таблице решений равно количеству
        реально назначенных заданий для каждого пользователя
        """
        competition_data = {
            'slug': 'test-competition-tasks',
            'start': timezone.now(),
            'finish': timezone.now() + timedelta(hours=2),
            'lab': self.lab.pk,
            'platoons': [self.platoon.pk],
            'tasks': [self.tasks[0].pk, self.tasks[1].pk, self.tasks[2].pk],
            'num_tasks': 2
        }

        form = CompetitionForm(data=competition_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        competition = form.save()

        url = reverse("interface_api:get_solutions", kwargs={"slug": competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        solutions = data['solutions']

        for user in self.users:
            user_solution = next((s for s in solutions if s['user_id'] == user.id), None)
            self.assertIsNotNone(user_solution, f"Solution not found for user {user.username}")

            comp2user = Competition2User.objects.get(competition=competition, user=user)
            actual_tasks_count = comp2user.tasks.count()

            self.assertEqual(
                user_solution['max_tasks'],
                actual_tasks_count,
                f"max_tasks ({user_solution['max_tasks']}) != actual tasks count ({actual_tasks_count}) for user {user.username}"
            )

            self.assertEqual(
                user_solution['total_tasks'],
                actual_tasks_count,
                f"total_tasks ({user_solution['total_tasks']}) != actual tasks count ({actual_tasks_count}) for user {user.username}"
            )

    def test_team_competition_max_tasks_equals_assigned_tasks(self):
        """
        Проверяет, что max_tasks в таблице решений для командного соревнования
        равно количеству реально назначенных заданий команде
        """
        comp_lab = Lab.objects.create(
            name="Team Competition Lab",
            platform="NO",
            lab_type="COMPETITION",
            learning_years=[1]
        )

        comp_tasks = []
        for i in range(4):
            task = LabTask.objects.create(
                lab=comp_lab,
                task_id=f"CompTask_{i + 1}",
                description=f"Competition task {i + 1}"
            )
            comp_tasks.append(task)

        team = Team.objects.create(name="Test Team", slug="test-team")
        team.users.set([self.users[0], self.users[1]])

        competition_data = {
            'slug': 'test-team-competition',
            'start': timezone.now(),
            'finish': timezone.now() + timedelta(hours=2),
            'lab': comp_lab.pk,
            'platoons': [],
            'non_platoon_users': [self.users[2].pk],
            'teams': [team.pk],
            'tasks': [t.pk for t in comp_tasks],
            'num_tasks': 4
        }

        form = TeamCompetitionForm(data=competition_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        competition = form.save()

        url = reverse("interface_api:get_solutions", kwargs={"slug": competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        solutions = data['solutions']

        team_comp = TeamCompetition2Team.objects.get(competition=competition, team=team)
        team_tasks_count = team_comp.tasks.count()

        for team_member in team.users.all():
            team_solution = next((s for s in solutions if s['user_id'] == team_member.id), None)
            self.assertIsNotNone(team_solution, f"Solution not found for team member {team_member.username}")

            self.assertEqual(
                team_solution['max_tasks'],
                team_tasks_count,
                f"Team max_tasks ({team_solution['max_tasks']}) != team tasks count ({team_tasks_count})"
            )

            self.assertEqual(
                team_solution['total_tasks'],
                team_tasks_count,
                f"Team total_tasks ({team_solution['total_tasks']}) != team tasks count ({team_tasks_count})"
            )

        comp2user = Competition2User.objects.get(competition=competition, user=self.users[2])
        individual_tasks_count = comp2user.tasks.count()

        individual_solution = next((s for s in solutions if s['user_id'] == self.users[2].id), None)
        self.assertIsNotNone(individual_solution, "Solution not found for individual user")

        self.assertEqual(
            individual_solution['max_tasks'],
            individual_tasks_count,
            f"Individual max_tasks ({individual_solution['max_tasks']}) != individual tasks count ({individual_tasks_count})"
        )

    def test_kkz_max_tasks_sum_equals_all_assigned_tasks(self):
        """
        Проверяет, что сумма max_tasks для всех лаб в ККЗ равна
        общему количеству назначенных заданий пользователю
        """
        lab2 = Lab.objects.create(
            name="Test Lab 2",
            platform="NO",
            lab_type="EXAM",
            learning_years=[1]
        )

        tasks2 = []
        for i in range(3):
            task = LabTask.objects.create(
                lab=lab2,
                task_id=f"Task2_{i + 1}",
                description=f"Test task 2.{i + 1}"
            )
            tasks2.append(task)

        labs_data = [
            {
                'lab_id': self.lab.id,
                'name': self.lab.name,
                'included': True,
                'task_ids': [t.id for t in self.tasks[:3]],
                'num_tasks': 2
            },
            {
                'lab_id': lab2.id,
                'name': lab2.name,
                'included': True,
                'task_ids': [t.id for t in tasks2],
                'num_tasks': 2
            }
        ]

        import json
        form_data = {
            'name': 'Test KKZ',
            'platoon': self.platoon.pk,
            'duration_0': '0',
            'duration_1': '2',
            'duration_2': '0',
            'unified_tasks': False,
            'labs_data': json.dumps(labs_data)
        }

        form = SimpleKkzForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        kkz = form.create_kkz()

        url = reverse("interface_api:get_kkz_solutions", kwargs={"kkz_id": kkz.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        solutions = data['solutions']

        for user in self.users:
            user_solution = next((s for s in solutions if s['user_id'] == user.id), None)
            self.assertIsNotNone(user_solution, f"Solution not found for user {user.username}")

            total_assigned = 0
            competitions = Competition.objects.filter(kkz=kkz)

            for competition in competitions:
                try:
                    comp2user = Competition2User.objects.get(competition=competition, user=user)
                    total_assigned += comp2user.tasks.count()
                except Competition2User.DoesNotExist:
                    pass

            self.assertEqual(
                user_solution['max_tasks'],
                total_assigned,
                f"max_tasks ({user_solution['max_tasks']}) != total assigned tasks ({total_assigned}) for user {user.username}"
            )

    def test_competition_different_task_counts_per_user(self):
        """
        Проверяет корректность отображения max_tasks когда у разных
        пользователей разное количество заданий
        """
        competition = Competition.objects.create(
            slug='test-different-counts',
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2),
            lab=self.lab,
            num_tasks=3
        )

        competition.platoons.add(self.platoon)

        for i, user in enumerate(self.users):
            comp2user = Competition2User.objects.create(
                competition=competition,
                user=user
            )
            tasks_to_assign = self.tasks[:2 + i]
            comp2user.tasks.set(tasks_to_assign)

        url = reverse("interface_api:get_solutions", kwargs={"slug": competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        solutions = data['solutions']

        for i, user in enumerate(self.users):
            user_solution = next((s for s in solutions if s['user_id'] == user.id), None)
            self.assertIsNotNone(user_solution)

            expected_count = 2 + i
            self.assertEqual(
                user_solution['max_tasks'],
                expected_count,
                f"User {user.username} should have {expected_count} tasks, got {user_solution['max_tasks']}"
            )

    def test_kkz_unified_tasks_same_max_tasks(self):
        """
        Проверяет, что при unified_tasks=True все пользователи имеют
        одинаковое количество max_tasks
        """
        max_tasks_limit = 3
        
        labs_data = [
            {
                'lab_id': self.lab.id,
                'name': self.lab.name,
                'included': True,
                'task_ids': [t.id for t in self.tasks], 
                'num_tasks': len(self. tasks),
                'max_tasks_limit': max_tasks_limit 
            }
        ]

        form_data = {
            'name': 'Test Unified KKZ',
            'platoon': self.platoon.pk,
            'duration_0': '0',
            'duration_1': '2',
            'duration_2': '0',
            'unified_tasks': True,
            'labs_data': json.dumps(labs_data)
        }

        form = SimpleKkzForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        kkz = form.create_kkz()

        url = reverse("interface_api:get_kkz_solutions", kwargs={"kkz_id": kkz.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        solutions = data['solutions']

        max_tasks_values = [s['max_tasks'] for s in solutions]

        self.assertTrue(
            all(v == max_tasks_values[0] for v in max_tasks_values),
            f"With unified_tasks=True, all users should have same max_tasks, got: {max_tasks_values}"
        )

        self.assertEqual(
            max_tasks_values[0],
            max_tasks_limit,
            f"Expected 3 tasks per user with unified_tasks, got {max_tasks_values[0]}"
        )

        competition = Competition.objects.get(kkz=kkz)
        first_user_tasks = None
        
        for user in self.users:
            comp2user = Competition2User.objects.get(competition=competition, user=user)
            user_task_ids = set(comp2user. tasks.values_list('id', flat=True))
            
            if first_user_tasks is None:
                first_user_tasks = user_task_ids
            else:
                self.assertEqual(
                    first_user_tasks,
                    user_task_ids,
                    f"User {user. username} has different tasks than first user in unified mode"
                )

    def test_max_total_progress_calculation(self):
        """
        Проверяет корректность расчета max_total_progress
        """
        competition = Competition.objects.create(
            slug='test-max-progress',
            start=timezone.now(),
            finish=timezone.now() + timedelta(hours=2),
            lab=self.lab,
            num_tasks=3,
            participants=len(self.users)
        )

        competition.platoons.add(self.platoon)

        for user in self.users:
            comp2user = Competition2User.objects.create(
                competition=competition,
                user=user
            )
            comp2user.tasks.set(self.tasks[:3])

        url = reverse("interface_api:get_solutions", kwargs={"slug": competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()

        expected_max_progress = len(self.users) * 3
        self.assertEqual(
            data['max_total_progress'],
            expected_max_progress,
            f"max_total_progress should be {expected_max_progress}, got {data['max_total_progress']}"
        )

        self.assertEqual(
            data['total_tasks'],
            3,
            f"total_tasks should be 3, got {data['total_tasks']}"
        )


    @patch("interface.pnet_session_manager.PNetSessionManager.delete_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.logout")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_nodes_and_connectors")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.login")
    def test_simple_kkz_form_with_max_tasks_limit(
            self,
            mock_login,
            mock_create_lab,
            mock_create_nodes,
            mock_logout,
            mock_delete_lab
    ):
        """
        Проверяем что max_tasks_limit ограничивает общее количество заданий
        даже когда preview_assignments не передан (пользователь не открывал превью)
        """
        lab2 = Lab.objects.create(
            name="Test Lab 2",
            platform="NO",
            lab_type="EXAM",
            learning_years=[1]
        )
        
        tasks2 = []
        for i in range(3):
            task = LabTask.objects.create(
                lab=lab2,
                task_id=f"Task2_{i + 1}",
                description=f"Test task 2. {i + 1}"
            )
            tasks2.append(task)

        # Устанавливаем лимит в 2 задания (при том что у нас 6 заданий в 2 лабах)
        max_tasks_limit = 2
        
        labs_data = [
            {
                'lab_id': self.lab.id,
                'name': self.lab.name,
                'included': True,
                'task_ids': [t.id for t in self.tasks],
                'num_tasks': len(self.tasks),
                'max_tasks_limit': max_tasks_limit
            },
            {
                'lab_id': lab2.id,
                'name': lab2.name,
                'included': True,
                'task_ids': [t.id for t in tasks2],
                'num_tasks': len(tasks2),
                'max_tasks_limit': max_tasks_limit
            }
        ]
        
        form_data = {
            'name': 'Test KKZ with limit',
            'platoon': self.platoon.pk,
            'duration_0': '0',
            'duration_1': '2',
            'duration_2': '0',
            'unified_tasks': False,
            'labs_data': json.dumps(labs_data),
            # НЕ передаем preview_assignments - имитируем что пользователь не открывал превью
        }

        form = SimpleKkzForm(data=form_data)
        self.assertTrue(form. is_valid(), f"Form errors: {form.errors}")
        kkz = form.create_kkz()

        # Проверяем что у каждого пользователя не более max_tasks_limit заданий
        for user in self.users:
            total_tasks_for_user = 0
            for competition in Competition.objects.filter(kkz=kkz):
                try:
                    comp2user = Competition2User.objects.get(
                        competition=competition,
                        user=user
                    )
                    total_tasks_for_user += comp2user.tasks.count()
                except Competition2User.DoesNotExist:
                    pass
            
            self.assertLessEqual(
                total_tasks_for_user,
                max_tasks_limit,
                f"User {user.username} has {total_tasks_for_user} tasks, "
                f"but max_tasks_limit is {max_tasks_limit}"
            )
            
            # проверяем что задания вообще назначены (не 0)
            self.assertGreater(
                total_tasks_for_user,
                0,
                f"User {user.username} should have at least 1 task"
            )
