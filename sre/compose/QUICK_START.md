# 🚀 Быстрый старт ELK Stack 9.1.1 (С аутентификацией)

## Шаг 1: Настройка переменных окружения
```bash
cp env.example .env
# Отредактируйте .env при необходимости
```

## Шаг 2: Генерация сертификатов
```bash
# Для Windows
init-certs.bat

# Для Linux/macOS
chmod +x init-certs.sh
./init-certs.sh
```

## Шаг 3: Запуск ELK Stack
```bash
run_elk.bat
```

## Шаг 4: Настройка пользователей и ролей
```bash
# Для Windows
setup-users.bat

# Для Linux/macOS
chmod +x setup-users.sh
./setup-users.sh
```

## Шаг 5: Проверка работы
- **Kibana**: https://localhost:5601 (требует аутентификации)
- **Elasticsearch**: https://localhost:9200 (username: elastic, password: elastic)
- **Logstash API**: http://localhost:9600

## Остановка
```bash
stop_elk.bat
```

## Полезные команды
```bash
# Просмотр логов
docker-compose logs elasticsearch
docker-compose logs logstash
docker-compose logs kibana

# Статус сервисов
docker-compose ps

# Перезапуск
docker-compose restart elasticsearch
```

## 🔑 Аутентификация
### Созданные пользователи:
- **admin** / admin123 (Superuser - полный доступ)
- **kibana_user** / kibana123 (Kibana user - может создавать дашборды)
- **readonly** / readonly123 (Read-only user - только просмотр данных)

### Доступ:
- **Elasticsearch**: https://localhost:9200 (username: elastic, password: elastic)
- **Kibana**: https://localhost:5601 (используйте любого из созданных пользователей)

⚠️ **Это учетные данные для разработки. Измените их для продакшена!**
