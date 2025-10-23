from django.test import TransactionTestCase
from django.utils import timezone
from unittest.mock import patch
from datetime import timedelta

from interface.forms import TeamCompetitionForm
from interface.models import (
    TeamCompetition, Team, Platoon, User, Lab, LabLevel, LabTask, 
    TeamCompetition2Team, Competition2User
)


class TeamCompetitionFormTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.patcher_login = patch("interface.pnet_session_manager.PNetSessionManager.login")
        cls.patcher_create_lab = patch("interface.pnet_session_manager.PNetSessionManager.create_lab_for_user")
        cls.patcher_create_nodes = patch("interface.pnet_session_manager.PNetSessionManager.create_lab_nodes_and_connectors")
        cls.patcher_logout = patch("interface.pnet_session_manager.PNetSessionManager.logout")
        cls.patcher_delete_lab_user = patch("interface.pnet_session_manager.PNetSessionManager.delete_lab_for_user")
        cls.patcher_change_workspace = patch("interface.pnet_session_manager.PNetSessionManager.change_user_workspace")
        cls.patcher_delete_lab_team = patch("interface.pnet_session_manager.PNetSessionManager.delete_lab_for_team")
        cls.patcher_elastic_client = patch("interface.elastic_utils.get_elastic_client", return_value=None)
        
        cls.mock_login = cls.patcher_login.start()
        cls.mock_create_lab = cls.patcher_create_lab.start()
        cls.mock_create_nodes = cls.patcher_create_nodes.start()
        cls.mock_logout = cls.patcher_logout.start()
        cls.mock_delete_lab_user = cls.patcher_delete_lab_user.start()
        cls.mock_change_workspace = cls.patcher_change_workspace.start()
        cls.mock_delete_lab_team = cls.patcher_delete_lab_team.start()
        cls.mock_elastic_client = cls.patcher_elastic_client.start()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        
        cls.patcher_login.stop()
        cls.patcher_create_lab.stop()
        cls.patcher_create_nodes.stop()
        cls.patcher_logout.stop()
        cls.patcher_delete_lab_user.stop()
        cls.patcher_change_workspace.stop()
        cls.patcher_delete_lab_team.stop()
        cls.patcher_elastic_client.stop()

    def setUp(self):
        self.mock_login.reset_mock()
        self.mock_create_lab.reset_mock()
        self.mock_create_nodes.reset_mock()
        self.mock_logout.reset_mock()
        self.mock_delete_lab_user.reset_mock()
        self.mock_change_workspace.reset_mock()
        self.mock_delete_lab_team.reset_mock()
        self.mock_elastic_client.reset_mock()
        self.lab = Lab.objects.create(
            name="PN Lab Competition",
            platform="PN",
            lab_type="COMPETITION"
        )

        self.level = LabLevel.objects.create(
            lab=self.lab,
            level_number=1,
            description=""
        )

        self.task1 = LabTask.objects.create(lab=self.lab, task_id="Task 1")
        self.task2 = LabTask.objects.create(lab=self.lab, task_id="Task 2")
        self.task3 = LabTask.objects.create(lab=self.lab, task_id="Task 3")

        self.platoon = Platoon.objects.create(number=1)

        self.users_in_platoon = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"user_platoon_{i}",
                first_name=f"Platoon_{i}",
                last_name="User",
                password="testpass",
                platoon=self.platoon
            )
            self.users_in_platoon.append(user)

        self.non_platoon_users = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"user_nop_{i}",
                first_name=f"NoPlatoon_{i}",
                last_name="User",
                password="testpass",
                platoon=None
            )
            self.non_platoon_users.append(user)

        self.team1 = Team.objects.create(name="Team Alpha", slug="team-alpha")
        self.team2 = Team.objects.create(name="Team Beta", slug="team-beta")

        team1_members = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"team1_user_{i}",
                first_name=f"Team1_{i}",
                last_name="User",
                password="testpass"
            )
            team1_members.append(user)
        self.team1.users.set(team1_members)

        team2_members = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"team2_user_{i}",
                first_name=f"Team2_{i}",
                last_name="User",
                password="testpass"
            )
            team2_members.append(user)
        self.team2.users.set(team2_members)

        self.start_time = timezone.now() + timedelta(hours=1)
        self.finish_time = timezone.now() + timedelta(hours=2)

        self.form_data = {
            "slug": "test-team-competition-form",
            "start": self.start_time,
            "finish": self.finish_time,
            "lab": self.lab.pk,
            "level": self.level.pk,
            "platoons": [self.platoon.pk],
            "non_platoon_users": [u.pk for u in self.non_platoon_users],
            "teams": [self.team1.pk, self.team2.pk],
            "tasks": [self.task1.pk, self.task2.pk, self.task3.pk]
        }

    def test_team_competition_creation_with_teams(self):
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        competition = form.save()

        self.assertIsInstance(competition, TeamCompetition)
        self.assertTrue(TeamCompetition.objects.filter(pk=competition.pk).exists())

        team_competition_records = TeamCompetition2Team.objects.filter(competition=competition)
        self.assertEqual(team_competition_records.count(), 2)

        team1_record = team_competition_records.get(team=self.team1)
        team2_record = team_competition_records.get(team=self.team2)

        self.assertEqual(team1_record.tasks.count(), 3)
        self.assertEqual(team2_record.tasks.count(), 3)

        task_ids = set([self.task1.pk, self.task2.pk, self.task3.pk])
        self.assertEqual(set(team1_record.tasks.values_list('pk', flat=True)), task_ids)
        self.assertEqual(set(team2_record.tasks.values_list('pk', flat=True)), task_ids)

    def test_pnet_calls_for_teams(self):
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        
        competition = form.save()

        expected_calls = (
            len(self.users_in_platoon) +
            len(self.non_platoon_users) +
            2  # 2 teams
        )

        self.assertEqual(
            self.mock_create_lab.call_count,
            expected_calls,
            f"Expected {expected_calls} create_lab calls (users + teams)"
        )
        self.assertEqual(
            self.mock_create_nodes.call_count,
            expected_calls,
            f"Expected {expected_calls} create_nodes calls (users + teams)"
        )

    def test_users_excluded_from_teams(self):
        team_user = self.team1.users.first()
        self.users_in_platoon[0].delete()
        self.users_in_platoon[0] = team_user
        team_user.platoon = self.platoon
        team_user.save()

        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        
        competition = form.save()

        individual_users = Competition2User.objects.filter(competition=competition)
        individual_user_ids = set(individual_users.values_list('user_id', flat=True))

        self.assertNotIn(
            team_user.id,
            individual_user_ids,
            "Team member should not be in individual Competition2User records"
        )

        remaining_platoon_users = [u for u in self.users_in_platoon if u.id != team_user.id]
        for user in remaining_platoon_users + self.non_platoon_users:
            self.assertIn(
                user.id,
                individual_user_ids,
                f"User {user.username} should be in Competition2User"
            )

    def test_team_competition_update(self):
        form_initial = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form_initial.is_valid())
        competition = form_initial.save()

        initial_team_records = TeamCompetition2Team.objects.filter(competition=competition)
        self.assertEqual(initial_team_records.count(), 2)

        team3 = Team.objects.create(name="Team Gamma", slug="team-gamma")
        team3_members = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"team3_user_{i}",
                password="testpass"
            )
            team3_members.append(user)
        team3.users.set(team3_members)

        form_data_update = {
            "slug": competition.slug,
            "start": competition.start,
            "finish": competition.finish,
            "lab": competition.lab.pk,
            "level": competition.level.pk,
            "platoons": [self.platoon.pk],
            "non_platoon_users": [u.pk for u in self.non_platoon_users],
            "teams": [self.team1.pk, team3.pk],
            "tasks": [self.task1.pk, self.task2.pk, self.task3.pk],
        }

        form_update = TeamCompetitionForm(data=form_data_update, instance=competition)
        self.assertTrue(form_update.is_valid())
        updated_competition = form_update.save()

        updated_team_records = TeamCompetition2Team.objects.filter(competition=updated_competition)
        updated_team_ids = set(updated_team_records.values_list('team_id', flat=True))

        self.assertIn(self.team1.id, updated_team_ids)
        self.assertIn(team3.id, updated_team_ids)
        self.assertNotIn(self.team2.id, updated_team_ids)

    def test_team_competition_deletion(self):
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        competition = form.save()

        team_competition_pks = list(
            TeamCompetition2Team.objects.filter(competition=competition).values_list('pk', flat=True)
        )
        individual_user_pks = list(
            Competition2User.objects.filter(competition=competition).values_list('pk', flat=True)
        )

        competition.delete()

        for pk in team_competition_pks:
            self.assertFalse(
                TeamCompetition2Team.objects.filter(pk=pk).exists(),
                f"TeamCompetition2Team with pk={pk} should be deleted"
            )

        for pk in individual_user_pks:
            self.assertFalse(
                Competition2User.objects.filter(pk=pk).exists(),
                f"Competition2User with pk={pk} should be deleted"
            )

        expected_user_delete_calls = len(self.users_in_platoon) + len(self.non_platoon_users)
        expected_team_delete_calls = 2

        self.assertEqual(
            self.mock_delete_lab_user.call_count,
            expected_user_delete_calls,
            f"Expected {expected_user_delete_calls} delete_lab_for_user calls"
        )
        
        self.assertEqual(
            self.mock_delete_lab_team.call_count,
            expected_team_delete_calls,
            f"Expected {expected_team_delete_calls} delete_lab_for_team calls"
        )

    def test_team_gets_all_tasks_when_specified(self):
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        competition = form.save()

        for team in [self.team1, self.team2]:
            team_record = TeamCompetition2Team.objects.get(
                competition=competition,
                team=team
            )
            assigned_task_ids = set(team_record.tasks.values_list('pk', flat=True))
            expected_task_ids = set([self.task1.pk, self.task2.pk, self.task3.pk])
            
            self.assertEqual(
                assigned_task_ids,
                expected_task_ids,
                f"Team {team.name} should have all specified tasks"
            )

    def test_team_gets_lab_tasks_when_no_tasks_specified(self):
        form_data_no_tasks = self.form_data.copy()
        form_data_no_tasks.pop('tasks')

        form = TeamCompetitionForm(data=form_data_no_tasks)
        self.assertTrue(form.is_valid())
        competition = form.save()

        for team in [self.team1, self.team2]:
            team_record = TeamCompetition2Team.objects.get(
                competition=competition,
                team=team
            )
            assigned_task_ids = set(team_record.tasks.values_list('pk', flat=True))
            lab_task_ids = set(self.lab.options.values_list('pk', flat=True))
            
            self.assertEqual(
                assigned_task_ids,
                lab_task_ids,
                f"Team {team.name} should have all lab tasks when none specified"
            )

