from django.test import TransactionTestCase
from unittest.mock import patch
import json

from interface.forms import SimpleKkzForm
from interface.models import (
    Kkz, KkzLab, KkzPreview, Competition, Competition2User,
    Platoon, User, Lab, LabTask, LabType
)


class SimpleKkzFormTest(TransactionTestCase):
    """
    Тесты для SimpleKkzForm - упрощенной формы создания ККЗ.
    Используем TransactionTestCase для корректной работы с операциями в соседних потоках.
    """
    def setUp(self):
        self.platoon = Platoon.objects.create(
            number=2512,
            learning_year=1
        )

        self.users = []
        for i in range(3):
            user = User.objects.create_user(
                username=f"student_{i}",
                first_name=f"Student_{i}",
                last_name="Test",
                password="testpass",
                platoon=self.platoon
            )
            self.users.append(user)

        self.labs = []
        self.tasks_by_lab = {}

        for i in range(2):
            lab = Lab.objects.create(
                name=f"Exam Lab {i + 1}",
                platform="PN",
                lab_type=LabType.EXAM,
                learning_years=[1]
            )
            self.labs.append(lab)

            tasks = []
            for j in range(3):
                task = LabTask.objects.create(
                    lab=lab,
                    task_id=f"Task {j + 1}",
                    description=f"Lab {i + 1} Task {j + 1}"
                )
                tasks.append(task)
            self.tasks_by_lab[lab.id] = tasks

        self.labs_data = []
        for lab in self.labs:
            task_ids = [t.id for t in self.tasks_by_lab[lab.id]]
            self.labs_data.append({
                'lab_id': lab.id,
                'name': lab.name,
                'included': True,
                'task_ids': task_ids,
                'num_tasks': len(task_ids),
                'max_tasks_limit': None
            })

        self.form_data = {
            'name': 'Test KKZ',
            'platoon': self.platoon.pk,
            'duration_0': '0',
            'duration_1': '2',
            'duration_2': '0',
            'unified_tasks': False,
            'labs_data': json.dumps(self.labs_data)
        }

    @patch("interface.pnet_session_manager.PNetSessionManager.delete_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.logout")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_nodes_and_connectors")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.login")
    def test_simple_kkz_form_creation_and_deletion(
            self,
            mock_login,
            mock_create_lab,
            mock_create_nodes,
            mock_logout,
            mock_delete_lab
    ):
        """
        1) Создать ККЗ через SimpleKkzForm
        2) Проверить, что для каждой лабы и каждого пользователя вызваны
           create_lab_for_user и create_lab_nodes_and_connectors ровно 1 раз
        3) Удалить ККЗ
        4) Проверить, что для каждой лабы и каждого пользователя вызван delete_lab_for_user
        """

        form = SimpleKkzForm(data=self.form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        kkz = form.create_kkz()

        self.assertIsInstance(kkz, Kkz)
        self.assertTrue(Kkz.objects.filter(pk=kkz.pk).exists())
        self.assertEqual(kkz.name, 'Test KKZ')

        kkz_labs = KkzLab.objects.filter(kkz=kkz)
        self.assertEqual(kkz_labs.count(), len(self.labs))

        competitions = Competition.objects.filter(kkz=kkz)
        self.assertEqual(competitions.count(), len(self.labs))

        mock_login.assert_called()
        # mock_logout.assert_called()

        expected_calls = len(self.labs) * len(self.users)
        self.assertEqual(
            mock_create_lab.call_count,
            expected_calls,
            f"Expected create_lab to be called {expected_calls} times "
            f"({len(self.labs)} labs × {len(self.users)} users), "
            f"but was called {mock_create_lab.call_count} times"
        )
        self.assertEqual(
            mock_create_nodes.call_count,
            expected_calls,
            f"Expected create_lab_nodes_and_connectors to be called {expected_calls} times "
            f"({len(self.labs)} labs × {len(self.users)} users), "
            f"but was called {mock_create_nodes.call_count} times"
        )

        for user in self.users:
            for lab in self.labs:
                competition = Competition.objects.get(kkz=kkz, lab=lab)
                comp2user_exists = Competition2User.objects.filter(
                    competition=competition,
                    user=user
                ).exists()
                self.assertTrue(
                    comp2user_exists,
                    f"Competition2User not found for user {user.username} and lab {lab.name}"
                )

                preview_exists = KkzPreview.objects.filter(
                    kkz=kkz,
                    lab=lab,
                    user=user
                ).exists()
                self.assertTrue(
                    preview_exists,
                    f"KkzPreview not found for user {user.username} and lab {lab.name}"
                )

        mock_delete_lab.reset_mock()
        comp2user_pks = list(
            Competition2User.objects.filter(
                competition__kkz=kkz
            ).values_list('pk', flat=True)
        )

        kkz.delete()

        self.assertEqual(
            mock_delete_lab.call_count,
            expected_calls,
            f"Expected delete_lab to be called {expected_calls} times "
            f"({len(self.labs)} labs × {len(self.users)} users), "
            f"but was called {mock_delete_lab.call_count} times"
        )

        for pk in comp2user_pks:
            self.assertFalse(
                Competition2User.objects.filter(pk=pk).exists(),
                f"Competition2User with pk={pk} should have been deleted"
            )

        self.assertFalse(Kkz.objects.filter(pk=kkz.pk).exists())

    @patch("interface.pnet_session_manager.PNetSessionManager.delete_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.logout")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_nodes_and_connectors")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.login")
    def test_simple_kkz_form_with_excluded_lab(
            self,
            mock_login,
            mock_create_lab,
            mock_create_nodes,
            mock_logout,
            mock_delete_lab
    ):
        """
        Проверяем что исключенные лабы (included=False) не создают Competition и не вызывают pnet операции
        """
        self.labs_data[1]['included'] = False
        form_data = {
            'name': self.form_data['name'],
            'platoon': self.form_data['platoon'],
            'duration_0': self.form_data['duration_0'],
            'duration_1': self.form_data['duration_1'],
            'duration_2': self.form_data['duration_2'],
            'unified_tasks': self.form_data['unified_tasks'],
            'labs_data': json.dumps(self.labs_data)
        }

        form = SimpleKkzForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        kkz = form.create_kkz()

        competitions = Competition.objects.filter(kkz=kkz)
        self.assertEqual(competitions.count(), 1)

        self.assertTrue(
            Competition.objects.filter(kkz=kkz, lab=self.labs[0]).exists()
        )
        self.assertFalse(
            Competition.objects.filter(kkz=kkz, lab=self.labs[1]).exists()
        )
        expected_calls = len(self.users)

        self.assertEqual(
            mock_create_lab.call_count,
            expected_calls,
            f"Expected create_lab to be called {expected_calls} times (1 lab × {len(self.users)} users)"
        )

        self.assertEqual(
            mock_create_nodes.call_count,
            expected_calls,
            f"Expected create_lab_nodes_and_connectors to be called {expected_calls} times"
        )

    @patch("interface.pnet_session_manager.PNetSessionManager.delete_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.logout")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_nodes_and_connectors")
    @patch("interface.pnet_session_manager.PNetSessionManager.create_lab_for_user")
    @patch("interface.pnet_session_manager.PNetSessionManager.login")
    def test_simple_kkz_form_unified_tasks(
            self,
            mock_login,
            mock_create_lab,
            mock_create_nodes,
            mock_logout,
            mock_delete_lab
    ):
        """
        Проверяем что при unified_tasks=True все пользователи получают одинаковые задания
        """
        form_data = {
            'name': self.form_data['name'],
            'platoon': self.form_data['platoon'],
            'duration_0': self.form_data['duration_0'],
            'duration_1': self.form_data['duration_1'],
            'duration_2': self.form_data['duration_2'],
            'unified_tasks': True,
            'labs_data': self.form_data['labs_data']
        }

        form = SimpleKkzForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        kkz = form.create_kkz()
        for lab in self.labs:
            competition = Competition.objects.get(kkz=kkz, lab=lab)

            first_user_comp2user = Competition2User.objects.get(
                competition=competition,
                user=self.users[0]
            )
            first_user_tasks = set(first_user_comp2user.tasks.values_list('id', flat=True))

            for user in self.users[1:]:
                comp2user = Competition2User.objects.get(
                    competition=competition,
                    user=user
                )
                user_tasks = set(comp2user.tasks.values_list('id', flat=True))
                self.assertEqual(
                    first_user_tasks,
                    user_tasks,
                    f"User {user.username} has different tasks than user {self.users[0].username} in unified mode"
                )

    def test_simple_kkz_form_validation_no_labs(self):
        """
        Проверяем что форма не валидна если не выбрана ни одна лаба
        """
        for lab_data in self.labs_data:
            lab_data['included'] = False

        form_data = {
            'name': self.form_data['name'],
            'platoon': self.form_data['platoon'],
            'duration_0': self.form_data['duration_0'],
            'duration_1': self.form_data['duration_1'],
            'duration_2': self.form_data['duration_2'],
            'unified_tasks': self.form_data['unified_tasks'],
            'labs_data': json.dumps(self.labs_data)
        }

        form = SimpleKkzForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('labs_data', form.errors)

    def test_simple_kkz_form_validation_empty_platoon(self):
        """
        Проверяем что форма падает с ошибкой если во взводе нет пользователей
        """
        empty_platoon = Platoon.objects.create(number=9999, learning_year=1)
        form_data = {
            'name': self.form_data['name'],
            'platoon': empty_platoon.pk,
            'duration_0': self.form_data['duration_0'],
            'duration_1': self.form_data['duration_1'],
            'duration_2': self.form_data['duration_2'],
            'unified_tasks': self.form_data['unified_tasks'],
            'labs_data': self.form_data['labs_data']
        }

        form = SimpleKkzForm(data=form_data)
        self.assertTrue(form.is_valid())

        with self.assertRaises(Exception) as context:
            form.create_kkz()

        self.assertIn("Во взводе нет пользователей", str(context.exception))