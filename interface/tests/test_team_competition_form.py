from django.test import TransactionTestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta
import re

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
        cls.patcher_flag_queue = patch("interface.models.get_flag_deployment_queue")
        
        cls.mock_login = cls.patcher_login.start()
        cls.mock_create_lab = cls.patcher_create_lab.start()
        cls.mock_create_nodes = cls.patcher_create_nodes.start()
        cls.mock_logout = cls.patcher_logout.start()
        cls.mock_delete_lab_user = cls.patcher_delete_lab_user.start()
        cls.mock_change_workspace = cls.patcher_change_workspace.start()
        cls.mock_delete_lab_team = cls.patcher_delete_lab_team.start()
        cls.mock_elastic_client = cls.patcher_elastic_client.start()
        
        # Mock flag deployment queue
        cls.mock_queue = MagicMock()
        cls.mock_flag_queue = cls.patcher_flag_queue.start()
        cls.mock_flag_queue.return_value = cls.mock_queue

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
        cls.patcher_flag_queue.stop()

    def setUp(self):
        self.mock_login.reset_mock()
        self.mock_create_lab.reset_mock()
        self.mock_create_nodes.reset_mock()
        self.mock_logout.reset_mock()
        self.mock_delete_lab_user.reset_mock()
        self.mock_change_workspace.reset_mock()
        self.mock_delete_lab_team.reset_mock()
        self.mock_elastic_client.reset_mock()
        self.mock_queue.reset_mock()
        
        # Create NodesData with USB drive options for testing
        self.nodes_data = [
            {
                "cpu": 2,
                "ram": 4096,
                "top": 434,
                "icon": "linux-1.png",
                "left": 356,
                "name": "Linux",
                "size": "",
                "type": "qemu",
                "uuid": "",
                "count": "1",
                "delay": 0,
                "image": "linux-Astra_snap_mrd",
                "config": 0,
                "console": "vnc",
                "postfix": 0,
                "cpulimit": 1,
                "ethernet": 1,
                "firstmac": "",
                "map_port": "",
                "password": "",
                "qemu_nic": "virtio-net-pci",
                "shutdown": 1,
                "template": "linux",
                "username": "",
                "first_nic": "",
                "qemu_arch": "x86_64",
                "console_2nd": "",
                "description": "Linux",
                "map_port_2nd": "",
                "qemu_options": "-machine type=pc,accel=kvm -vga virtio -usbdevice tablet -boot order=cd -cpu host -device usb-ehci -device usb-storage,drive=usbdisk -drive id=usbdisk,file=/usr/share/qemu/usb_flash1.img,if=none",
                "qemu_version": "4.1.0",
                "config_script": "",
                "script_timeout": 1200
            },
            {
                "cpu": 1,
                "ram": 256,
                "top": 478,
                "icon": "Router.png",
                "left": 540,
                "name": "Mikrotik",
                "size": "",
                "type": "qemu",
                "uuid": "",
                "count": "1",
                "delay": 0,
                "image": "mikrotik-mikrotik_L3",
                "config": 0,
                "console": "telnet",
                "postfix": 0,
                "cpulimit": 1,
                "ethernet": 4,
                "firstmac": "",
                "map_port": "",
                "password": "",
                "qemu_nic": "e1000",
                "template": "mikrotik",
                "username": "",
                "first_nic": "",
                "qemu_arch": "x86_64",
                "console_2nd": "",
                "description": "MikroTik RouterOS",
                "map_port_2nd": "",
                "qemu_options": "-machine type=pc,accel=kvm -serial mon:stdio -nographic -no-user-config -nodefaults -display none -vga std -rtc base=utc -drive id=usb_drive,file=flashdrive.img",
                "qemu_version": "2.12.0",
                "config_script": "config_mikrotik.py",
                "script_timeout": 1200
            }
        ]
        
        self.lab = Lab.objects.create(
            name="PN Lab Competition",
            platform="PN",
            lab_type="COMPETITION",
            NodesData=self.nodes_data,
            ConnectorsData=[],
            Connectors2CloudData=[],
            NetworksData=[]
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
                password="testpass",
                pnet_login=f"pnet_team1_user_{i}",
                pnet_password="pnetpass123"
            )
            team1_members.append(user)
        self.team1.users.set(team1_members)

        team2_members = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"team2_user_{i}",
                first_name=f"Team2_{i}",
                last_name="User",
                password="testpass",
                pnet_login=f"pnet_team2_user_{i}",
                pnet_password="pnetpass123"
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
                password="testpass",
                pnet_login=f"pnet_team3_user_{i}",
                pnet_password="pnetpass123"
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

    def test_flag_generation_on_team_task_assignment(self):
        """
        Проверяет, что при назначении задач командам:
        1) Генерируются флаги и сохраняются в TeamCompetition2Team.generated_flags
        2) Создается задача развертывания флагов и отправляется в очередь
        """
        # Создаем лабораторию с нодами для развертывания флагов
        from interface.models import LabNode
        LabNode.objects.create(
            lab=self.lab,
            node_name="test_node",
            login="admin",
            password="admin123"
        )
        
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        competition = form.save()
        
        # Проверяем, что для каждого TeamCompetition2Team сгенерированы флаги
        for team_comp in TeamCompetition2Team.objects.filter(competition=competition):
            # Проверяем, что задачи назначены
            self.assertTrue(
                team_comp.tasks.exists(),
                f"Tasks should be assigned to TeamCompetition2Team for team {team_comp.team.name}"
            )
            
            # Проверяем, что флаги сгенерированы
            self.assertIsNotNone(
                team_comp.generated_flags,
                f"Generated flags should be set for team {team_comp.team.name}"
            )
            
            # Проверяем формат флагов (должен быть список или словарь)
            self.assertIsInstance(
                team_comp.generated_flags,
                (list, dict),
                f"Generated flags should be list or dict for team {team_comp.team.name}"
            )
            
            # Если это список, проверяем структуру
            if isinstance(team_comp.generated_flags, list):
                for flag_item in team_comp.generated_flags:
                    self.assertIn('task_id', flag_item, "Flag item should have task_id")
                    self.assertIn('flag', flag_item, "Flag item should have flag")
                    self.assertTrue(
                        flag_item['flag'].startswith('FLAG_'),
                        f"Flag should start with 'FLAG_': {flag_item['flag']}"
                    )
            
            # Проверяем, что количество флагов соответствует количеству задач
            assigned_tasks = team_comp.tasks.all()
            if isinstance(team_comp.generated_flags, list):
                self.assertEqual(
                    len(team_comp.generated_flags),
                    assigned_tasks.count(),
                    f"Number of flags should match number of tasks for team {team_comp.team.name}"
                )
        
        # Проверяем, что очередь развертывания флагов была вызвана
        # (для каждого TeamCompetition2Team с задачами должна быть создана задача)
        team_comps_with_tasks = [
            tc for tc in TeamCompetition2Team.objects.filter(competition=competition)
            if tc.tasks.exists() and tc.team.users.exists() and tc.team.users.first().pnet_login and tc.team.users.first().pnet_password
        ]
        
        # Проверяем, что submit_task был вызван (если есть ноды в лаборатории)
        if self.lab.nodes.exists() and team_comps_with_tasks:
            self.assertGreaterEqual(
                self.mock_queue.submit_task.call_count,
                1,
                f"Flag deployment task should be submitted for {len(team_comps_with_tasks)} TeamCompetition2Team records with tasks and pnet credentials"
            )
            
            # Проверяем, что каждая задача была отправлена с правильными параметрами
            submitted_tasks = self.mock_queue.submit_task.call_args_list
            self.assertEqual(
                len(submitted_tasks),
                len(team_comps_with_tasks),
                f"Expected {len(team_comps_with_tasks)} flag deployment tasks to be submitted"
            )

    def test_usb_device_ids_shared_between_users_and_teams(self):
        """
        Проверяет, что в TeamCompetitionForm пользователи и команды используют один общий набор USB IDs
        без пересечений.
        """
        from dynamic_config.models import ConfigEntry
        
        ConfigEntry.objects.update_or_create(
            key='USB_DEVICES_COUNT',
            defaults={'value': '20'}
        )
        
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        competition = form.save()
        
        # Собираем все USB IDs от пользователей
        comp2users = Competition2User.objects.filter(competition=competition)
        user_usb_ids = []
        for comp2user in comp2users:
            usb_ids = comp2user.deploy_meta.get('usb_device_ids', [])
            user_usb_ids.extend(usb_ids)
        
        # Собираем все USB IDs от команд
        team_comps = TeamCompetition2Team.objects.filter(competition=competition)
        team_usb_ids = []
        for team_comp in team_comps:
            usb_ids = team_comp.deploy_meta.get('usb_device_ids', [])
            team_usb_ids.extend(usb_ids)
        
        # Проверяем, что нет пересечений между пользователями и командами
        all_ids = user_usb_ids + team_usb_ids
        unique_ids = set(all_ids)
        self.assertEqual(len(all_ids), len(unique_ids),
                        "USB IDs should not overlap between users and teams")
        
        # Проверяем, что все ID уникальны
        self.assertGreater(len(user_usb_ids), 0, "Users should have USB IDs")
        self.assertGreater(len(team_usb_ids), 0, "Teams should have USB IDs")

    def test_usb_device_ids_passed_to_create_nodes_for_teams(self):
        """
        Проверяет, что USB device IDs правильно передаются в create_lab_nodes_and_connectors для команд.
        """
        from dynamic_config.models import ConfigEntry
        
        ConfigEntry.objects.update_or_create(
            key='USB_DEVICES_COUNT',
            defaults={'value': '20'}
        )
        
        # Сохраняем аргументы вызовов create_lab_nodes_and_connectors
        call_args_list = []
        
        def capture_call_args(*args, **kwargs):
            call_args_list.append((args, kwargs))
            return self.mock_create_nodes.return_value
        
        self.mock_create_nodes.side_effect = capture_call_args
        
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        
        competition = form.save()
        
        # Проверяем вызовы для команд
        team_comps = TeamCompetition2Team.objects.filter(competition=competition)
        
        # Находим вызовы для команд (по username=team_slug)
        team_calls = []
        for team_comp in team_comps:
            for args, kwargs in call_args_list:
                # create_lab_nodes_and_connectors вызывается с lab, lab_name, username, usb_device_ids=...
                # args: (lab, lab_name, username)
                # kwargs: {usb_device_ids=...}
                if len(args) >= 3 and args[2] == team_comp.team.slug:
                    team_calls.append((team_comp, kwargs))
                    break
        
        # Проверяем, что USB IDs переданы правильно для каждой команды
        self.assertGreater(len(team_calls), 0, "Should have calls for teams")
        for team_comp, kwargs in team_calls:
            expected_usb_ids = team_comp.deploy_meta.get('usb_device_ids', [])
            actual_usb_ids = kwargs.get('usb_device_ids', [])
            self.assertEqual(actual_usb_ids, expected_usb_ids,
                           f"USB IDs for team {team_comp.team.name} should match deploy_meta")

    def test_usb_device_ids_replacement_in_qemu_options_for_teams(self):
        """
        Проверяет, что USB device IDs правильно заменяются в qemu_options для команд.
        """
        from interface.utils import replace_usb_device_ids_in_nodes
        from dynamic_config.models import ConfigEntry
        
        ConfigEntry.objects.update_or_create(
            key='USB_DEVICES_COUNT',
            defaults={'value': '20'}
        )
        
        form = TeamCompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        
        competition = form.save()
        
        # Получаем первую команду для проверки
        team_comp = TeamCompetition2Team.objects.filter(competition=competition).first()
        self.assertIsNotNone(team_comp, "Should have at least one TeamCompetition2Team")
        
        usb_ids = team_comp.deploy_meta.get('usb_device_ids', [])
        self.assertGreater(len(usb_ids), 0, "Should have USB IDs")
        
        # Проверяем замену в qemu_options
        modified_nodes = replace_usb_device_ids_in_nodes(self.nodes_data, usb_ids)
        
        # Проверяем, что опции были заменены
        usb_id_index = 0
        for node in modified_nodes:
            qemu_options = node.get('qemu_options', '')
            # Ищем паттерн file=*.img в опциях drive
            if re.search(r'-{1,2}drive\s+[^,]*id=[^,]+,\s*file=[^,\s]+\.img', qemu_options):
                # Если есть опция, она должна быть заменена на /usr/share/qemu/usb_flash{i}.img
                expected_path = f'/usr/share/qemu/usb_flash{usb_ids[usb_id_index]}.img'
                self.assertIn(expected_path, qemu_options,
                             f"USB ID {usb_ids[usb_id_index]} should be in qemu_options as {expected_path}")
                usb_id_index += 1
                if usb_id_index >= len(usb_ids):
                    break

