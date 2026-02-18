"""
E2E: засчитанные по API задания отображаются студенту на competition_detail
и корректно видны администратору в таблице решений (с учётом анимации).
"""

import logging
import time

import pytest

from integration_tests.utils.playwright_utils import (
    activate_competition_now as _activate_competition_now,
    launch_browser_or_skip as _launch_browser_or_skip,
    login_in_ui as _login_in_ui,
)

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.pnet, pytest.mark.docker, pytest.mark.slow]


def test_credited_tasks_visible_on_competition_detail_student_and_admin(
    django_ready, integration_stack, cleanup_context
):
    """
    Засчитанные по API задания отображаются студенту в списке заданий и в счётчике,
    а администратору — в таблице решений на competition_detail (с ожиданием анимации).
    """
    from integration_tests.utils.db_seed import (
        INTEGRATION_TEST_PASSWORD,
        register_competition_cleanup,
        seed_competition_scenario,
    )
    from integration_tests.utils.http_client import login_to_django

    prefix = f"it-credited-{int(time.time())}"
    scenario = seed_competition_scenario(
        prefix, users_count=2, make_first_user_superuser=True
    )
    _activate_competition_now(scenario.competition)
    register_competition_cleanup(cleanup_context, prefix, scenario)

    # Задания с вопросом и ответом для проверки через API
    task_one = scenario.tasks[0]
    task_one.question = "What is the first answer?"
    task_one.answer = "answer1"
    task_one.save(update_fields=["question", "answer"])

    admin_user = scenario.users[0]
    student_user = scenario.users[1]
    base_url = integration_stack["base_url"]
    total_tasks = len(scenario.tasks)

    # 1) Засчитываем задание студенту через API
    # login_to_django использует /accounts/login/ (принимает любого пользователя),
    # а не student-форму на "/", которая ищет по last_name + "_" + first_name —
    # такой username не совпадает с тестовыми пользователями db_seed.
    student_session = login_to_django(
        base_url,
        username=student_user.username,
        password=INTEGRATION_TEST_PASSWORD,
    )
    check_response = student_session.post(
        f"{base_url}/api/check_task_answers/",
        json={
            "competition_slug": scenario.competition.slug,
            "answers": {str(task_one.id): "answer1"},
        },
        headers={"X-CSRFToken": student_session.cookies.get("csrftoken", "")},
        timeout=10,
    )
    assert check_response.status_code == 200, check_response.text
    data = check_response.json()
    assert data.get("success") is True
    assert data.get("results", {}).get(str(task_one.id), {}).get("status") == "correct"

    # 2) Студент открывает competition_detail — должен видеть зачёт и обновлённый счётчик
    pw, browser = _launch_browser_or_skip()
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()
    try:
        _login_in_ui(
            page,
            base_url,
            INTEGRATION_TEST_PASSWORD,
            admin_login=False,
            username=student_user.username,
            first_name=student_user.first_name,
            last_name=student_user.last_name,
            platoon_id=student_user.platoon_id,
        )
        page.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        page.wait_for_selector("#tasks-list-box", timeout=15000)
        # Счётчик: 1/N
        page.wait_for_selector(
            "#tasks-completion-counter .completed-count:has-text('1')",
            timeout=10000,
        )
        page.wait_for_selector(
            f"#tasks-completion-counter .total-count:has-text('{total_tasks}')",
            timeout=5000,
        )
        # В списке заданий — тег "Выполнено" у первого задания
        done_tag = page.locator(
            f".task-item[data-task-id='{task_one.id}'] .task-status-tag .tag.is-success"
        )
        done_tag.wait_for(state="visible", timeout=10000)
        assert "Выполнено" in (done_tag.text_content() or "")
    finally:
        context.close()
        browser.close()
        pw.stop()

    # 3) Админ открывает competition_detail — в таблице решений виден прогресс студента
    pw2, browser2 = _launch_browser_or_skip()
    context2 = browser2.new_context(ignore_https_errors=True)
    page2 = context2.new_page()
    try:
        _login_in_ui(
            page2,
            base_url,
            INTEGRATION_TEST_PASSWORD,
            admin_login=True,
            username=admin_user.username,
        )
        page2.goto(
            f"{base_url}/cyberpolygon/competitions/{scenario.competition.slug}/",
            wait_until="domcontentloaded",
        )
        page2.wait_for_selector("#solutions-container", timeout=15000)
        # Таблица подгружается через get_competition_solutions; ждём строку с прогрессом 1/N
        progress_cell = page2.locator("#solutions-table td").filter(has_text="1/")
        progress_cell.wait_for(state="visible", timeout=15000)
        # Ожидание анимации Flip (duration 2s в solutions_table.js)
        page2.wait_for_timeout(2500)
        # Проверяем, что в таблице есть ячейка с прогрессом 1/total_tasks
        table_text = page2.locator("#solutions-table").inner_text()
        assert f"1/{total_tasks}" in table_text, f"Expected '1/{total_tasks}' in table: {table_text}"
    finally:
        context2.close()
        browser2.close()
        pw2.stop()
