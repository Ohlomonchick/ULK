# Интеграционные e2e тесты (Docker + Nginx + Postgres + Elasticsearch + PNET)

Этот набор тестов проверяет реальную интеграцию:
- Django-приложение в Docker (`web`),
- Nginx в Docker (`nginx`),
- Postgres в отдельном контейнере,
- Elasticsearch (single-node, TLS) в отдельном контейнере,
- внешний PNET (поднят отдельно, например в VirtualBox).

## Что поднимается

Файл: `integration_tests/docker/compose.yml`

Сервисы:
- `postgres` на `localhost:55431`
- `elasticsearch` на `https://localhost:19200` (TLS, `elastic/elastic`)
- `web` (build через Dockerfile со слоем зависимостей + migrate + gunicorn)
- `nginx` на `localhost:18080` (проксирует `/api` в Django и `/pnetlab` в PNET)
- `web` ожидает healthcheck Postgres перед запуском миграций (исключает race condition с БД)

Примечание: первый старт может идти несколько минут, так как `web` контейнер устанавливает зависимости.

Единственный обязательный внешний параметр для compose: `PNET_IP`.

## Ключевые пути

- `integration_tests/conftest.py` — orchestration Docker стека, env, cleanup context
- `integration_tests/utils/db_seed.py` — подготовка тестовых сущностей (Competition/TeamCompetition/KKZ), регистрация cleanup (`register_*_cleanup`)
- `integration_tests/utils/pnet_cleanup.py` — очистка пользователей/директорий/лаб в PNET
- `integration_tests/utils/topology.py` — извлечение nodes/links из ответа PNET topology
- `integration_tests/utils/http_client.py` — helper для логина в Django
- `interface/config.py` — поддержка env override для `PNET_BASE_DIR`, `STUDENT_WORKSPACE`, `WEB_URL`

## Запуск (Linux/WSL)

```bash
export PNET_IP=192.168.0.108
pytest -m integration integration_tests/test_*_e2e.py -v
```

Для browser-level сценариев (`test_frontend_iframe_playwright_e2e.py`) нужен браузер Playwright:

```bash
playwright install chromium
```

или:

```bash
chmod +x integration_tests/run_e2e.sh
integration_tests/run_e2e.sh
```

## Запуск (Windows PowerShell)

```powershell
$env:PNET_IP="192.168.0.108"
pytest -m integration integration_tests/test_*_e2e.py -v
```

Для browser-level сценариев:

```powershell
playwright install chromium
```

или:

```powershell
.\integration_tests\run_e2e.ps1 -PnetIp 192.168.0.108
```

Скрипт поднимает стек (`compose up -d`), ждёт готовности, затем запускает pytest **внутри контейнера web** (`compose exec web pytest ...`), чтобы один прогон покрывал и e2e, и тесты Gunicorn в том же окружении, что и приложение (сеть между контейнерами: nginx, elasticsearch по имени сервиса).

Скрипты запуска включают live-вывод (`-s --log-cli-level=INFO`), поэтому во время прогона видно, где именно выполняется тест.

Дополнительно для каждого теста создается отдельный файл:
- `integration_tests/logs/<run_id>/<timestamp>_<nodeid>.log`

Это упрощает разбор падений и долгих сценариев.

## Elasticsearch сертификаты

При запуске `integration_stack` сертификаты для Elasticsearch генерируются автоматически, если их нет в `integration_tests/docker/certs/`.

Генерация делается через одноразовые Linux-контейнеры (`docker run`) с утилитами:
- `elasticsearch-certutil` для `ca.p12` и `elasticsearch.p12`,
- `openssl` для конвертации в `ca.crt`, `elasticsearch.crt`, `elasticsearch.key`.

Сертификаты монтируются в `elasticsearch` контейнер и доступны приложению в `web` через путь репозитория (`/app/integration_tests/docker/certs/...`).

## Маркеры pytest

