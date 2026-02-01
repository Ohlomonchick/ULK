"""
Тесты для выборки заданий с учётом зависимостей (sample_tasks_with_dependencies)
и проверки корректности выдачи при разных ограничениях.
"""
import random
from unittest.mock import patch

from django.test import TestCase

from interface.models import Lab, LabTask, LabType, Platoon, User
from interface.utils import sample_tasks_with_dependencies


def _task_has_dependencies(task):
    """Есть ли у задания зависимости (по полю dependencies)."""
    deps = getattr(task, 'dependencies', None) or ''
    return bool([p for p in deps.split(',') if p.strip()])


def _all_deps_in_result(task, key_to_task, selected_ids):
    """Все ли зависимости задания есть в selected_ids (по pk)."""
    deps = getattr(task, 'dependencies', None) or ''
    for part in deps.split(','):
        key = part.strip()
        if not key:
            continue
        dep = key_to_task.get(key)
        if dep is not None and dep.pk not in selected_ids:
            return False
    return True


def _is_dependency_closed(tasks, key_to_task):
    """Проверка: для каждого задания в списке все его зависимости тоже в списке."""
    ids = {t.pk for t in tasks}
    for task in tasks:
        deps = getattr(task, 'dependencies', None) or ''
        for part in deps.split(','):
            key = part.strip()
            if not key:
                continue
            dep = key_to_task.get(key)
            if dep is not None and dep.pk not in ids:
                return False
    return True


