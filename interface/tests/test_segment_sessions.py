"""
Тесты для логики сегментных сессий (кросс-командное взаимодействие).

Покрывает:
1. _build_segment_sessions — распределение команд/пользователей по сегментам
2. _handle_segment_sessions — создание TeamCompetition2TeamsAndUsers и TeamOrUser2Segment
3. TeamCompetitionDetailView — контекст с segment_vm_names
4. get_issue_for_user — находит TeamCompetition2TeamsAndUsers для участника сегмента
5. Регрессия — старая логика лаб без сегментов не сломана
"""

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta
import uuid

from interface.forms import TeamCompetitionForm
from interface.models import (
    Lab, TeamCompetition, Team, User, Platoon,
    TopologySegment, TeamCompetition2TeamsAndUsers, TeamOrUser2Segment,
    TeamCompetition2Team, Competition2User, LabTask,
)
from interface.api_utils import get_issue_for_user


# ---------------------------------------------------------------------------
# Вспомогательные фабрики — уникальные имена через uuid-суффикс
# ---------------------------------------------------------------------------

def _uid():
    return uuid.uuid4().hex[:8]


def make_lab(segments_count=0, platform='CMD'):
    uid = _uid()
    lab = Lab.objects.create(
        name=f'Lab_{uid}',
        slug=f'lab-{uid}',
        platform=platform,
        description='',
        answer_flag='',
        NodesData=[{'name': 'vm1', 'template': 'docker', 'console': 'ssh'}],
        ConnectorsData=[],
        Connectors2CloudData=[],
        NetworksData=[],
    )
    segments = []
    for i in range(segments_count):
        seg = TopologySegment.objects.create(
            lab=lab,
            name=f'Сегмент {i+1}',
            vm_names=[f'vm{i+1}', 'shared_vm'],
        )
        segments.append(seg)
    return lab, segments


def make_user():
    uid = _uid()
    u = User.objects.create_user(username=f'user_{uid}', password='pass')
    u.pnet_login = f'user_{uid}'
    u.pnet_password = 'eve'
    u.save(update_fields=['pnet_login', 'pnet_password'])
    return u


def make_team(*users):
    uid = _uid()
    t = Team.objects.create(name=f'Team_{uid}', slug=f'team-{uid}')
    for u in users:
        t.users.add(u)
    return t


def make_competition(lab, **kwargs):
    defaults = dict(
        start=timezone.now() - timedelta(hours=1),
        finish=timezone.now() + timedelta(hours=2),
        participants=10,
    )
    defaults.update(kwargs)
    return TeamCompetition.objects.create(slug=f'comp-{_uid()}', lab=lab, **defaults)


# ---------------------------------------------------------------------------
# Патчи PNET — не ходим в реальный PNET ни в одном тесте
# ---------------------------------------------------------------------------

PNET_PATCHES = [
    patch('interface.pnet_session_manager.PNetSessionManager.login'),
    patch('interface.pnet_session_manager.PNetSessionManager.logout'),
    patch('interface.pnet_session_manager.PNetSessionManager.create_lab_for_user'),
    patch('interface.pnet_session_manager.PNetSessionManager.create_lab_nodes_and_connectors'),
    patch('interface.pnet_session_manager.PNetSessionManager.change_user_workspace'),
    patch('interface.pnet_session_manager.PNetSessionManager.delete_lab_for_user'),
    patch('interface.pnet_session_manager.PNetSessionManager.delete_lab_for_team'),
    patch('interface.elastic_utils.get_elastic_client', return_value=None),
    patch('interface.models.get_flag_deployment_queue'),
]


def start_pnet_patches():
    mocks = [p.start() for p in PNET_PATCHES]
    mocks[-1].return_value = MagicMock()
    return mocks


def stop_pnet_patches():
    for p in PNET_PATCHES:
        p.stop()


# ===========================================================================
# 1. Тесты _build_segment_sessions
# ===========================================================================

