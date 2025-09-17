#!/bin/bash

echo "[SSL] Настройка ELK Stack с SSL по умолчанию (версия 9.1.1)"
echo ""

echo "[INFO] Этот скрипт настроит:"
echo "   1. Остановку текущих сервисов"
echo "   2. Копирование сертификатов для SSL"
echo "   3. Запуск ELK Stack с SSL"
echo "   4. Настройку пользователей"
echo ""

read -p "Продолжить? (y/n): " continue
if [[ ! "$continue" =~ ^[Yy]$ ]]; then
    echo "Отменено пользователем"
    exit 0
fi

echo ""
echo "[STOP] Остановка текущих сервисов..."
docker-compose down

echo ""
echo "[COPY] Копирование сертификатов в правильные места..."
./copy-certs.sh

echo ""
echo "[START] Запуск ELK Stack с SSL..."
docker-compose up -d elasticsearch logstash kibana filebeat

echo ""
echo "[WAIT] Ожидание готовности Elasticsearch..."
sleep 30

echo ""
echo "[PASS] Установка паролей для системных пользователей..."

# Установка пароля для elastic
echo "[PASS] Установка пароля для elastic..."
curl -k -X POST "https://localhost:9200/_security/user/elastic/_password" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"password": "elastic"}'

# Установка пароля для kibana_system
echo "[PASS] Установка пароля для kibana_system..."
curl -k -X POST "https://localhost:9200/_security/user/kibana_system/_password" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"password": "elastic"}'

# Установка пароля для logstash_system
echo "[PASS] Установка пароля для logstash_system..."
curl -k -X POST "https://localhost:9200/_security/user/logstash_system/_password" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"password": "elastic"}'

echo ""
echo "[USER] Создание пользователей для Kibana..."

# Создание ролей
echo "[ROLE] Создание ролей..."
curl -k -X POST "https://localhost:9200/_security/role/kibana_user" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"cluster": ["monitor"], "indices": [{"names": [".kibana*", ".reporting*"], "privileges": ["all"]}, {"names": ["logstash-*", "filebeat-*"], "privileges": ["read", "view_index_metadata"]}]}'

curl -k -X POST "https://localhost:9200/_security/role/readonly_user" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"cluster": ["monitor"], "indices": [{"names": ["logstash-*", "filebeat-*"], "privileges": ["read", "view_index_metadata"]}]}'

# Создание пользователей
echo "[USER] Создание пользователей..."
curl -k -X POST "https://localhost:9200/_security/user/admin" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"password": "admin123", "roles": ["superuser"], "full_name": "Administrator", "email": "admin@cyberpolygon.local"}'

curl -k -X POST "https://localhost:9200/_security/user/kibana_user" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"password": "kibana123", "roles": ["kibana_user"], "full_name": "Kibana User", "email": "kibana@cyberpolygon.local"}'

curl -k -X POST "https://localhost:9200/_security/user/readonly" \
  -H "Content-Type: application/json" \
  -u elastic:elastic \
  -d '{"password": "readonly123", "roles": ["readonly_user"], "full_name": "Read Only User", "email": "readonly@cyberpolygon.local"}'

echo ""
echo "[SUCCESS] Настройка завершена!"
echo ""
echo "[USERS] Созданные пользователи:"
echo "   admin / admin123 (Superuser - полный доступ)"
echo "   kibana_user / kibana123 (Kibana user - может создавать дашборды)"
echo "   readonly / readonly123 (Read-only user - только просмотр данных)"
echo ""
echo "[ACCESS] Доступ:"
echo "   Elasticsearch: https://localhost:9200 (elastic/elastic)"
echo "   Kibana: https://localhost:5601 (используйте любого из созданных пользователей)"
echo ""
echo "[WARNING] Это учетные данные для разработки. Измените их для продакшена!"
echo ""


