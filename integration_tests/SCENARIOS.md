# Сценарии интеграционных e2e-тестов

Документ описывает сценарии интеграционного контура тестирования системы Cyberpolygon в связке с внешним PNET, Nginx, PostgreSQL и Elasticsearch. Тесты выполняются в окружении Docker-стека и проверяют сквозные потоки от веб-приложения до файловой структуры и API PNET.

---

## 1. Контур и предпосылки

**Контур:** маркировка `integration`, `docker`, `pnet`, при необходимости `slow`. Запуск: `pytest -m integration integration_tests/test_*_e2e.py`.

**Стек:** Django (контейнер `web`), Nginx на порту 18080 (проксирование `/api` в Django, `/pnetlab` в PNET), PostgreSQL, Elasticsearch (TLS), внешний PNET (параметр `PNET_IP`).

**Очистка:** фикстура `cleanup_context` собирает созданных пользователей, папки, лабы и префиксы сущностей в БД; в teardown выполняется удаление лаб, пользователей PNET, папок и очистка seed-сущностей по префиксу. По умолчанию очистка выполняется всегда. При передаче `--keep-pnet-on-fail` очистка не выполняется только для **упавших** тестов (артефакты остаются для разбора). Базовый воркспейс в PNET: `STUDENT_WORKSPACE=Practice Work/Test_Labs`, каталог прогона: `PNET_BASE_DIR=/Practice Work/Test_Labs/IT_TestLabs/it_<timestamp>`.

---

## 2. Жизненный цикл пользователя и структура воркспейса

**Цель:** убедиться, что создание пользователя через форму и смена пароля приводят к появлению корректной структуры директорий в PNET и к возможности входа с новым паролем.

**Сценарий:**
- Создание пользователя через `CustomUserCreationForm` (username, platoon, пароль). Проверяется валидность формы и установка `pnet_login` (slug от username).
- Путь воркспейса пользователя в PNET: `{PNET_BASE_DIR}/{pnet_login}`. Этот путь регистрируется в `cleanup_context` для последующего удаления папки и пользователя.
- Смена пароля через `change_user_password` (PNET API) с использованием административной сессии. Проверяется успешный HTTP-ответ (2xx/3xx).
- Вход пользователя в PNET с новым паролем через `login_user_to_pnet` — сессия должна быть получена.
- Запрос параметров пользователя в PNET (`get_user_params`): проверяется наличие `user_workspace` и окончание пути на `{pnet_login}`.
- Запрос списка папок по полному пути воркспейса (`get_folders`): ответ не должен быть 404; тем самым проверяется, что форма при создании пользователя создала директорию (через `create_directory`).

**Файл:** `test_user_lifecycle_e2e.py::test_user_create_password_change_and_workspace_dirs`.

---

## 3. Создание лаб в рамках мероприятия (Competition / TeamCompetition)

**Цель:** проверить, что при создании сценария мероприятия через `SimpleCompetitionForm` для каждого участника (взвода или команды) в PNET создаётся лаба и соблюдается ожидаемая структура директорий. Соревнование создаётся сразу в статусе «идёт» (start=now), без отдельного запуска.

### 3.1. Соревнование по взводам (SimpleCompetitionForm)

**Сценарий:**
- Подготовка сценария через `seed_competition_scenario(prefix, users_count=3)`: создаётся лаба (тип EXAM) с уровнями и заданиями, взвод, пользователи через `CustomUserCreationForm`, затем заполняется и сохраняется `SimpleCompetitionForm` (duration, level, tasks); форма внутри создаёт Competition через `CompetitionForm`. Валидность проверяется перед `form.create_competition()`.
- Для каждого пользователя из сценария проверяется наличие файла лабы в его директории в PNET: путь пользователя `{PNET_BASE_DIR}/{pnet_login}`, имя лабы — `get_pnet_lab_name(competition)`. Используется `folder_contains_lab_file(pnet_url, cookie, user_path, pnet_lab_name)` (поиск `{lab_name}.unl` в ответе `get_folders` по пути).
- Лабы и пользователи регистрируются в `cleanup_context` для удаления после теста.

**Файл:** `test_competition_lab_provisioning_e2e.py::test_competition_form_creates_lab_for_each_user`.

### 3.2. Командное соревнование (SimpleCompetitionForm) и смена воркспейса

**Цель:** убедиться, что при создании командного мероприятия воркспейс участников команды переключается на командную директорию (slug команды), а после удаления мероприятия возвращается к персональному воркспейсу.

