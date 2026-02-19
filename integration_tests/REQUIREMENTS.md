# Библиотеки, используемые в интеграционных тестах

Все перечисленные пакеты реально импортируются или вызываются в коде `integration_tests/`. Продакшен-зависимости подключаются через `-r requirements.txt` в корневом `requirements-test.txt`.

## Установка

```bash
pip install -r requirements-test.txt
```

Для e2e-тестов с браузером после установки выполните:

```bash
playwright install chromium
```

---

## Список библиотек

### Pytest и плагины

| Пакет       | Версия (prod) | Где используется |
|------------|----------------|------------------|
| pytest     | 8.3.5          | Все тесты, `conftest.py` (фикстуры, хуки `pytest_addoption`, `pytest_runtest_makereport`, `pytest_runtest_setup`/`teardown`), маркеры `@pytest.mark.integration`, `pytest.skip`/`fail`, `playwright_utils` (`importorskip`) |
| pytest-cov | 6.1.1          | Покрытие кода при запуске с `--cov` |
| coverage   | 7.8.0          | Движок отчётов покрытия |

### HTTP и сеть

| Пакет    | Версия (prod) | Где используется |
|----------|----------------|------------------|
| requests | 2.31.0        | `conftest.py` (ожидание готовности стека, логи), `utils/http_client.py` (логин, сессии), `utils/pnet_dirs.py` (создание папок в PNET), `gunicorn/test_gunicorn_conf.py` (запросы к воркерам) |
| urllib3  | 2.2.1         | `gunicorn/test_gunicorn_conf.py` — `urllib3.util.retry.Retry` для повторных запросов |

### Django

| Пакет  | Версия (prod) | Где используется |
|--------|----------------|------------------|
| Django | 5.0.3         | `conftest.py` (`django.setup()`), `utils/db_seed.py` (`django.utils.timezone`, формы, модели), `utils/playwright_utils.py` (`django.utils.timezone`), `test_concurrent_two_competitions_form_e2e.py`, `test_concurrent_lab_sessions_e2e.py` (`django.core.management.call_command`), `test_pnet_lab_cleanup_after_competition_end_e2e.py` (`django.utils.timezone`) |

### E2E (браузер)

| Пакет     | Версия      | Где используется |
|-----------|-------------|------------------|
| playwright | ≥1.49.0,<3 | `utils/playwright_utils.py` (`playwright.sync_api`), `test_frontend_iframe_playwright_e2e.py`, `test_competition_detail_credited_tasks_e2e.py`. Тесты помечают отсутствие пакета через `importorskip` и пропускают запуск. |

---

## Зависимости из requirements.txt (уже включены через -r)

Указанные выше пакеты тянют за собой (из prod): `attrs`, `iniconfig`, `pluggy` (pytest), `certifi`, `charset-normalizer`, `idna` (requests), `asgiref`, `sqlparse` (Django) и остальные зависимости приложения, нужные для импорта `interface.*` и `dynamic_config.*` в тестах.

## Опциональные (в requirements-test.txt не входят)

- **pytest-timeout** — таймауты на тест (`@pytest.mark.timeout(60)`).
- **pytest-xdist** — параллельный запуск (`-n auto`).
- **psutil** / **pytest-xprocess** — управление процессами (в текущих тестах не используются).
