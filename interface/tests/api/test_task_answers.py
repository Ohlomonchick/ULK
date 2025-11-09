from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.test import Client
import json

from interface.models import (
    Competition, Platoon, User, Lab, LabTask, Answers,
    Competition2User, TeamCompetition, Team, TeamCompetition2Team
)


class BaseTaskAnswersTestCase(TestCase):
    """
    Базовый класс для тестов API с общими методами
    """
    
    def setUp(self):
        self.client = Client()
        self.user = self._create_user()
        self.lab = self._create_lab()
        self.competition = self._create_competition()
        self.competition_user = Competition2User.objects.create(
            competition=self.competition,
            user=self.user
        )
        self.client.login(username='testuser', password='testpass123')
    
    def _create_user(self, username='testuser', password='testpass123'):
        """Создает и возвращает пользователя"""
        return User.objects.create_user(
            username=username,
            password=password,
            first_name='Test',
            last_name='User',
            pnet_login=username
        )
    
    def _create_lab(self, name='Test Lab', slug='test-lab'):
        """Создает и возвращает лабораторную работу"""
        return Lab.objects.create(
            name=name,
            platform='NO',
            slug=slug,
            description='Test description'
        )
    
    def _create_competition(self):
        """Создает и возвращает соревнование"""
        return Competition.objects.create(
            slug='test-competition',
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=2),
            lab=self.lab,
            participants=5
        )
    
    def _create_task(self, task_id, description='Task', question='', answer=''):
        """Создает задание с указанными параметрами"""
        return LabTask.objects.create(
            lab=self.lab,
            task_id=task_id,
            description=description,
            question=question,
            answer=answer
        )
    
    def _add_tasks_to_user(self, *tasks):
        """Добавляет задания пользователю"""
        self.competition_user.tasks.add(*tasks)
    
    def _post_answers(self, answers_dict):
        """Отправляет ответы на проверку"""
        return self.client.post(
            self.url,
            data=json.dumps({
                'competition_slug': self.competition.slug,
                'answers': answers_dict
            }),
            content_type='application/json'
        )
    
    def _assert_answer_exists(self, task, should_exist=True):
        """Проверяет наличие/отсутствие ответа"""
        exists = Answers.objects.filter(
            user=self.user,
            lab=self.lab,
            lab_task=task
        ).exists()
        if should_exist:
            self.assertTrue(exists, f'Answer for task {task.task_id} not found')
        else:
            self.assertFalse(exists, f'Answer for task {task.task_id} should not exist')
    
    def _count_answers(self):
        """Возвращает количество ответов пользователя"""
        return Answers.objects.filter(user=self.user, lab=self.lab).count()