**Сценарий:**
- Подготовка через `seed_team_competition_scenario(prefix, team_size=2)`: лаба (тип COMPETITION), команда, пользователи команды, сохранение через `SimpleCompetitionForm` (duration, level, tasks, teams) с привязкой к команде.
- Для каждого участника команды запрашивается текущий воркспейс в PNET (`get_user_workspace` по `get_user_params`). Проверяется, что путь заканчивается на `/{team.slug}`.
- Выполняется `scenario.competition.delete()`.
- Для каждого участника снова запрашивается воркспейс. Проверяется, что путь заканчивается на `/{pnet_login}` и содержит базовый относительный путь воркспейса (`get_user_workspace_relative_path`), т.е. воркспейс вернулся к персональному.

**Файл:** `test_competition_lab_provisioning_e2e.py::test_team_workspace_switch_and_restore_on_delete`.

---

## 4. Соответствие топологии лабы конфигурации и отсутствие дубликатов

**Цель:** проверить, что развёрнутая в PNET топология созданной лабы совпадает с заданной в конфигурации лабы (набор узлов) и не содержит дубликатов узлов и связей.

**Сценарий:**
- Создаётся сценарий соревнования с одним пользователем (`seed_competition_scenario(prefix, users_count=1)`). Пользователь логинится в Django через Nginx (`login_to_django`), получает PNET-аутентификацию (`POST /api/get_pnet_auth/`), создаёт сессию лабы (`POST /api/create_pnet_lab_session/`, slug мероприятия). Ожидается 200 для обоих запросов.
- Топология запрашивается через прокси PNET (`get_lab_topology(pnet_proxy_url, web_session.cookies)`). Из ответа извлекаются узлы и связи (поля `nodes`, `links` в `data` или в `data.lab`).
- Проверки: (1) количество узлов в топологии не меньше количества узлов в `scenario.lab.NodesData`; (2) имена узлов уникальны (нет дубликатов); (3) идентификаторы связей уникальны (нет дубликатов).

**Файл:** `test_lab_topology_e2e.py::test_created_lab_topology_matches_config_and_has_no_duplicates`.

---

## 5. Аутентификация в PNET через приложение (поверх Nginx)

**Цель:** убедиться, что ручка приложения выдаёт успешную аутентификацию в PNET (HTTP 200, cookies) и что с полученными cookies запрос к PNET через Nginx возвращает данные пользователя и не даёт Unauthorized.

**Сценарий:**
- Пользователь логинится в Django по Nginx (`login_to_django(base_url, username, password)`).
- Выполняется `POST {base_url}/api/get_pnet_auth/` с пустым JSON. Проверяется: `status_code == 200`, в теле `success === true` и наличие поля `cookies`.
- С теми же cookies выполняется запрос к прокси PNET: `GET {base_url}/pnetlab/api/auth`. Ожидается 200 и в JSON `code == 200` (отсутствие Unauthorized).

**Файл:** `test_pnet_auth_session_via_nginx_e2e.py::test_pnet_auth_and_lab_session_via_nginx` (первая часть).

---

## 6. Создание сессии лабы и проверка session_id (поверх Nginx)

**Цель:** проверить, что ручка создания сессии лабы возвращает 200 и `lab_path`, и что для этого пути у пользователя можно получить один и тот же `session_id` через общий метод `get_session_id()` и через фильтрацию по `lab_path` (`get_session_id_by_filter()`).

**Сценарий:**
- После сценария аутентификации (п. 5) выполняется `POST {base_url}/api/create_pnet_lab_session/` с `json={"slug": scenario.competition.slug}`. Проверяется 200, `success === true`, наличие `lab_path` в ответе.
- По cookies сессии и `lab_path` вызывается `get_session_id_by_filter(pnet_proxy_url, cookies, xsrf_token, lab_path)`. Ожидается ненулевой `session_id` и отсутствие ошибки.
- Вызывается `get_session_id(pnet_proxy_url, cookies)`. Проверяется, что возвращённый идентификатор совпадает с полученным по фильтру (с точностью до типа, например приведение к int). Тем самым проверяется согласованность сессии лабы с тем, что возвращает общий endpoint (с учётом возможной временной метки в lab_path).

**Файл:** `test_pnet_auth_session_via_nginx_e2e.py::test_pnet_auth_and_lab_session_via_nginx`.

---

## 7. KKZ: множественные лабы на пользователя и выборочная проверка топологии

**Цель:** проверить, что при создании сценария KKZ (контрольно-курсовое мероприятие) для каждого пользователя создаётся несколько лаб (по числу конкурсов/лаб в KKZ), и в случайно выбранной лабе топология получается и не пуста.