class BuildSegmentSessionsTest(TestCase):
    """Тесты логики распределения участников по сегментам."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start_pnet_patches()

    @classmethod
    def tearDownClass(cls):
        stop_pnet_patches()
        super().tearDownClass()

    def setUp(self):
        self.lab, self.segments = make_lab(segments_count=2)
        self.competition = make_competition(self.lab)

    def _make_form(self, teams=None, users=None):
        form = TeamCompetitionForm.__new__(TeamCompetitionForm)
        form.cleaned_data = {
            'teams': teams or [],
            'non_platoon_users': users or [],
            'platoons': [],
        }
        return form

    def test_two_teams_two_segments(self):
        t1 = make_team(make_user(), make_user())
        t2 = make_team(make_user(), make_user())
        form = self._make_form(teams=[t1, t2])
        with patch.object(form, 'get_all_users', return_value=[]):
            sessions = form._build_segment_sessions(self.competition, self.segments)

        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0]), 2)
        kinds = {kind for _, kind, _ in sessions[0]}
        self.assertEqual(kinds, {'team'})

    def test_two_users_two_segments(self):
        u1, u2 = make_user(), make_user()
        form = self._make_form(teams=[])
        with patch.object(form, 'get_all_users', return_value=[u1, u2]):
            sessions = form._build_segment_sessions(self.competition, self.segments)

        self.assertEqual(len(sessions), 1)
        self.assertEqual(len(sessions[0]), 2)
        kinds = {kind for _, kind, _ in sessions[0]}
        self.assertEqual(kinds, {'user'})

    def test_one_team_one_user_two_segments(self):
        """Смешанная сессия: одна команда + один пользователь."""
        t1 = make_team(make_user())
        u2 = make_user()
        form = self._make_form(teams=[t1])
        with patch.object(form, 'get_all_users', return_value=[u2]):
            sessions = form._build_segment_sessions(self.competition, self.segments)

        self.assertEqual(len(sessions), 1)
        kinds = {kind for _, kind, _ in sessions[0]}
        self.assertEqual(kinds, {'team', 'user'})

    def test_not_divisible_raises(self):
        """3 участника при 2 сегментах — AssertionError."""
        form = self._make_form(teams=[])
        with patch.object(form, 'get_all_users', return_value=[make_user(), make_user(), make_user()]):
            with self.assertRaises(AssertionError):
                form._build_segment_sessions(self.competition, self.segments)

    def test_empty_participants_returns_empty(self):
        form = self._make_form(teams=[])
        with patch.object(form, 'get_all_users', return_value=[]):
            sessions = form._build_segment_sessions(self.competition, self.segments)
        self.assertEqual(sessions, [])

    def test_four_teams_two_segments_two_sessions(self):
        teams = [make_team(make_user(), make_user()) for _ in range(4)]
        form = self._make_form(teams=teams)
        with patch.object(form, 'get_all_users', return_value=[]):
            sessions = form._build_segment_sessions(self.competition, self.segments)
        self.assertEqual(len(sessions), 2)
        for sess in sessions:
            self.assertEqual(len(sess), 2)

    def test_segments_assigned_correctly(self):
        """Каждый элемент сессии содержит правильный сегмент из списка."""
        u1, u2 = make_user(), make_user()
        form = self._make_form(teams=[])
        with patch.object(form, 'get_all_users', return_value=[u1, u2]):
            sessions = form._build_segment_sessions(self.competition, self.segments)

        assigned_segments = [seg for seg, _, _ in sessions[0]]
        self.assertEqual(
            set(s.id for s in assigned_segments),
            set(s.id for s in self.segments)
        )


# ===========================================================================
# 2. Тесты _handle_segment_sessions — создание объектов в БД
# ===========================================================================

class HandleSegmentSessionsTest(TransactionTestCase):
    """Тесты создания TeamCompetition2TeamsAndUsers и TeamOrUser2Segment."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start_pnet_patches()

    @classmethod
    def tearDownClass(cls):
        stop_pnet_patches()
        super().tearDownClass()

    def setUp(self):
        self.lab, self.segments = make_lab(segments_count=2)
        self.competition = make_competition(self.lab)

    def _run_handle(self, teams, solo_users):
        form = TeamCompetitionForm.__new__(TeamCompetitionForm)
        form.cleaned_data = {
            'teams': teams,
            'non_platoon_users': solo_users,
            'platoons': [],
        }
        with patch.object(form, 'get_all_users', return_value=solo_users):
            form._handle_segment_sessions(self.competition, self.segments)

    def test_creates_session_objects(self):
        u1, u2 = make_user(), make_user()
        self._run_handle([], [u1, u2])

        sessions = TeamCompetition2TeamsAndUsers.objects.filter(team_competition=self.competition)
        self.assertEqual(sessions.count(), 1)

    def test_creates_segment_assignments(self):
        u1, u2 = make_user(), make_user()
        self._run_handle([], [u1, u2])

        assignments = TeamOrUser2Segment.objects.filter(team_competition=self.competition)
        self.assertEqual(assignments.count(), 2)

    def test_team_session_creates_assignments(self):
        t1 = make_team(make_user(), make_user())
        t2 = make_team(make_user(), make_user())
        self._run_handle([t1, t2], [])

        session = TeamCompetition2TeamsAndUsers.objects.get(team_competition=self.competition)
        self.assertEqual(session.teams.count(), 2)
        self.assertEqual(
            TeamOrUser2Segment.objects.filter(team_competition=self.competition).count(), 2
        )

    def test_old_sessions_deleted_on_rerun(self):
        """При повторном вызове старые сессии удаляются."""
        u1, u2 = make_user(), make_user()
        self._run_handle([], [u1, u2])
        first_session_id = TeamCompetition2TeamsAndUsers.objects.get(
            team_competition=self.competition
        ).pk

        u3, u4 = make_user(), make_user()
        self._run_handle([], [u3, u4])

        sessions = TeamCompetition2TeamsAndUsers.objects.filter(team_competition=self.competition)
        self.assertEqual(sessions.count(), 1)
        self.assertNotEqual(sessions.first().pk, first_session_id)

    def test_creates_competition2user_for_participants(self):
        """Для каждого участника сессии создаётся Competition2User."""
        u1, u2 = make_user(), make_user()
        task = LabTask.objects.create(lab=self.lab, task_id='T1', description='task')
        self.competition.tasks.add(task)
        self._run_handle([], [u1, u2])

        for user in [u1, u2]:
            self.assertTrue(
                Competition2User.objects.filter(competition=self.competition, user=user).exists(),
                f'Competition2User не создан для {user}'
            )

    def test_no_segments_skips_handle(self):
        """Если сегментов нет — сессии не создаются."""
        lab_no_seg, _ = make_lab(segments_count=0)
        comp = make_competition(lab_no_seg)
        form = TeamCompetitionForm.__new__(TeamCompetitionForm)
        form.cleaned_data = {'teams': [], 'non_platoon_users': [], 'platoons': []}
        with patch.object(form, 'get_all_users', return_value=[]):
            form._handle_segment_sessions(comp, [])

        self.assertEqual(
            TeamCompetition2TeamsAndUsers.objects.filter(team_competition=comp).count(), 0
        )


