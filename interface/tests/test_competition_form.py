from django.test import TransactionTestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta
import re

from interface.forms import CompetitionForm
from interface.models import (
    Competition, Platoon, User, Lab, LabLevel, LabTask, Competition2User
)


class CompetitionFormTest(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        cls.patcher_login = patch("interface.pnet_session_manager.PNetSessionManager.login")
        cls.patcher_create_lab = patch("interface.pnet_session_manager.PNetSessionManager.create_lab_for_user")
        cls.patcher_create_nodes = patch("interface.pnet_session_manager.PNetSessionManager.create_lab_nodes_and_connectors")
        cls.patcher_logout = patch("interface.pnet_session_manager.PNetSessionManager.logout")
        cls.patcher_delete_lab = patch("interface.pnet_session_manager.PNetSessionManager.delete_lab_for_user")
        cls.patcher_elastic_client = patch("interface.elastic_utils.get_elastic_client", return_value=None)
        cls.patcher_flag_queue = patch("interface.models.get_flag_deployment_queue")
        
        cls.mock_login = cls.patcher_login.start()
        cls.mock_create_lab = cls.patcher_create_lab.start()
        cls.mock_create_nodes = cls.patcher_create_nodes.start()
        cls.mock_logout = cls.patcher_logout.start()
        cls.mock_delete_lab = cls.patcher_delete_lab.start()
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
        cls.patcher_delete_lab.stop()
        cls.patcher_elastic_client.stop()
        cls.patcher_flag_queue.stop()

    def setUp(self):
        self.mock_login.reset_mock()
        self.mock_create_lab.reset_mock()
        self.mock_create_nodes.reset_mock()
        self.mock_logout.reset_mock()
        self.mock_delete_lab.reset_mock()
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
        
        # Create a Lab that uses "PN" platform to trigger external calls
        self.lab = Lab.objects.create(
            name="PN Lab",
            platform="PN",  # So it attempts to call pf_login/create_lab on save
            NodesData=self.nodes_data,
            ConnectorsData=[],
            Connectors2CloudData=[],
            NetworksData=[]
        )

        # Create a LabLevel
        self.level = LabLevel.objects.create(
            lab=self.lab,
            level_number=1,
            description=""
        )

        # Create some tasks
        self.task1 = LabTask.objects.create(lab=self.lab, task_id="Task 1")
        self.task2 = LabTask.objects.create(lab=self.lab, task_id="Task 2")

        # Create a Platoon
        self.platoon = Platoon.objects.create(
            number=1
        )

        # Create some users in the platoon
        self.users_in_platoon = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"user_platoon_{i}",
                first_name=f"Platoon_{i}",
                last_name="User",
                password="testpass",
                platoon=self.platoon,
                pnet_login=f"pnet_user_platoon_{i}",
                pnet_password="pnetpass123"
            )
            self.users_in_platoon.append(user)

        # Create some users NOT in the platoon
        self.non_platoon_users = []
        for i in range(2):
            user = User.objects.create_user(
                username=f"user_nop_{i}",
                first_name=f"NoPlatoon_{i}",
                last_name="User",
                password="testpass",
                platoon=None,
                pnet_login=f"pnet_user_nop_{i}",
                pnet_password="pnetpass123"
            )
            self.non_platoon_users.append(user)

        # Start/finish times in the future so validation passes
        self.start_time = timezone.now() + timedelta(hours=1)
        self.finish_time = timezone.now() + timedelta(hours=2)

        # Prepare form data
        self.form_data = {
            "slug": "test-competition-form",
            "start": self.start_time,
            "finish": self.finish_time,
            "lab": self.lab.pk,  # Must reference primary key
            "level": self.level.pk,  # Same for foreign key fields
            "platoons": [self.platoon.pk],  # ManyToMany => list of IDs
            "non_platoon_users": [u.pk for u in self.non_platoon_users],
            "tasks": [self.task1.pk, self.task2.pk]
        }

    def test_competition_form_creation_and_deletion(self):
        """
        1) Submit data through the CompetitionForm to create a Competition.
        2) Confirm IssuedLabs are created for platoon users and non-platoon users.
        3) Delete the Competition, verify IssuedLabs are removed.
        """
        # Note: The CompetitionForm uses ModelForm fields `__all__`, 
        # so make sure to fill in any required fields.

        # Instantiate the form with data
        form = CompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        competition = form.save()

        self.mock_login.assert_called()
        self.mock_create_lab.assert_called()
        self.mock_create_nodes.assert_called()

        # Verify that the competition is actually created in DB
        self.assertIsInstance(competition, Competition)
        self.assertTrue(Competition.objects.filter(pk=competition.pk).exists())

        # --- Verify IssuedLabs creation ---
        # Should be created for each platoon user + each non-platoon user
        for user in self.non_platoon_users + self.users_in_platoon:
            user_issued_in_competition = competition.competition_users.filter(user=user)
            self.assertTrue(
                user_issued_in_competition.exists(),
                f"Competition2User not found for user {user.username} in this competition"
            )

        self.assertEqual(
            self.mock_create_lab.call_count,
            len(self.users_in_platoon) + len(self.non_platoon_users),
            "Expected `create_lab` to be called once for each user."
        )
        self.assertEqual(
            self.mock_create_nodes.call_count,
            len(self.users_in_platoon) + len(self.non_platoon_users),
            "Expected `create_all_lab_nodes_and_connectors` to be called once for each user."
        )

        # Store all pks of IssuedLabs that belong to this competition
        competition2users_pks = list(competition.competition_users.values_list('pk', flat=True))

        # Now delete the competition
        competition.delete()

        self.assertEqual(
            self.mock_delete_lab.call_count,
            len(self.non_platoon_users) + len(self.users_in_platoon),
            "Expected `delete_lab_with_session_destroy` to be called once for each user."
        )

        # Verify they are truly removed from the database
        for pk in competition2users_pks:
            self.assertFalse(
                Competition2User.objects.filter(pk=pk).exists(),
                f"IssuedLabs with pk={pk} should have been deleted after competition deletion."
            )

    def test_flag_generation_on_task_assignment(self):
        """
        Проверяет, что при назначении задач:
        1) Генерируются флаги и сохраняются в Competition2User.generated_flags
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
        
        form = CompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        competition = form.save()
        
        # Проверяем, что для каждого Competition2User сгенерированы флаги
        for comp2user in competition.competition_users.all():
            # Проверяем, что задачи назначены
            self.assertTrue(
                comp2user.tasks.exists(),
                f"Tasks should be assigned to Competition2User for user {comp2user.user.username}"
            )
            
            # Проверяем, что флаги сгенерированы
            self.assertIsNotNone(
                comp2user.generated_flags,
                f"Generated flags should be set for user {comp2user.user.username}"
            )
            
            # Проверяем формат флагов (должен быть список или словарь)
            self.assertIsInstance(
                comp2user.generated_flags,
                (list, dict),
                f"Generated flags should be list or dict for user {comp2user.user.username}"
            )
            
            # Если это список, проверяем структуру
            if isinstance(comp2user.generated_flags, list):
                for flag_item in comp2user.generated_flags:
                    self.assertIn('task_id', flag_item, "Flag item should have task_id")
                    self.assertIn('flag', flag_item, "Flag item should have flag")
                    self.assertTrue(
                        flag_item['flag'].startswith('FLAG_'),
                        f"Flag should start with 'FLAG_': {flag_item['flag']}"
                    )
            
            # Проверяем, что количество флагов соответствует количеству задач
            assigned_tasks = comp2user.tasks.all()
            if isinstance(comp2user.generated_flags, list):
                self.assertEqual(
                    len(comp2user.generated_flags),
                    assigned_tasks.count(),
                    f"Number of flags should match number of tasks for user {comp2user.user.username}"
                )
        
        # Проверяем, что очередь развертывания флагов была вызвана
        # (для каждого Competition2User с задачами должна быть создана задача)
        comp2users_with_tasks = [
            comp2user for comp2user in competition.competition_users.all()
            if comp2user.tasks.exists() and comp2user.user.pnet_login and comp2user.user.pnet_password
        ]
        
        # Проверяем, что submit_task был вызван (если есть ноды в лаборатории)
        if self.lab.nodes.exists() and comp2users_with_tasks:
            self.assertGreaterEqual(
                self.mock_queue.submit_task.call_count,
                1,
                f"Flag deployment task should be submitted for {len(comp2users_with_tasks)} Competition2User records with tasks and pnet credentials"
            )
            
            # Проверяем, что каждая задача была отправлена с правильными параметрами
            submitted_tasks = self.mock_queue.submit_task.call_args_list
            self.assertEqual(
                len(submitted_tasks),
                len(comp2users_with_tasks),
                f"Expected {len(comp2users_with_tasks)} flag deployment tasks to be submitted"
            )

    def test_competition_form_update(self):
        """
        1) Create a Competition with an initial set of users & platoons (form create).
        2) Update the same Competition (form edit) to remove some users and add others
           (both in non-platoon and in platoons).
        3) Verify the 'Competition2User' table is updated accordingly.
        """

        form_initial = CompetitionForm(data=self.form_data)
        self.assertTrue(form_initial.is_valid(), f"Initial form errors: {form_initial.errors}")
        competition = form_initial.save()

        initial_comp2users = competition.competition_users.all()
        # Check which user IDs are present
        initial_user_ids = set(initial_comp2users.values_list("user_id", flat=True))
        self.assertTrue(
            all(u.id in initial_user_ids for u in self.users_in_platoon + self.non_platoon_users),
            "All platoon + non_platoon users should be in competition_users initially."
        )

        # -------------------------------------------------------------
        # Step 2: Update the competition
        #   - Remove some users from non_platoon_users
        #   - Add a new user to non_platoon_users
        #   - Possibly add a new user to the same platoon or a new platoon
        # -------------------------------------------------------------
        # Let's remove user_nop_0 from non-platoon, keep user_nop_1, and add a new user_nop_2
        user_nop_2 = User.objects.create_user(
            username="user_nop_2",
            password="testpass",
            first_name="NoPlatoon_2",
            last_name="User",
            pnet_login="pnet_user_nop_2",
            pnet_password="pnetpass123"
        )

        # Also let's remove user_platoon_0 from the competition by changing that user's platoon
        # or removing that platoon from the competition.
        # We could also just remove the entire platoon from the form, but let's do something simpler:
        other_platoon = Platoon.objects.create(number=2)
        self.users_in_platoon[0].platoon = other_platoon
        self.users_in_platoon[0].save()

        # We'll *keep* user_platoon_1 and user_platoon_2 in platoon #1, so they remain in the competition

        # Compose the new form data to reflect the updated competition
        form_data_update = {
            "slug": "test-update-competition",
            "start": competition.start,
            "finish": competition.finish,
            "lab": competition.lab.pk,
            "level": competition.level.pk,
            "platoons": [self.platoon.pk],
            # Non platoon now has user_nop_1 and newly created user_nop_2
            "non_platoon_users": [self.non_platoon_users[1].pk, user_nop_2.pk],
            "tasks": [self.task1.pk, self.task2.pk],
        }

        # Edit an existing instance
        form_update = CompetitionForm(data=form_data_update, instance=competition)
        self.assertTrue(form_update.is_valid(), f"Update form errors: {form_update.errors}")
        updated_competition = form_update.save()  # same DB object, but updated

        # -------------------------------------------------------------
        # Step 3: Check competition_users after update
        # -------------------------------------------------------------
        updated_comp2users = updated_competition.competition_users.all()
        updated_count = updated_comp2users.count()

        # Who should remain?
        # - user_platoon_1, user_platoon_2 (still in the original platoon #1)
        # - user_nop_1, user_nop_2 (explicitly in non_platoon_users in updated form)
        # That's 4 total.
        self.assertEqual(
            updated_count,
            4,
            f"Expected 4 Competition2User records after update, got {updated_count}"
        )

        # The removed user is user_platoon_0 (moved to platoon #2, not in competition)
        # and user_nop_0 (not in updated non-platoon selection).
        remaining_user_ids = set(updated_comp2users.values_list("user_id", flat=True))

        # Check we no longer have user_platoon_0 in competition_users
        self.assertNotIn(
            self.users_in_platoon[0].id,
            remaining_user_ids,
            "user_platoon_0 should have been removed after update"
        )
        # Check user_nop_0 is removed
        self.assertNotIn(
            self.non_platoon_users[0].id,
            remaining_user_ids,
            "user_nop_0 should have been removed after update"
        )
        # Check user_nop_2 was added
        self.assertIn(
            user_nop_2.id,
            remaining_user_ids,
            "user_nop_2 should have been added after update"
        )
        # Check user_platoon_1, user_platoon_2 remain
        self.assertIn(
            self.users_in_platoon[1].id,
            remaining_user_ids,
            "user_platoon_1 should still be in competition_users"
        )
        self.assertIn(
            self.users_in_platoon[2].id,
            remaining_user_ids,
            "user_platoon_2 should still be in competition_users"
        )

    def test_usb_device_ids_generation_and_storage(self):
        """
        Проверяет, что USB device IDs генерируются и сохраняются в deploy_meta для каждого Competition2User.
        """
        from dynamic_config.models import ConfigEntry
        
        # Устанавливаем количество USB устройств
        ConfigEntry.objects.update_or_create(
            key='USB_DEVICES_COUNT',
            defaults={'value': '20'}
        )
        
        form = CompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        competition = form.save()
        
        # Проверяем, что для каждого Competition2User сохранены USB IDs в deploy_meta
        comp2users = Competition2User.objects.filter(competition=competition)
        self.assertGreater(comp2users.count(), 0, "Should have at least one Competition2User")
        
        all_usb_ids = []
        for comp2user in comp2users:
            self.assertIsNotNone(comp2user.deploy_meta, "deploy_meta should be set")
            self.assertIn('usb_device_ids', comp2user.deploy_meta, "usb_device_ids should be in deploy_meta")
            usb_ids = comp2user.deploy_meta['usb_device_ids']
            self.assertIsInstance(usb_ids, list, "usb_device_ids should be a list")
            self.assertGreater(len(usb_ids), 0, "usb_device_ids should not be empty")
            all_usb_ids.extend(usb_ids)
        
        # Проверяем, что все USB IDs уникальны (нет пересечений)
        self.assertEqual(len(all_usb_ids), len(set(all_usb_ids)), "All USB IDs should be unique")

    def test_usb_device_ids_passed_to_create_nodes(self):
        """
        Проверяет, что USB device IDs правильно передаются в create_lab_nodes_and_connectors.
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
        
        form = CompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        
        competition = form.save()
        
        # Проверяем, что create_lab_nodes_and_connectors был вызван с правильными USB IDs
        comp2users = Competition2User.objects.filter(competition=competition)
        self.assertGreater(len(call_args_list), 0, 
                          "create_lab_nodes_and_connectors should be called at least once")
        
        # Проверяем, что USB IDs переданы правильно
        # Создаем словарь для сопоставления username -> comp2user
        user_map = {comp2user.user.username: comp2user for comp2user in comp2users}
        
        for args, kwargs in call_args_list:
            # args: (lab, lab_name, username)
            # kwargs: {usb_device_ids=...}
            if len(args) >= 3:
                username = args[2]
                if username in user_map:
                    comp2user = user_map[username]
                    expected_usb_ids = comp2user.deploy_meta.get('usb_device_ids', [])
                    actual_usb_ids = kwargs.get('usb_device_ids', [])
                    self.assertEqual(actual_usb_ids, expected_usb_ids,
                                   f"USB IDs for user {username} should match deploy_meta")

    def test_usb_device_ids_replacement_in_qemu_options(self):
        """
        Проверяет, что USB device IDs правильно заменяются в qemu_options при создании узлов.
        """
        from interface.utils import replace_usb_device_ids_in_nodes
        from dynamic_config.models import ConfigEntry
        
        ConfigEntry.objects.update_or_create(
            key='USB_DEVICES_COUNT',
            defaults={'value': '20'}
        )
        
        form = CompetitionForm(data=self.form_data)
        self.assertTrue(form.is_valid())
        
        competition = form.save()
        
        # Получаем первый Competition2User для проверки
        comp2user = Competition2User.objects.filter(competition=competition).first()
        self.assertIsNotNone(comp2user, "Should have at least one Competition2User")
        
        usb_ids = comp2user.deploy_meta.get('usb_device_ids', [])
        self.assertGreater(len(usb_ids), 0, "Should have USB IDs")
        
        # Проверяем замену в qemu_options
        modified_nodes = replace_usb_device_ids_in_nodes(self.nodes_data, usb_ids)
        
        # Проверяем, что опции были заменены
        for node in modified_nodes:
            usb_id_index = 0
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