**Сценарий:**
- Подготовка через `seed_kkz_scenario(prefix, users_count=3, labs_count=2)`: создаётся взвод с пользователями, несколько лаб (тип EXAM), форма `SimpleKkzForm` с привязкой лаб и заданий; вызывается `form.create_kkz()`. В результате у KKZ несколько конкурентов (competitions), у каждого — своё имя лабы в PNET.
- Для каждой пары (competition, user) проверяется наличие файла лабы в директории пользователя: `folder_contains_lab_file(pnet_url, cookie, user_path, get_pnet_lab_name(competition))`. Тем самым проверяется, что все лабы KKZ созданы для каждого пользователя.
- Выбираются случайные competition и user. От имени этого пользователя выполняется вход в Django, получение PNET-auth и создание сессии выбранной лабы по slug конкурса. Запрашивается топология через прокси PNET. Проверяется, что топология получена и не пуста (выборочная проверка соответствия топологии конфигурации).

**Файл:** `test_kkz_multi_lab_e2e.py::test_kkz_creates_multiple_labs_per_user_with_topology_checks`.

---

## 8. Сводная таблица сценариев

| Сценарий | Форма/API | Проверяемое поведение |
|----------|------------|------------------------|
| Жизненный цикл пользователя | CustomUserCreationForm, change_user_password | Директория пользователя в PNET, user_workspace, вход с новым паролем |
| Лабы по взводу | SimpleCompetitionForm (create_competition) | Наличие .unl лабы у каждого участника во взводе |
| Воркспейс команды | SimpleCompetitionForm (create_competition) | Воркспейс = team.slug при наличии мероприятия; возврат к pnet_login после delete |
| Топология лабы | — | Совпадение узлов с конфигом, уникальность nodes/links |
| PNET auth через Nginx | POST /api/get_pnet_auth/ | 200, cookies, GET /pnetlab/api/auth без Unauthorized |
| Сессия лабы через Nginx | POST /api/create_pnet_lab_session/ | 200, lab_path, совпадение get_session_id и get_session_id_by_filter(lab_path) |
| KKZ | SimpleKkzForm (create_kkz) | Несколько лаб на пользователя, выборочная проверка топологии |

Все сценарии выполняются поверх Nginx (base_url с портом 18080); обращения к PNET для проверок структуры и сессий идут либо через прокси `/pnetlab`, либо напрямую к PNET_IP при админских операциях и cleanup.

---

## 9. Усложненная топология для топологических e2e

**Цель:** в тестах, где важна проверка topology API, использовать более сложный набор нод (несколько `docker` + `vpcs`) без изменения остальных seed-сценариев.

**Сценарий:**
- В `db_seed` добавлен отдельный helper `build_complex_topology_data()` и override-параметры для `seed_competition_scenario`/`seed_kkz_scenario`.
- Override применяется **только** в:
  - `test_lab_topology_e2e.py::test_created_lab_topology_matches_config_and_has_no_duplicates`
  - `test_kkz_multi_lab_e2e.py::test_kkz_creates_multiple_labs_per_user_with_topology_checks`
- Проверяется, что все заданные ноды присутствуют в topology и что нет дубликатов нод/связей.

---

## 10. Frontend iframe/console проверки через Playwright

**Цель:** убедиться на уровне браузера, что фронтенд реально инициализирует `iframe` в сценариях PN/CMD, а для ПЗ это работает и для администратора.

**Сценарий:**
- Новый файл `test_frontend_iframe_playwright_e2e.py`.
- Проверки:
  - PN + обычный пользователь: на странице соревнования есть `#pnetFrame`, проходит create session flow, `src` указывает на `/pnetlab/...`.
  - CMD + обычный пользователь: после `create_pnet_lab_session_with_console` `src` указывает на guacamole URL.
  - PZ + администратор: при `lab_type=PZ` и `platform=PN` iframe отображается и проходит инициализацию с созданием сессии.

---

## 11. Конкурентные и командные сценарии сессий

### 11.1. Два одновременных создания lab session + worker credentials

**Цель:** проверить корректность создания сессий при конкурентных POST и сценарий подготовки worker credentials.

**Сценарий:**
- Перед тестом выполняется команда `create_worker_credentials --workers 3`.
- Сохраняется pre-state `WORKER_1..3_CREDS`, после теста он восстанавливается.
- Выполняются 2 одновременных POST `/api/create_pnet_lab_session/` от разных пользователей.
- Проверяется:
  - ответы 200 и `success=true`;
  - трафик реально обслуживается несколькими gunicorn воркерами (`/cyberpolygon/test/worker-id/`);
  - topology для обеих сессий валидна и без дубликатов.
- Тестовые worker-пользователи в PNET удаляются в teardown.

### 11.2. Командная shared-session: распространение состояния ноды

**Цель:** подтвердить семантику командной сессии: если один участник включил ноду, второй видит это в текущей сессии команды.

**Сценарий:**
- Для TeamCompetition два участника команды создают сессию через `/api/create_pnet_lab_session/`.
- Участник A включает ноду (`turn_on_node`).
- Участник B проверяет статус этой же ноды через `nodestatus` (должен быть running/starting) и видит ноду в topology текущей сессии.