- `integration` — интеграционный контур
- `docker` — требует docker compose
- `pnet` — требует доступ к PNET
- `slow` — длительные проверки

## Что покрывается сценариями

- создание пользователей и смена паролей + проверка workspace директорий;
- создание сценариев соревнований через `SimpleCompetitionForm` (взвод/команда) и наличие лаб на каждого участника;
- проверка смены workspace у командных участников и возврата после удаления;
- аутентификация в PNET через ручку приложения поверх Nginx;
- создание сессии лабы через ручку, проверка `session_id` через `get_session_id()` и filter-flow;
- KKZ: множественные лабы для каждого пользователя + выборочная проверка топологии.
- усложненная topology-конфигурация (`docker` + `vpcs`) в целевых топологических e2e;
- browser e2e через Playwright: проверка iframe для PN/CMD и PZ-admin flow;
- конкурентные POST `/api/create_pnet_lab_session/` с проверкой распределения по gunicorn воркерам;
- team shared-session: включение ноды одним участником и видимость состояния у другого;
- отображение засчитанных по API заданий: студент видит зачёт в списке заданий и счётчике на competition_detail, админ — в таблице решений (с ожиданием анимации);
- тесты Gunicorn (`integration_tests/gunicorn/`): нумерация воркеров, стабильность после перезапусков — выполняются **внутри контейнера** при полном прогоне `run_e2e.ps1` (без skip на Windows).

## Очистка побочных эффектов

Cleanup выполняется в fixture `cleanup_context` после каждого теста:
- удаление созданных лаб (`delete_lab_with_session_destroy`);
- удаление тестовых пользователей PNET (`delete_user`);
- удаление тестовых директорий (`delete_folder`);
- удаление seed-сущностей в Postgres по тестовому префиксу.

**По умолчанию** очистка выполняется всегда (и при успехе, и при падении теста).

Опция **`--keep-pnet-on-fail`**: если передан этот аргумент и тест **упал**, очистка PNET и БД для этого теста **не выполняется** — артефакты остаются для разбора. При успешном прохождении теста очистка выполняется как обычно.

Примеры (оставить артефакты при падении):
```bash
pytest -m integration integration_tests/test_*_e2e.py -v --keep-pnet-on-fail
```
Через скрипт PowerShell (все интеграционные тесты, включая gunicorn, запускаются одним pytest внутри контейнера):
```powershell
.\integration_tests\run_e2e.ps1 -PnetIp 192.168.1.11 -KeepPnetOnFail
.\integration_tests\run_e2e.ps1 -PnetIp 192.168.1.11 -Test "test_team_shared_session_e2e.py::test_team_shared_session_propagates_node_state_between_users" -KeepPnetOnFail
# Удаление лаб PNET через час после окончания соревнования (management-скрипт):
.\integration_tests\run_e2e.ps1 -PnetIp 192.168.1.11 -Test "test_pnet_lab_cleanup_after_competition_end_e2e.py::test_pnet_labs_removed_by_management_job_one_hour_after_competition_end"
# Только тесты Gunicorn (так же через -Test):
.\integration_tests\run_e2e.ps1 -PnetIp 192.168.1.11 -Test "gunicorn/test_gunicorn_conf.py"
.\integration_tests\run_e2e.ps1 -PnetIp 192.168.1.11 -Test "gunicorn/test_gunicorn_conf.py::test_worker_numbering"
```

Для каждого прогона лабы и папки пользователей создаются под базовым воркспейсом Student в PNET (`/Practice Work/Test_Labs`):
- `STUDENT_WORKSPACE=Practice Work/Test_Labs`
- `PNET_BASE_DIR=/Practice Work/Test_Labs/IT_TestLabs/it_<timestamp>`
Воркспейс пользователя в PNET задаётся относительно `STUDENT_WORKSPACE`: `/IT_TestLabs/it_<timestamp>/<username>`.

