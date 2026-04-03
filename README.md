# Веб-интерфейс УЛК

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.0-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-NCFL%20v1.0-blue.svg)](LICENCE.md)

**Учебно-лабораторный комплекс (УЛК)** — комплекс для автоматизации оценивания, проведения практических, лабораторных и экзаменационных работ, а также соревнований по информационной безопасности. Проект разрабатывается в **Военно-учебном центре (ВУЦ) НИУ ВШЭ**.

<p align="center">
  <img src="assets/icons/vuz_logo.png" alt="Логотип ВУЦ НИУ ВШЭ" width="120" />
</p>

---

## Организация и лабораторные работы

Код лабораторных работ и связанные репозитории УЛК находятся в организации GitHub:

**[Киберполигон (ПИК) — hse-cyberpoligon](https://github.com/hse-cyberpoligon)**

---

## Структура проекта

```
Cyberpolygon-Interface/
├── assets/                 # Статика: CSS, JS, иконки
│   ├── css/
│   ├── js/
│   └── icons/
├── Cyberpolygon/           # Настройки Django (settings, urls, wsgi)
├── interface/              # Основное приложение: модели, views, API, админка
├── templates/              # Шаблоны (base, лабораторные, соревнования)
├── sre/                    # Развёртывание и инфраструктура
│   ├── run_service.sh      # Скрипт поднятия сервиса (systemd, nginx, deploy)
│   ├── deploy.py           # Генерация nginx/systemd из шаблонов
│   ├── gunicorn.conf.py
│   ├── Dockerfile          # Образ веб-приложения
│   └── compose/            # Docker Compose
│       ├── docker-compose.yml   # PostgreSQL + ELK (Elasticsearch, Kibana)
│       ├── env.example
│       ├── init-scripts/
│       └── elk-configs/
├── manage.py
├── requirements.txt
└── LICENCE.md
```

---

## Как поднять проект

### Вариант 1: Docker Compose (рекомендуется для разработки)

Используется каталог `sre/compose`: поднимаются PostgreSQL и при необходимости ELK (Elasticsearch, Kibana).

1. **Перейти в каталог compose и настроить окружение:**

   ```bash
   cd sre/compose
   cp env.example .env
   # При необходимости отредактировать .env (пароли, порты)
   ```

2. **Запустить PostgreSQL (достаточно для работы веб-интерфейса):**

   ```bash
   docker compose up -d postgres
   ```

3. **Опционально — ELK (логи, Kibana):**
   См. `sre/compose/README.md` и `sre/compose/QUICK_START.md` (сертификаты, `run_elk.bat` / `docker compose up -d` и т.д.).

4. **Установить зависимости и запустить Django:**

   ```bash
   # из корня репозитория
   pip install -r requirements.txt
   export USE_POSTGRES=yes
   export DB_HOST=localhost
   export POSTGRES_PORT=5431   # порт из docker-compose
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py runserver
   ```

   Приложение будет доступно по адресу `http://127.0.0.1:8000` (или по указанному в настройках).

Подключение к БД: хост `localhost`, порт `5431`, БД `cyberpolygon`, пользователь/пароль из `.env` (по умолчанию `postgres`/`postgres`).

---

### Вариант 2: Скрипт `sre/run_service.sh` (продакшен/сервер)

Скрипт настраивает окружение, генерирует конфиги (nginx, systemd), выполняет миграции и запускает сервисы через systemd.

**Требования:** Linux, права на `sudo`, установленные nginx, Python 3, настроенные переменные окружения (IP серверов БД, nginx, PNet, Kibana и т.д.).

1. **Настроить переменные** в `sre/run_service.sh` или экспортировать их перед запуском, например:

   ```bash
   export PROD=True
   export USE_POSTGRES=yes
   export DB_HOST=192.168.100.5      # хост PostgreSQL
   export NGINX_IP=192.168.100.10
   export PNET_IP=172.18.4.254
   export KIBANA_IP=192.168.100.11
   export WORKDIR=/path/to/Cyberpolygon-Interface
   ```

2. **Запустить скрипт из каталога `sre`:**

   ```bash
   cd sre
   ./run_service.sh
   ```

Скрипт вызовет `deploy.py` (шаблоны → nginx, systemd), выполнит `collectstatic`, `makemigrations`, `migrate`, скопирует unit-файлы и включит/запустит `cyberpolygon` и `cyberpolygon-scheduler`.

---

### Вариант 3: Только Docker-образ приложения

Из корня репозитория:

```bash
docker build -f sre/Dockerfile -t ulk-web .
docker run -p 8000:8000 -e USE_POSTGRES=yes -e DB_HOST=host.docker.internal ulk-web
```

Базу данных (PostgreSQL) нужно поднять отдельно (например, через `sre/compose/docker-compose.yml`).

---

## Лицензия

Проект распространяется на условиях **Non-Commercial Fork License (NCFL) v1.0**. Подробности — в [LICENCE.md](LICENCE.md).

---

**Разработано в ВУЦ НИУ ВШЭ.**
