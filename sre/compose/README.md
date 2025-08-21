# PostgreSQL Docker Compose Setup

Этот docker-compose файл настраивает PostgreSQL 15 для проекта Cyberpolygon.

## Особенности

- PostgreSQL 15
- Порт: 5431 (внешний) -> 5432 (внутренний)
- Настроен для подключения отовсюду (`listen_addresses='*'`)
- Оптимизированные настройки производительности
- Постоянное хранение данных в Docker volume

## Быстрый старт

1. Скопируйте файл переменных окружения:
   ```bash
   cp env.example .env
   ```

2. При необходимости отредактируйте `.env` файл:
   ```bash
   # Измените пароль и другие настройки
   POSTGRES_PASSWORD=your_secure_password
   ```

3. Запустите PostgreSQL:
   ```bash
   docker-compose up -d
   ```

4. Проверьте статус:
   ```bash
   docker-compose ps
   ```

## Подключение к базе данных

### Через psql (внутри контейнера):
```bash
docker-compose exec postgres psql -U postgres -d cyberpolygon
```

### Через внешний клиент:
- Host: `localhost`
- Port: `5431`
- Database: `cyberpolygon`
- Username: `postgres`
- Password: `postgres` (или значение из .env)

### Пример подключения через Python:
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5431,
    database="cyberpolygon",
    user="postgres",
    password="postgres"
)
```

## Управление

### Остановка:
```bash
docker-compose down
```

### Остановка с удалением данных:
```bash
docker-compose down -v
```

### Просмотр логов:
```bash
docker-compose logs postgres
```

### Перезапуск:
```bash
docker-compose restart postgres
```

## Настройки производительности

Docker-compose включает оптимизированные настройки PostgreSQL:
- `shared_buffers`: 256MB
- `effective_cache_size`: 1GB
- `work_mem`: 4MB
- `maintenance_work_mem`: 64MB
- `max_connections`: 200

Эти настройки подходят для большинства средних нагрузок. Для продакшена рекомендуется настроить под конкретные требования.

## Безопасность

⚠️ **Важно**: В продакшене обязательно измените пароль по умолчанию и настройте соответствующие правила доступа.
