@echo off
echo 🔐 Настройка аутентификации Kibana (без SSL)
echo.

echo 📋 Этот скрипт настроит:
echo    1. Перезапуск ELK Stack с аутентификацией
echo    2. Создание пользователей для Kibana
echo.

set /p continue="Продолжить? (y/n): "
if /i not "%continue%"=="y" (
    echo Отменено пользователем
    pause
    exit /b 0
)

echo.
echo 🛑 Остановка текущих сервисов...
docker-compose down

echo.
echo 🚀 Запуск ELK Stack с аутентификацией...
docker-compose up -d elasticsearch logstash kibana filebeat

echo.
echo ⏳ Ожидание готовности Elasticsearch...
timeout /t 30 > nul

echo.
echo 👥 Создание пользователей для Kibana...

REM Создание ролей
echo 🔐 Создание ролей...
curl -X POST "http://localhost:9200/_security/role/kibana_user" -H "Content-Type: application/json" -u elastic:elastic -d "{\"cluster\": [\"monitor\"], \"indices\": [{\"names\": [\".kibana*\", \".reporting*\"], \"privileges\": [\"all\"]}, {\"names\": [\"logstash-*\", \"filebeat-*\"], \"privileges\": [\"read\", \"view_index_metadata\"]}]}"

curl -X POST "http://localhost:9200/_security/role/readonly_user" -H "Content-Type: application/json" -u elastic:elastic -d "{\"cluster\": [\"monitor\"], \"indices\": [{\"names\": [\"logstash-*\", \"filebeat-*\"], \"privileges\": [\"read\", \"view_index_metadata\"]}]}"

echo.
echo 👤 Создание пользователей...

REM Admin user
curl -X POST "http://localhost:9200/_security/user/admin" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"admin123\", \"roles\": [\"superuser\"], \"full_name\": \"Administrator\", \"email\": \"admin@cyberpolygon.local\"}"

REM Kibana user
curl -X POST "http://localhost:9200/_security/user/kibana_user" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"kibana123\", \"roles\": [\"kibana_user\"], \"full_name\": \"Kibana User\", \"email\": \"kibana@cyberpolygon.local\"}"

REM Read-only user
curl -X POST "http://localhost:9200/_security/user/readonly" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"readonly123\", \"roles\": [\"readonly_user\"], \"full_name\": \"Read Only User\", \"email\": \"readonly@cyberpolygon.local\"}"

echo.
echo 🎉 Настройка завершена!
echo.
echo 📋 Созданные пользователи:
echo    👑 admin / admin123 (Superuser - полный доступ)
echo    📊 kibana_user / kibana123 (Kibana user - может создавать дашборды)
echo    👁️  readonly / readonly123 (Read-only user - только просмотр данных)
echo.
echo 🌐 Доступ:
echo    Elasticsearch: http://localhost:9200 (elastic/elastic)
echo    Kibana: http://localhost:5601 (используйте любого из созданных пользователей)
echo.
echo ⚠️  Это учетные данные для разработки. Измените их для продакшена!
echo.
pause