class SampleTasksWithDependenciesTestCase(TestCase):
    """Тесты для sample_tasks_with_dependencies."""

    def setUp(self):
        self.lab = Lab.objects.create(
            name="Test Lab Dependencies",
            platform="NO",
            lab_type=LabType.EXAM,
            learning_years=[1],
        )
        # Задания без зависимостей: 1, 2
        self.t1 = LabTask.objects.create(
            lab=self.lab,
            task_id="1",
            description="Task 1",
        )
        self.t2 = LabTask.objects.create(
            lab=self.lab,
            task_id="2",
            description="Task 2",
        )
        # Задание 3 зависит от 1 и 2
        self.t3 = LabTask.objects.create(
            lab=self.lab,
            task_id="3",
            description="Task 3",
            dependencies="1, 2",
        )
        # Задание 4 зависит от 1
        self.t4 = LabTask.objects.create(
            lab=self.lab,
            task_id="4",
            description="Task 4",
            dependencies="1",
        )
        # Задание 5 без зависимостей
        self.t5 = LabTask.objects.create(
            lab=self.lab,
            task_id="5",
            description="Task 5",
        )
        self.all_tasks = [self.t1, self.t2, self.t3, self.t4, self.t5]

    def _key_to_task(self, tasks):
        key_to_task = {}
        for t in tasks:
            key_to_task[str(t.pk)] = t
            if getattr(t, 'task_id', None) and str(t.task_id).strip():
                key_to_task[str(t.task_id).strip()] = t
        return key_to_task

    def test_empty_or_zero_returns_empty(self):
        """Пустой список или n<=0 возвращает пустой список."""
        self.assertEqual(sample_tasks_with_dependencies([], 5), [])
        self.assertEqual(sample_tasks_with_dependencies(self.all_tasks, 0), [])
        self.assertEqual(sample_tasks_with_dependencies(self.all_tasks, -1), [])

    def test_n1_only_tasks_without_dependencies(self):
        """При n=1 в выборке только задания без зависимостей."""
        for _ in range(30):
            result = sample_tasks_with_dependencies(self.all_tasks, 1)
            self.assertEqual(len(result), 1, msg="При n=1 должен быть ровно 1 элемент")
            self.assertFalse(
                _task_has_dependencies(result[0]),
                msg="При n=1 не должно быть задания с зависимостями",
            )
            self.assertIn(
                result[0].pk,
                [self.t1.pk, self.t2.pk, self.t5.pk],
                msg="Должны быть только t1, t2 или t5",
            )

    def test_n1_pool_only_with_deps_returns_empty(self):
        """При n=1 и пуле только из заданий с зависимостями — пустой результат."""
        tasks_with_deps = [self.t3, self.t4]
        result = sample_tasks_with_dependencies(tasks_with_deps, 1)
        self.assertEqual(result, [])

    def test_result_size_never_exceeds_n(self):
        """Размер результата не превышает n."""
        for n in (1, 2, 3, 4, 5, 10):
            for _ in range(20):
                result = sample_tasks_with_dependencies(self.all_tasks, n)
                self.assertLessEqual(
                    len(result),
                    n,
                    msg=f"При n={n} результат должен быть <= {n}",
                )

    def test_result_is_dependency_closed(self):
        """Результат замкнут по зависимостям: у каждого задания все его зависимости в списке."""
        key_to_task = self._key_to_task(self.all_tasks)
        for n in (2, 3, 4, 5):
            for _ in range(30):
                result = sample_tasks_with_dependencies(self.all_tasks, n)
                self.assertTrue(
                    _is_dependency_closed(result, key_to_task),
                    msg=f"Результат при n={n} должен быть замкнут по зависимостям: {[t.task_id for t in result]}",
                )

    def test_n2_dependent_task_comes_with_deps(self):
        """При n=2 если в выборке задание с зависимостью, то его зависимости тоже в выборке."""
        key_to_task = self._key_to_task(self.all_tasks)
        for _ in range(50):
            result = sample_tasks_with_dependencies(self.all_tasks, 2)
            if len(result) == 2:
                self.assertTrue(
                    _is_dependency_closed(result, key_to_task),
                    msg=f"При n=2 результат должен быть замкнут: {[t.task_id for t in result]}",
                )
                # Если попал t3 (зависит от 1,2), то в результате должны быть 1,2,3 — но n=2,
                # значит t3 при n=2 не может попасть (нужно 3 слота). Поэтому при n=2 в результате
                # могут быть только пары без «незакрытых» зависимостей.
                for task in result:
                    deps = getattr(task, 'dependencies', None) or ''
                    for key in deps.split(','):
                        key = key.strip()
                        if not key:
                            continue
                        dep = key_to_task.get(key)
                        if dep and dep.pk not in {t.pk for t in result}:
                            self.fail(f"Задание {task.task_id} зависит от {key}, но его нет в результате")

    def test_n3_can_include_task_with_two_deps(self):
        """При n=3 может попасть задание 3 вместе с 1 и 2."""
        key_to_task = self._key_to_task(self.all_tasks)
        found_t3_with_deps = False
        for _ in range(100):
            result = sample_tasks_with_dependencies(self.all_tasks, 3)
            result_ids = {t.task_id for t in result}
            if self.t3.pk in {t.pk for t in result}:
                self.assertIn("1", result_ids, "Если есть t3, должна быть зависимость 1")
                self.assertIn("2", result_ids, "Если есть t3, должна быть зависимость 2")
                found_t3_with_deps = True
            self.assertTrue(_is_dependency_closed(result, key_to_task))
        self.assertTrue(found_t3_with_deps, "За 100 итераций хотя бы раз должна попасть тройка (1,2,3)")

    def test_task_with_dep_not_in_pool_is_skipped(self):
        """Задание с зависимостью, которой нет в пуле, не попадает в выборку."""
        # Только t3 в пуле (зависит от 1, 2 которых нет в пуле)
        pool = [self.t3]
        result = sample_tasks_with_dependencies(pool, 5)
        self.assertEqual(result, [])

    def test_deterministic_with_seed(self):
        """При фиксированном seed результат детерминирован."""
        with patch.object(random, 'shuffle', side_effect=lambda x: x.reverse()):
            result1 = sample_tasks_with_dependencies(self.all_tasks, 2)
            result2 = sample_tasks_with_dependencies(self.all_tasks, 2)
            ids1 = [t.pk for t in result1]
            ids2 = [t.pk for t in result2]
            self.assertEqual(ids1, ids2)

    def test_dependencies_resolved_by_task_id(self):
        """Зависимости разрешаются по task_id (не только по pk)."""
        tasks = [self.t1, self.t4]  # t4 зависит от "1" (task_id t1)
        for _ in range(20):
            result = sample_tasks_with_dependencies(tasks, 2)
            self.assertEqual(len(result), 2)
            self.assertTrue(
                _is_dependency_closed(result, self._key_to_task(tasks)),
                "t4 и t1 должны оба быть в результате",
            )

    def test_n2_pair_with_one_dep(self):
        """При n=2 пара (задание с одной зависимостью + сама зависимость) корректна."""
        tasks = [self.t1, self.t4]  # t4 -> t1
        key_to_task = self._key_to_task(tasks)
        for _ in range(30):
            result = sample_tasks_with_dependencies(tasks, 2)
            self.assertLessEqual(len(result), 2)
            self.assertTrue(_is_dependency_closed(result, key_to_task))
            if len(result) == 2:
                self.assertEqual({self.t1.pk, self.t4.pk}, {t.pk for t in result})