# ===========================================================================
# 3. Тесты get_issue_for_user — находит правильный issue
# ===========================================================================

class GetIssueForUserSegmentTest(TestCase):
    """get_issue_for_user должен находить TeamCompetition2TeamsAndUsers для участника сегментной сессии."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start_pnet_patches()

    @classmethod
    def tearDownClass(cls):
        stop_pnet_patches()
        super().tearDownClass()

    def setUp(self):
        self.lab, _ = make_lab(segments_count=2)
        self.competition = make_competition(self.lab)
        self.user1 = make_user()
        self.user2 = make_user()
        self.session = TeamCompetition2TeamsAndUsers.objects.create(
            team_competition=self.competition,
        )
        self.session.users.add(self.user1, self.user2)

    def test_finds_segment_session_for_user(self):
        issue, err = get_issue_for_user(self.competition, self.user1)
        self.assertIsNone(err)
        self.assertIsInstance(issue, TeamCompetition2TeamsAndUsers)
        self.assertEqual(issue.pk, self.session.pk)

    def test_finds_segment_session_for_team_member(self):
        u3, u4 = make_user(), make_user()
        team = make_team(u3, u4)
        self.session.teams.add(team)

        issue, err = get_issue_for_user(self.competition, u3)
        self.assertIsNone(err)
        self.assertIsInstance(issue, TeamCompetition2TeamsAndUsers)

    def test_returns_error_for_non_participant(self):
        outsider = make_user()
        issue, err = get_issue_for_user(self.competition, outsider)
        self.assertIsNone(issue)
        self.assertIsNotNone(err)


# ===========================================================================
# 4. Тесты TeamCompetitionDetailView — контекст segment_vm_names
# ===========================================================================

class TeamCompetitionDetailViewSegmentContextTest(TestCase):
    """Проверяем что view передаёт segment_vm_names в контекст."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start_pnet_patches()

    @classmethod
    def tearDownClass(cls):
        stop_pnet_patches()
        super().tearDownClass()

    def setUp(self):
        from django.urls import reverse
        self.reverse = reverse

        self.lab, self.segments = make_lab(segments_count=2)
        self.competition = make_competition(self.lab)
        self.user = make_user()

        TeamOrUser2Segment.objects.create(
            team_competition=self.competition,
            segment=self.segments[0],
            user=self.user,
        )

    def test_segment_vm_names_in_context(self):
        self.client.login(username=self.user.username, password='pass')
        url = self.reverse('interface:team-competition-detail', kwargs={'slug': self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get('segment_vm_names'), self.segments[0].vm_names)

    def test_no_segment_vm_names_when_no_assignment(self):
        other_user = make_user()
        self.client.login(username=other_user.username, password='pass')
        url = self.reverse('interface:team-competition-detail', kwargs={'slug': self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.get('segment_vm_names'), [])

    def test_segment_name_in_context(self):
        self.client.login(username=self.user.username, password='pass')
        url = self.reverse('interface:team-competition-detail', kwargs={'slug': self.competition.slug})
        response = self.client.get(url)
        self.assertEqual(response.context.get('segment_name'), self.segments[0].name)


# ===========================================================================
# 5. Регрессия — лабы БЕЗ сегментов работают как прежде
# ===========================================================================

class RegressionNoSegmentsTest(TransactionTestCase):
    """Убеждаемся что старая логика TeamCompetition2Team не сломана."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        start_pnet_patches()

    @classmethod
    def tearDownClass(cls):
        stop_pnet_patches()
        super().tearDownClass()

    def setUp(self):
        self.lab, _ = make_lab(segments_count=0)
        self.competition = make_competition(self.lab)

    def test_no_segment_sessions_when_empty_segments_list(self):
        """_handle_segment_sessions с пустым списком сегментов не создаёт сессии."""
        form = TeamCompetitionForm.__new__(TeamCompetitionForm)
        form.cleaned_data = {'teams': [], 'non_platoon_users': [], 'platoons': []}
        with patch.object(form, 'get_all_users', return_value=[]):
            form._handle_segment_sessions(self.competition, [])

        self.assertEqual(
            TeamCompetition2TeamsAndUsers.objects.filter(team_competition=self.competition).count(), 0
        )

    def test_team_competition2team_created_for_lab_without_segments(self):
        """Для лабы без сегментов _create_competition_teams вызывается через handle_competition_users."""
        t1 = make_team(make_user(), make_user())

        form = TeamCompetitionForm.__new__(TeamCompetitionForm)
        form.cleaned_data = {
            'teams': [t1],
            'non_platoon_users': [],
            'platoons': [],
            'num_tasks': 0,
        }
        with patch.object(form, 'get_all_users', return_value=[]):
            with patch.object(form, '_get_new_participants', return_value=[]):
                with patch.object(form, '_get_new_teams', return_value=[t1]):
                    with patch.object(form, '_delete_removed_users'):
                        with patch.object(form, '_delete_removed_teams'):
                            with patch('interface.forms.with_pnet_session_if_needed',
                                       side_effect=lambda lab, fn: fn()):
                                with patch.object(form, '_create_competition_teams') as mock_create:
                                    form.handle_competition_users(self.competition)
                                    mock_create.assert_called_once()

    def test_get_issue_for_user_returns_competition2user_no_segments(self):
        """get_issue_for_user для обычной Competition2User работает."""
        u = make_user()
        c2u = Competition2User.objects.create(competition=self.competition, user=u)

        issue, err = get_issue_for_user(self.competition, u)
        self.assertIsNone(err)
        self.assertIsInstance(issue, Competition2User)
        self.assertEqual(issue.pk, c2u.pk)

    def test_teamcompetition2team_issue_returned(self):
        """get_issue_for_user для TeamCompetition2Team работает."""
        u1, u2 = make_user(), make_user()
        team = make_team(u1, u2)
        tc2t = TeamCompetition2Team.objects.create(competition=self.competition, team=team)

        issue, err = get_issue_for_user(self.competition, u1)
        self.assertIsNone(err)
        self.assertIsInstance(issue, TeamCompetition2Team)
        self.assertEqual(issue.pk, tc2t.pk)

