"""Seed helpers for integration tests running against Postgres + real PNET."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from interface.forms import CompetitionForm, SimpleKkzForm, TeamCompetitionForm
from interface.models import (
    Kkz,
    Competition,
    Competition2User,
    Lab,
    LabLevel,
    LabTask,
    LabType,
    Platoon,
    Team,
    TeamCompetition,
    TeamCompetition2Team,
    User,
)
from interface.utils import get_pnet_lab_name


def _ensure_participant_dirs(names: list[str]) -> None:
    """
    Создает директории участников в PNET до запуска form.save(),
    чтобы create_lab не падал с parent folder does not exist (60018).
    """
    if not names:
        return

    from interface.config import get_pnet_base_dir
    from interface.pnet_session_manager import ensure_admin_pnet_session
    from integration_tests.utils.pnet_dirs import ensure_directory_path

    base_dir = get_pnet_base_dir()
    session = ensure_admin_pnet_session()
    with session:
        pnet_url, cookie, _ = session.session_data
        ensure_directory_path(pnet_url, cookie, base_dir)
        for name in names:
            if name:
                ensure_directory_path(pnet_url, cookie, f"{base_dir}/{name}")


def _ensure_pnet_base_dir() -> None:
    """Создаёт только базовый путь в PNET (без поддиректорий пользователей)."""
    from interface.config import get_pnet_base_dir
    from interface.pnet_session_manager import ensure_admin_pnet_session
    from integration_tests.utils.pnet_dirs import ensure_directory_path

    base_dir = get_pnet_base_dir()
    session = ensure_admin_pnet_session()
    with session:
        pnet_url, cookie, _ = session.session_data
        ensure_directory_path(pnet_url, cookie, base_dir)


def _build_nodes_data():
    return [
        {
            "cpu": 1,
            "ram": 1024,
            "top": 240,
            "icon": "linux-1.png",
            "left": 220,
            "name": "node-a",
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
            "description": "Linux node A",
            "map_port_2nd": "",
            "qemu_options": "-machine type=pc,accel=kvm -vga virtio",
            "qemu_version": "4.1.0",
            "config_script": "",
            "script_timeout": 1200,
        },
        {
            "cpu": 1,
            "ram": 1024,
            "top": 360,
            "icon": "linux-1.png",
            "left": 460,
            "name": "node-b",
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
            "description": "Linux node B",
            "map_port_2nd": "",
            "qemu_options": "-machine type=pc,accel=kvm -vga virtio",
            "qemu_version": "4.1.0",
            "config_script": "",
            "script_timeout": 1200,
        },
    ]


def build_complex_topology_data() -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """
    Топология для интеграционных тестов с несколькими узлами на docker/vpcs.

    Формат полей сохраняем совместимым с тем, что ожидают API создания нод в PNET.
    """
    nodes_data = [
        {
            "cpu": 1,
            "ram": 512,
            "top": 220,
            "icon": "Server.png",
            "left": 220,
            "name": "sender",
            "size": "",
            "type": "docker",
            "count": "1",
            "delay": 0,
            "image": "pnetlab/ubuntu_sv:latest",
            "config": 0,
            "console": "ssh",
            "postfix": 0,
            "ethernet": 1,
            "template": "docker",
            "username": "",
            "password": "",
            "map_port": "",
            "console_2nd": "",
            "map_port_2nd": "",
            "config_script": "config_docker.py",
            "docker_options": "--privileged",
        },
        {
            "cpu": 1,
            "ram": 512,
            "top": 220,
            "icon": "Server.png",
            "left": 430,
            "name": "attacker",
            "size": "",
            "type": "docker",
            "count": "1",
            "delay": 0,
            "image": "pnetlab/ubuntu_sv:latest",
            "config": 0,
            "console": "ssh",
            "postfix": 0,
            "ethernet": 1,
            "template": "docker",
            "username": "",
            "password": "",
            "map_port": "",
            "console_2nd": "",
            "map_port_2nd": "",
            "config_script": "config_docker.py",
            "docker_options": "--privileged",
        },
        {
            "cpu": 1,
            "ram": 512,
            "top": 420,
            "icon": "Server.png",
            "left": 325,
            "name": "receiver",
            "size": "",
            "type": "docker",
            "count": "1",
            "delay": 0,
            "image": "pnetlab/ubuntu_sv:latest",
            "config": 0,
            "console": "ssh",
            "postfix": 0,
            "ethernet": 1,
            "template": "docker",
            "username": "",
            "password": "",
            "map_port": "",
            "console_2nd": "",
            "map_port_2nd": "",
            "config_script": "config_docker.py",
            "docker_options": "--privileged",
        },
        {
            "template": "vpcs",
            "type": "vpcs",
            "name": "vpc-router",
            "icon": "Desktop.png",
            "ethernet": 4,
            "mtu": 9000,
            "ram": 128,
            "config": 0,
            "delay": 0,
            "size": "",
            "left": 325,
            "top": 320,
            "count": "1",
            "postfix": 0,
        },
    ]
    # Для стабильности прогона в текущем тестовом контуре используем "мягкие" заготовки:
    # PNET корректно обрабатывает их, а фактические связи проверяются по topology API.
    connectors_data = [{}]
    connectors2cloud_data = [{}]
    networks_data = [{}]
    return nodes_data, connectors_data, connectors2cloud_data, networks_data


def create_lab_with_level_and_tasks(prefix: str, *, lab_type: str = LabType.COMPETITION) -> tuple[Lab, LabLevel, list[LabTask]]:
    return create_lab_with_level_and_tasks_overrides(prefix, lab_type=lab_type)


def create_lab_with_level_and_tasks_overrides(
    prefix: str,
    *,
    lab_type: str = LabType.COMPETITION,
    platform: str = "PN",
    nodes_data_override: list[dict] | None = None,
    connectors_data_override: list[dict] | None = None,
    connectors2cloud_data_override: list[dict] | None = None,
    networks_data_override: list[dict] | None = None,
) -> tuple[Lab, LabLevel, list[LabTask]]:
    nodes_data = nodes_data_override if nodes_data_override is not None else _build_nodes_data()
    connectors_data = connectors_data_override if connectors_data_override is not None else []
    connectors2cloud_data = (
        connectors2cloud_data_override if connectors2cloud_data_override is not None else []
    )
    networks_data = networks_data_override if networks_data_override is not None else []

    lab = Lab.objects.create(
        name=f"{prefix}-lab-{lab_type.lower()}",
        description=f"Integration lab {prefix}",
        platform=platform,
        program="COMPETITION",
        lab_type=lab_type,
        learning_years=[1],
        NodesData=nodes_data,
        ConnectorsData=connectors_data,
        Connectors2CloudData=connectors2cloud_data,
        NetworksData=networks_data,
    )
    level = LabLevel.objects.create(lab=lab, level_number=1, description="L1")
    tasks = [
        LabTask.objects.create(lab=lab, task_id="1", description="Task one"),
        LabTask.objects.create(lab=lab, task_id="2", description="Task two"),
        LabTask.objects.create(lab=lab, task_id="3", description="Task three", dependencies="1"),
    ]
    return lab, level, tasks


INTEGRATION_TEST_PASSWORD = "Passw0rd!123"


def create_platoon_with_users(prefix: str, users_count: int = 3) -> tuple[Platoon, list[User]]:
    """
    Создаёт взвод и пользователей через CustomUserCreationForm:
    Django-пользователь, директория в PNET и пользователь PNET создаются формой.
    """
    from interface.forms import CustomUserCreationForm

    _ensure_pnet_base_dir()
    platoon = Platoon.objects.create(number=int(timezone.now().timestamp()) % 100000, learning_year=1)
    users: list[User] = []
    for idx in range(users_count):
        form = CustomUserCreationForm(
            data={
                "username": f"{prefix}-student-{idx}",
                "first_name": f"Student{idx}",
                "last_name": "Integration",
                "platoon": platoon.pk,
                "password1": INTEGRATION_TEST_PASSWORD,
                "password2": INTEGRATION_TEST_PASSWORD,
            }
        )
        if not form.is_valid():
            raise AssertionError(f"CustomUserCreationForm invalid for {prefix}-student-{idx}: {form.errors}")
        user = form.save()
        users.append(user)
    return platoon, users


@dataclass
class CompetitionScenario:
    competition: Competition
    users: list[User]
    lab: Lab
    tasks: list[LabTask]


def seed_competition_scenario(
    prefix: str,
    users_count: int = 3,
    *,
    lab_type: str = LabType.COMPETITION,
    platform: str = "PN",
    nodes_data_override: list[dict] | None = None,
    connectors_data_override: list[dict] | None = None,
    connectors2cloud_data_override: list[dict] | None = None,
    networks_data_override: list[dict] | None = None,
) -> CompetitionScenario:
    from interface.pnet_session_manager import reset_admin_pnet_session

    reset_admin_pnet_session()
    lab, level, tasks = create_lab_with_level_and_tasks_overrides(
        prefix,
        lab_type=lab_type,
        platform=platform,
        nodes_data_override=nodes_data_override,
        connectors_data_override=connectors_data_override,
        connectors2cloud_data_override=connectors2cloud_data_override,
        networks_data_override=networks_data_override,
    )
    platoon, users = create_platoon_with_users(prefix, users_count=users_count)

    form = CompetitionForm(
        data={
            "start": timezone.now() + timedelta(minutes=5),
            "finish": timezone.now() + timedelta(hours=2),
            "lab": lab.pk,
            "level": level.pk,
            "platoons": [platoon.pk],
            "tasks": [task.pk for task in tasks],
            "num_tasks": 2,
            "non_platoon_users": [],
        }
    )
    if not form.is_valid():
        raise AssertionError(f"CompetitionForm is invalid: {form.errors}")
    competition = form.save()
    return CompetitionScenario(competition=competition, users=users, lab=lab, tasks=tasks)


@dataclass
class TeamCompetitionScenario:
    competition: TeamCompetition
    team: Team
    team_users: list[User]
    lab: Lab


def seed_team_competition_scenario(prefix: str, team_size: int = 2) -> TeamCompetitionScenario:
    from interface.pnet_session_manager import reset_admin_pnet_session

    reset_admin_pnet_session()
    lab, level, tasks = create_lab_with_level_and_tasks(prefix, lab_type=LabType.COMPETITION)
    team = Team.objects.create(name=f"{prefix}-team", slug=f"{prefix}-team")
    _, team_users = create_platoon_with_users(f"{prefix}-team", users_count=team_size)
    team.users.set(team_users)
    _ensure_participant_dirs([team.slug])

    form = TeamCompetitionForm(
        data={
            "start": timezone.now() + timedelta(minutes=5),
            "finish": timezone.now() + timedelta(hours=2),
            "lab": lab.pk,
            "level": level.pk,
            "platoons": [],
            "teams": [team.pk],
            "tasks": [task.pk for task in tasks],
            "num_tasks": 2,
            "non_platoon_users": [],
        }
    )
    if not form.is_valid():
        raise AssertionError(f"TeamCompetitionForm is invalid: {form.errors}")
    competition = form.save()
    return TeamCompetitionScenario(competition=competition, team=team, team_users=team_users, lab=lab)


@dataclass
class KkzScenario:
    kkz: Kkz
    users: list[User]
    labs: list[Lab]


def seed_kkz_scenario(
    prefix: str,
    users_count: int = 3,
    labs_count: int = 2,
    *,
    platform: str = "PN",
    nodes_data_override: list[dict] | None = None,
    connectors_data_override: list[dict] | None = None,
    connectors2cloud_data_override: list[dict] | None = None,
    networks_data_override: list[dict] | None = None,
) -> KkzScenario:
    from interface.pnet_session_manager import reset_admin_pnet_session

    reset_admin_pnet_session()
    platoon, users = create_platoon_with_users(f"{prefix}-kkz", users_count=users_count)
    labs: list[Lab] = []
    labs_data = []

    for idx in range(labs_count):
        lab, _, tasks = create_lab_with_level_and_tasks_overrides(
            f"{prefix}-kkz-{idx}",
            lab_type=LabType.EXAM,
            platform=platform,
            nodes_data_override=nodes_data_override,
            connectors_data_override=connectors_data_override,
            connectors2cloud_data_override=connectors2cloud_data_override,
            networks_data_override=networks_data_override,
        )
        labs.append(lab)
        labs_data.append(
            {
                "lab_id": lab.id,
                "name": lab.name,
                "included": True,
                "task_ids": [task.id for task in tasks],
                "num_tasks": 2,
                "max_tasks_limit": None,
            }
        )

    form = SimpleKkzForm(
        data={
            "name": f"{prefix}-kkz",
            "platoon": platoon.pk,
            "duration_0": "0",
            "duration_1": "2",
            "duration_2": "0",
            "unified_tasks": False,
            "labs_data": json.dumps(labs_data),
        }
    )
    if not form.is_valid():
        raise AssertionError(f"SimpleKkzForm is invalid: {form.errors}")

    kkz = form.create_kkz()
    return KkzScenario(kkz=kkz, users=users, labs=labs)


def collect_lab_pairs_for_competition(competition: Competition) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    lab_name = get_pnet_lab_name(competition)
    for issue in Competition2User.objects.filter(competition=competition):
        pairs.append((lab_name, issue.user.pnet_login))
    return pairs


def collect_lab_pairs_for_team_competition(competition: TeamCompetition) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    lab_name = get_pnet_lab_name(competition)
    for issue in TeamCompetition2Team.objects.filter(competition=competition):
        pairs.append((lab_name, issue.team.slug))
    return pairs


def register_competition_cleanup(
    cleanup_context: dict,
    prefix: str,
    scenario: CompetitionScenario,
) -> None:
    """Регистрирует в cleanup_context пользователей, лабы и префикс БД для сценария Competition."""
    cleanup_context["prefixes_for_db"].add(prefix)
    cleanup_context["users"].update(u.pnet_login for u in scenario.users)
    cleanup_context["labs"].extend(collect_lab_pairs_for_competition(scenario.competition))


def register_team_competition_cleanup(
    cleanup_context: dict,
    prefix: str,
    scenario: TeamCompetitionScenario,
) -> None:
    """Регистрирует в cleanup_context пользователей, лабы и префикс БД для TeamCompetition."""
    cleanup_context["prefixes_for_db"].add(prefix)
    cleanup_context["users"].update(u.pnet_login for u in scenario.team_users)
    cleanup_context["labs"].extend(collect_lab_pairs_for_team_competition(scenario.competition))


def register_kkz_cleanup(
    cleanup_context: dict,
    prefix: str,
    scenario: KkzScenario,
) -> None:
    """Регистрирует в cleanup_context пользователей, лабы и префикс БД для KKZ."""
    cleanup_context["prefixes_for_db"].add(prefix)
    cleanup_context["users"].update(u.pnet_login for u in scenario.users)
    for competition in scenario.kkz.competitions.all():
        lab_name = get_pnet_lab_name(competition)
        for user in scenario.users:
            cleanup_context["labs"].append((lab_name, user.pnet_login))


def cleanup_seeded_entities(prefix: str) -> None:
    """
    Удаляет сущности интеграционного прогона по префиксу.
    PNET side-effects обрабатываются модельными delete() вызовами.
    """
    TeamCompetition.objects.filter(lab__name__startswith=prefix).delete()
    Competition.objects.filter(lab__name__startswith=prefix).delete()
    Kkz.objects.filter(name__startswith=prefix).delete()
    Team.objects.filter(name__startswith=prefix).delete()
    User.objects.filter(username__startswith=prefix).delete()
    Lab.objects.filter(name__startswith=prefix).delete()