class CompetitionFormDependenciesTestCase(TestCase):
    """
    Тесты выдачи заданий при создании соревнования (не ККЗ):
    при num_tasks=1 выдаются только задания без зависимостей,
    при num_tasks>=2 выдаётся замкнутое по зависимостям множество.
    """

    def setUp(self):
        from unittest.mock import MagicMock, patch

        self.lab = Lab.objects.create(
            name="Test Lab Deps",
            platform="NO",
            lab_type=LabType.EXAM,
            learning_years=[1],
        )
        self.t1 = LabTask.objects.create(
            lab=self.lab,
            task_id="1",
            description="Task 1",
        )
        self.t2 = LabTask.objects.create(
            lab=self.lab,
            task_id="2",
            description="Task 2",
        )
        self.t3 = LabTask.objects.create(
            lab=self.lab,
            task_id="3",
            description="Task 3",
            dependencies="1, 2",
        )
        self.platoon = Platoon.objects.create(
            number=99,
            learning_year=1,
        )
        self.user = User.objects.create_user(
            username="test_dep_user",
            password="testpass",
            platoon=self.platoon,
            pnet_login="pnet_dep",
            pnet_password="pnetpass",
        )

    def _key_to_task(self, tasks):
        key_to_task = {}
        for t in tasks:
            key_to_task[str(t.pk)] = t
            if getattr(t, 'task_id', None) and str(t.task_id).strip():
                key_to_task[str(t.task_id).strip()] = t
        return key_to_task

    def _is_dependency_closed(self, tasks, key_to_task):
        ids = {t.pk for t in tasks}
        for task in tasks:
            deps = getattr(task, 'dependencies', None) or ''
            for part in deps.split(','):
                key = part.strip()
                if not key:
                    continue
                dep = key_to_task.get(key)
                if dep is not None and dep.pk not in ids:
                    return False
        return True

    @patch("interface.forms.with_pnet_session_if_needed")
    @patch("interface.flag_deployment.get_flag_deployment_queue")
    def test_competition_num_tasks_one_assigns_only_without_deps(
        self, mock_queue, mock_pnet
    ):
        """При num_tasks=1 пользователю назначается только задание без зависимостей."""
        from datetime import timedelta

        from django.utils import timezone

        from interface.forms import CompetitionForm
        from interface.models import Competition2User

        mock_queue.return_value.get_tasks_by_competition.return_value = []
        mock_pnet.side_effect = lambda lab, fn: fn()

        tasks = [self.t1, self.t2, self.t3]
        form = CompetitionForm(
            data={
                "lab": self.lab.pk,
                "start": timezone.now(),
                "finish": timezone.now() + timedelta(hours=1),
                "platoons": [self.platoon.pk],
                "tasks": [self.t1.pk, self.t2.pk, self.t3.pk],
                "num_tasks": 1,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        comp = form.save()

        c2u = Competition2User.objects.get(competition=comp, user=self.user)
        assigned = list(c2u.tasks.all())
        self.assertEqual(len(assigned), 1)
        deps = (getattr(assigned[0], "dependencies", None) or "").strip()
        self.assertFalse(
            bool(deps),
            "При num_tasks=1 не должно назначаться задание с зависимостями",
        )
        self.assertIn(
            assigned[0].pk,
            [self.t1.pk, self.t2.pk],
            "Должно быть только t1 или t2",
        )

    @patch("interface.forms.with_pnet_session_if_needed")
    @patch("interface.flag_deployment.get_flag_deployment_queue")
    def test_competition_num_tasks_two_assigns_dependency_closed(
        self, mock_queue, mock_pnet
    ):
        """При num_tasks=2 назначенные задания замкнуты по зависимостям."""
        from datetime import timedelta

        from django.utils import timezone

        from interface.forms import CompetitionForm
        from interface.models import Competition2User

        mock_queue.return_value.get_tasks_by_competition.return_value = []
        mock_pnet.side_effect = lambda lab, fn: fn()

        form = CompetitionForm(
            data={
                "lab": self.lab.pk,
                "start": timezone.now(),
                "finish": timezone.now() + timedelta(hours=1),
                "platoons": [self.platoon.pk],
                "tasks": [self.t1.pk, self.t2.pk, self.t3.pk],
                "num_tasks": 2,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        comp = form.save()

        c2u = Competition2User.objects.get(competition=comp, user=self.user)
        assigned = list(c2u.tasks.all())
        self.assertLessEqual(len(assigned), 2)
        key_to_task = self._key_to_task([self.t1, self.t2, self.t3])
        self.assertTrue(
            self._is_dependency_closed(assigned, key_to_task),
            f"Назначенные задания должны быть замкнуты по зависимостям: {assigned}",
        )
