"""
E2E: удаление лаб в PNET management-скриптом (delete_labs_job) через час после окончания
соревнования. Время моделируется сдвигом finish в прошлое; джоба вызывается вручную
(в проде она запускается по расписанию через APScheduler, стартуемый systemctl в контейнере).
"""

import time

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def test_pnet_labs_removed_by_management_job_one_hour_after_competition_end(
    django_ready, integration_stack, integration_env, pnet_admin_session, cleanup_context
):
    """
    Проверка удаления из PNET лаб management-скриптом (delete_labs_job) через час после
    конца времени соревнования. Время моделируется ручной установкой start/finish в прошлое;
    джоба вызывается напрямую (эквивалент одного срабатывания планировщика, запускаемого
    в проде через systemctl start внутри контейнера).
    """
    from datetime import timedelta
    from django.utils import timezone
    from interface.models import Competition, Competition2User
    from interface.utils import get_pnet_lab_name
    from interface.management.commands.runapscheduler import delete_labs_job
    from integration_tests.utils.db_seed import seed_competition_scenario
    from integration_tests.utils.pnet_cleanup import folder_contains_lab_file

    prefix = f"it-cleanup-{int(time.time())}"
    scenario = seed_competition_scenario(prefix, users_count=1)

    # Регистрируем только пользователей и префикс БД: лабы удалит джоба, в teardown не трогаем их
    cleanup_context["prefixes_for_db"].add(prefix)
    cleanup_context["users"].update(u.pnet_login for u in scenario.users)

    pnet_url = pnet_admin_session["pnet_url"]
    cookie = pnet_admin_session["cookie"]
    base_dir = integration_env["PNET_BASE_DIR"]
    pnet_lab_name = get_pnet_lab_name(scenario.competition)
    user = scenario.users[0]
    user_path = f"{base_dir}/{user.pnet_login}"

    # До сдвига времени лаба должна быть в PNET
    assert folder_contains_lab_file(pnet_url, cookie, user_path, pnet_lab_name), (
        "Lab must exist in PNET before running cleanup job"
    )

    # Моделируем ситуацию «прошёл час после окончания»: сдвигаем start/finish в прошлое
    # (delete_labs_job выбирает записи с competition.finish <= now - 1h)
    now = timezone.now()
    past_start = now - timedelta(hours=3)
    past_finish = now - timedelta(hours=2)
    Competition.objects.filter(pk=scenario.competition.pk).update(start=past_start, finish=past_finish)
    scenario.competition.refresh_from_db(fields=["start", "finish"])

    # Однократный запуск джобы (в проде — по расписанию через systemctl start планировщика)
    delete_labs_job()

    # Лаба удалена из PNET у пользователя
    assert not folder_contains_lab_file(pnet_url, cookie, user_path, pnet_lab_name), (
        "Lab must be removed from PNET by delete_labs_job"
    )

    # Соревнование и задания помечены удалёнными
    scenario.competition.refresh_from_db(fields=["deleted"])
    assert scenario.competition.deleted, "Competition must be marked deleted"
    c2u_deleted = list(
        Competition2User.objects.filter(competition=scenario.competition).values_list("deleted", flat=True)
    )
    assert all(c2u_deleted), "All Competition2User must be marked deleted"