class CheckTaskAnswersAPITestCase(BaseTaskAnswersTestCase):
    """
    Тесты для API endpoint /api/check_task_answers/
    Проверяет различные сценарии с заданиями (с вопросами и без)
    """
    
    def setUp(self):
        super().setUp()
        self.url = reverse('interface_api:check_task_answers')

    def test_check_answers_all_tasks_without_questions(self):
        """
        Тест 1: Все задания без вопросов (question пустой или None)
        Должен вернуть success=True, но results будет пустым
        """
        task1 = self._create_task('task_1', question='', answer='')
        task2 = self._create_task('task_2', question=None, answer=None)
        self._add_tasks_to_user(task1, task2)
        
        response = self._post_answers({
            str(task1.id): 'some answer',
            str(task2.id): 'another answer'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 0)
        self.assertEqual(self._count_answers(), 0)

    def test_check_answers_all_tasks_with_questions_correct(self):
        """
        Тест 2: Все задания с вопросами, все ответы правильные
        Должны создаться записи Answers для каждого задания
        """
        tasks = [
            self._create_task('task_1', question='What is 2+2?', answer='4'),
            self._create_task('task_2', question='Capital of France?', answer='Paris'),
            self._create_task('task_3', question='Color of sky?', answer='Blue')
        ]
        self._add_tasks_to_user(*tasks)
        
        response = self._post_answers({
            str(tasks[0].id): '4',
            str(tasks[1].id): 'paris',  # Регистронезависимость
            str(tasks[2].id): 'BLUE'     # Регистронезависимость
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 3)
        
        for task in tasks:
            self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
            self.assertEqual(data['results'][str(task.id)]['message'], 'Верно!')
            self._assert_answer_exists(task, should_exist=True)
        
        self.assertEqual(self._count_answers(), 3)

    def test_check_answers_all_tasks_with_questions_incorrect(self):
        """
        Тест 2b: Все задания с вопросами, все ответы неправильные
        НЕ должны создаться записи Answers
        """
        tasks = [
            self._create_task('task_1', question='What is 2+2?', answer='4'),
            self._create_task('task_2', question='Capital of France?', answer='Paris')
        ]
        self._add_tasks_to_user(*tasks)
        
        response = self._post_answers({
            str(tasks[0].id): '5',
            str(tasks[1].id): 'London'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 2)
        
        for task in tasks:
            self.assertEqual(data['results'][str(task.id)]['status'], 'incorrect')
            self.assertEqual(data['results'][str(task.id)]['message'], 'Неверно')
        
        self.assertEqual(self._count_answers(), 0)

    def test_check_answers_mixed_tasks(self):
        """
        Тест 3: Часть заданий с вопросами, часть без
        Должны обрабатываться только задания с вопросами
        """
        with_q = [
            self._create_task('task_q1', question='What is 10+5?', answer='15'),
            self._create_task('task_q2', question='What is 3*3?', answer='9')
        ]
        without_q = [
            self._create_task('task_no_q1', question='', answer=''),
            self._create_task('task_no_q2', question=None, answer=None)
        ]
        self._add_tasks_to_user(*with_q, *without_q)
        
        response = self._post_answers({
            str(with_q[0].id): '15',      # Правильный
            str(with_q[1].id): '8',       # Неправильный
            str(without_q[0].id): 'ignored',
            str(without_q[1].id): 'also ignored'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['results']), 2)
        
        # Проверяем, что обработаны только задания с вопросами
        self.assertIn(str(with_q[0].id), data['results'])
        self.assertIn(str(with_q[1].id), data['results'])
        self.assertNotIn(str(without_q[0].id), data['results'])
        self.assertNotIn(str(without_q[1].id), data['results'])
        
        self.assertEqual(data['results'][str(with_q[0].id)]['status'], 'correct')
        self.assertEqual(data['results'][str(with_q[1].id)]['status'], 'incorrect')
        self.assertEqual(self._count_answers(), 1)
        
        answer = Answers.objects.get(user=self.user, lab=self.lab)
        self.assertEqual(answer.lab_task, with_q[0])

    def test_check_answers_duplicate_prevention(self):
        """
        Тест 4: Задание с ответом сохраняется Answer извне (по API)
        При повторной отправке правильного ответа должен использоваться get_or_create
        и НЕ дублироваться запись
        """
        task = self._create_task('task_1', question='What is the answer?', answer='42')
        self._add_tasks_to_user(task)
        
        # Создаем ответ извне (имитация внешнего API)
        external_answer = Answers.objects.create(
            lab=self.lab,
            user=self.user,
            lab_task=task,
            datetime=timezone.now() - timedelta(minutes=30)
        )
        self.assertEqual(self._count_answers(), 1)
        
        response = self._post_answers({str(task.id): '42'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        
        # Проверяем, что запись НЕ дублировалась
        self.assertEqual(self._count_answers(), 1)
        answer = Answers.objects.get(user=self.user, lab=self.lab, lab_task=task)
        self.assertEqual(answer.id, external_answer.id)

    def test_check_answers_multiple_correct_then_duplicate(self):
        """
        Тест 4b: Несколько заданий, часть уже выполнена извне
        Проверяем, что новые создаются, старые не дублируются
        """
        tasks = [
            self._create_task('task_1', question='Q1?', answer='A1'),
            self._create_task('task_2', question='Q2?', answer='A2'),
            self._create_task('task_3', question='Q3?', answer='A3')
        ]
        self._add_tasks_to_user(*tasks)
        
        # Создаем ответ для первого задания извне
        Answers.objects.create(
            lab=self.lab,
            user=self.user,
            lab_task=tasks[0],
            datetime=timezone.now() - timedelta(minutes=30)
        )
        self.assertEqual(self._count_answers(), 1)
        
        response = self._post_answers({
            str(tasks[0].id): 'A1',  # Уже существует
            str(tasks[1].id): 'A2',  # Новый
            str(tasks[2].id): 'A3'   # Новый
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        for task in tasks:
            self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        
        # Проверяем: должно быть 3 ответа (не 4!)
        self.assertEqual(self._count_answers(), 3)
        
        # Каждый ответ уникален
        for task in tasks:
            task_answers = Answers.objects.filter(
                user=self.user, lab=self.lab, lab_task=task
            )
            self.assertEqual(task_answers.count(), 1)

    def test_check_answers_empty_answer_skipped(self):
        """
        Тест: Пустые ответы должны быть пропущены (status: skipped)
        """
        task = self._create_task('task_1', question='Question?', answer='Answer')
        self._add_tasks_to_user(task)
        
        response = self._post_answers({str(task.id): ''})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task.id)]['status'], 'skipped')
        self.assertEqual(self._count_answers(), 0)

    def test_check_answers_with_flag_correct(self):
        """
        Тест: Проверка флага как правильного ответа для отдельного пользователя
        Флаг должен засчитываться как правильный ответ
        """
        task = self._create_task('task_1', question='What is the answer?', answer='42')
        self._add_tasks_to_user(task)
        
        # Устанавливаем флаг для задания
        self.competition_user.generated_flags = [
            {'task_id': 'task_1', 'flag': 'FLAG_TestFlag123'}
        ]
        self.competition_user.save()
        
        # Отправляем флаг как ответ
        response = self._post_answers({str(task.id): 'FLAG_TestFlag123'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        self.assertEqual(data['results'][str(task.id)]['message'], 'Верно!')
        self._assert_answer_exists(task, should_exist=True)
        self.assertEqual(self._count_answers(), 1)

    def test_check_answers_with_flag_case_insensitive(self):
        """
        Тест: Проверка флага регистронезависимо
        """
        task = self._create_task('task_1', question='What is the answer?', answer='42')
        self._add_tasks_to_user(task)
        
        self.competition_user.generated_flags = [
            {'task_id': 'task_1', 'flag': 'FLAG_TestFlag123'}
        ]
        self.competition_user.save()
        
        # Отправляем флаг в другом регистре
        response = self._post_answers({str(task.id): 'flag_testflag123'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')

    def test_check_answers_flag_only_for_correct_task(self):
        """
        Тест: Флаг засчитывается только для соответствующего задания
        """
        task1 = self._create_task('task_1', question='Q1?', answer='A1')
        task2 = self._create_task('task_2', question='Q2?', answer='A2')
        self._add_tasks_to_user(task1, task2)
        
        # Устанавливаем флаг только для task_1
        self.competition_user.generated_flags = [
            {'task_id': 'task_1', 'flag': 'FLAG_FlagForTask1'}
        ]
        self.competition_user.save()
        
        # Пытаемся использовать флаг task_1 для task_2
        response = self._post_answers({
            str(task1.id): 'FLAG_FlagForTask1',  # Правильно
            str(task2.id): 'FLAG_FlagForTask1'   # Неправильно (флаг для другого задания)
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task1.id)]['status'], 'correct')
        self.assertEqual(data['results'][str(task2.id)]['status'], 'incorrect')
        self.assertEqual(self._count_answers(), 1)

    def test_check_answers_regular_answer_has_priority(self):
        """
        Тест: Обычный ответ проверяется первым, флаг - только если обычный не подошел
        """
        task = self._create_task('task_1', question='What is 2+2?', answer='4')
        self._add_tasks_to_user(task)
        
        self.competition_user.generated_flags = [
            {'task_id': 'task_1', 'flag': 'FLAG_TestFlag123'}
        ]
        self.competition_user.save()
        
        # Отправляем правильный обычный ответ
        response = self._post_answers({str(task.id): '4'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        self._assert_answer_exists(task, should_exist=True)

    def test_check_answers_flag_when_regular_answer_wrong(self):
        """
        Тест: Флаг засчитывается, если обычный ответ неправильный
        """
        task = self._create_task('task_1', question='What is 2+2?', answer='4')
        self._add_tasks_to_user(task)
        
        self.competition_user.generated_flags = [
            {'task_id': 'task_1', 'flag': 'FLAG_TestFlag123'}
        ]
        self.competition_user.save()
        
        # Отправляем неправильный обычный ответ, но правильный флаг
        response = self._post_answers({str(task.id): 'FLAG_TestFlag123'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        self._assert_answer_exists(task, should_exist=True)

    def test_check_answers_unauthenticated(self):
        """Тест: Неавторизованный пользователь должен получить 401"""
        self.client.logout()
        response = self._post_answers({})
        self.assertEqual(response.status_code, 401)

    def test_check_answers_not_participant(self):
        """Тест: Пользователь не участник соревнования - должен получить 403"""
        other_user = self._create_user('otheruser', 'testpass456')
        self.client.logout()
        self.client.login(username='otheruser', password='testpass456')
        response = self._post_answers({})
        self.assertEqual(response.status_code, 403)


class GetUserTasksStatusAPITestCase(BaseTaskAnswersTestCase):
    """
    Тесты для API endpoint /api/get_user_tasks_status/
    Проверяет корректность возврата статуса заданий пользователя
    """
    
    def setUp(self):
        super().setUp()
        self.url = reverse('interface_api:get_user_tasks_status')
    
    def _get_status(self, competition_slug=None):
        """Получает статус заданий"""
        slug = competition_slug or self.competition.slug
        return self.client.get(self.url, {'competition_slug': slug})

    def test_get_status_all_tasks_not_done(self):
        """Тест: Все задания не выполнены"""
        tasks = [
            self._create_task('task_1', question='Q1?', answer='A1'),
            self._create_task('task_2', question='', answer='')
        ]
        self._add_tasks_to_user(*tasks)
        
        response = self._get_status()
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['tasks']), 2)
        self.assertTrue(data['has_questions'])
        
        tasks_by_id = {t['id']: t for t in data['tasks']}
        self.assertFalse(tasks_by_id[tasks[0].id]['done'])
        self.assertFalse(tasks_by_id[tasks[1].id]['done'])
        self.assertTrue(tasks_by_id[tasks[0].id]['has_question'])
        self.assertFalse(tasks_by_id[tasks[1].id]['has_question'])

    def test_get_status_some_tasks_done(self):
        """Тест: Часть заданий выполнена"""
        tasks = [
            self._create_task(f'task_{i}', question=f'Q{i}?', answer=f'A{i}')
            for i in range(1, 4)
        ]
        self._add_tasks_to_user(*tasks)
        
        # Создаем ответы для первых двух заданий
        for task in tasks[:2]:
            Answers.objects.create(
                lab=self.lab, user=self.user,
                lab_task=task, datetime=timezone.now()
            )
        
        response = self._get_status()
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        tasks_by_id = {t['id']: t for t in data['tasks']}
        self.assertTrue(tasks_by_id[tasks[0].id]['done'])
        self.assertTrue(tasks_by_id[tasks[1].id]['done'])
        self.assertFalse(tasks_by_id[tasks[2].id]['done'])

    def test_get_status_no_questions(self):
        """Тест: Все задания без вопросов - has_questions должен быть False"""
        tasks = [
            self._create_task('task_1', question='', answer=''),
            self._create_task('task_2', question=None, answer=None)
        ]
        self._add_tasks_to_user(*tasks)
        
        response = self._get_status()
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['has_questions'])

    def test_get_status_unauthenticated(self):
        """Тест: Неавторизованный пользователь должен получить 401"""
        self.client.logout()
        response = self._get_status()
        self.assertEqual(response.status_code, 401)

    def test_get_status_competition_not_found(self):
        """Тест: Несуществующее соревнование - должен получить 404"""
        response = self._get_status('non-existent-slug')
        self.assertEqual(response.status_code, 404)


class CheckTaskAnswersWithFlagsTeamTestCase(TestCase):
    """
    Тесты для проверки флагов в командных соревнованиях
    """
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='teamuser',
            password='testpass123',
            first_name='Team',
            last_name='User',
            pnet_login='teamuser'
        )
        self.lab = Lab.objects.create(
            name='Team Lab',
            platform='NO',
            slug='team-lab',
            description='Team lab description'
        )
        self.competition = TeamCompetition.objects.create(
            slug='team-competition',
            start=timezone.now() - timedelta(hours=1),
            finish=timezone.now() + timedelta(hours=2),
            lab=self.lab,
            participants=5
        )
        self.team = Team.objects.create(name='Test Team', slug='test-team')
        self.team.users.add(self.user)
        
        self.team_competition = TeamCompetition2Team.objects.create(
            competition=self.competition,
            team=self.team
        )
        self.client.login(username='teamuser', password='testpass123')
        self.url = reverse('interface_api:check_task_answers')
    
    def _create_task(self, task_id, description='Task', question='', answer=''):
        """Создает задание с указанными параметрами"""
        return LabTask.objects.create(
            lab=self.lab,
            task_id=task_id,
            description=description,
            question=question,
            answer=answer
        )
    
    def _add_tasks_to_team(self, *tasks):
        """Добавляет задания команде"""
        self.team_competition.tasks.add(*tasks)
    
    def _post_answers(self, answers_dict):
        """Отправляет ответы на проверку"""
        return self.client.post(
            self.url,
            data=json.dumps({
                'competition_slug': self.competition.slug,
                'answers': answers_dict
            }),
            content_type='application/json'
        )
    
    def _assert_answer_exists(self, task, should_exist=True):
        """Проверяет наличие/отсутствие ответа для команды"""
        exists = Answers.objects.filter(
            team=self.team,
            lab=self.lab,
            lab_task=task
        ).exists()
        if should_exist:
            self.assertTrue(exists, f'Answer for task {task.task_id} not found')
        else:
            self.assertFalse(exists, f'Answer for task {task.task_id} should not exist')
    
    def test_team_flag_correct(self):
        """
        Тест: Проверка флага как правильного ответа для команды
        """
        task = self._create_task('team_task_1', question='What is the answer?', answer='42')
        self._add_tasks_to_team(task)
        
        # Устанавливаем флаг для задания
        self.team_competition.generated_flags = [
            {'task_id': 'team_task_1', 'flag': 'FLAG_TeamFlag123'}
        ]
        self.team_competition.save()
        
        # Отправляем флаг как ответ
        response = self._post_answers({str(task.id): 'FLAG_TeamFlag123'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        self.assertEqual(data['results'][str(task.id)]['message'], 'Верно!')
        self._assert_answer_exists(task, should_exist=True)
    
    def test_team_flag_case_insensitive(self):
        """
        Тест: Проверка флага регистронезависимо для команды
        """
        task = self._create_task('team_task_1', question='What is the answer?', answer='42')
        self._add_tasks_to_team(task)
        
        self.team_competition.generated_flags = [
            {'task_id': 'team_task_1', 'flag': 'FLAG_TeamFlag123'}
        ]
        self.team_competition.save()
        
        # Отправляем флаг в другом регистре
        response = self._post_answers({str(task.id): 'flag_teamflag123'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        self._assert_answer_exists(task, should_exist=True)
    
    def test_team_flag_only_for_correct_task(self):
        """
        Тест: Флаг засчитывается только для соответствующего задания в команде
        """
        task1 = self._create_task('team_task_1', question='Q1?', answer='A1')
        task2 = self._create_task('team_task_2', question='Q2?', answer='A2')
        self._add_tasks_to_team(task1, task2)
        
        # Устанавливаем флаг только для task_1
        self.team_competition.generated_flags = [
            {'task_id': 'team_task_1', 'flag': 'FLAG_FlagForTask1'}
        ]
        self.team_competition.save()
        
        # Пытаемся использовать флаг task_1 для task_2
        response = self._post_answers({
            str(task1.id): 'FLAG_FlagForTask1',  # Правильно
            str(task2.id): 'FLAG_FlagForTask1'   # Неправильно
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task1.id)]['status'], 'correct')
        self.assertEqual(data['results'][str(task2.id)]['status'], 'incorrect')
    
    def test_team_regular_answer_has_priority(self):
        """
        Тест: Обычный ответ проверяется первым, флаг - только если обычный не подошел (команда)
        """
        task = self._create_task('team_task_1', question='What is 2+2?', answer='4')
        self._add_tasks_to_team(task)
        
        self.team_competition.generated_flags = [
            {'task_id': 'team_task_1', 'flag': 'FLAG_TeamFlag123'}
        ]
        self.team_competition.save()
        
        # Отправляем правильный обычный ответ
        response = self._post_answers({str(task.id): '4'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task.id)]['status'], 'correct')
        self._assert_answer_exists(task, should_exist=True)
    
    def test_team_multiple_flags(self):
        """
        Тест: Несколько заданий с разными флагами для команды
        """
        task1 = self._create_task('team_task_1', question='Q1?', answer='A1')
        task2 = self._create_task('team_task_2', question='Q2?', answer='A2')
        task3 = self._create_task('team_task_3', question='Q3?', answer='A3')
        self._add_tasks_to_team(task1, task2, task3)
        
        self.team_competition.generated_flags = [
            {'task_id': 'team_task_1', 'flag': 'FLAG_Flag1'},
            {'task_id': 'team_task_2', 'flag': 'FLAG_Flag2'},
            {'task_id': 'team_task_3', 'flag': 'FLAG_Flag3'}
        ]
        self.team_competition.save()
        
        # Отправляем правильные флаги для всех заданий
        response = self._post_answers({
            str(task1.id): 'FLAG_Flag1',
            str(task2.id): 'FLAG_Flag2',
            str(task3.id): 'FLAG_Flag3'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['results'][str(task1.id)]['status'], 'correct')
        self.assertEqual(data['results'][str(task2.id)]['status'], 'correct')
        self.assertEqual(data['results'][str(task3.id)]['status'], 'correct')
        
        # Проверяем, что все ответы сохранены
        self.assertEqual(Answers.objects.filter(team=self.team, lab=self.lab).count(), 3)

