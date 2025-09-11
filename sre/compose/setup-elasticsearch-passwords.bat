@echo off
echo 🔐 Настройка паролей для встроенных пользователей Elasticsearch
echo.

echo 📋 Этот скрипт установит пароли для системных пользователей:
echo    - elastic (суперпользователь)
echo    - kibana_system (для Kibana)
echo    - logstash_system (для Logstash)
echo.

set /p continue="Продолжить? (y/n): "
if /i not "%continue%"=="y" (
    echo Отменено пользователем
    pause
    exit /b 0
)

echo.
echo ⏳ Ожидание готовности Elasticsearch...
timeout /t 10 > nul

echo.
echo 🔑 Установка паролей для системных пользователей...

REM Установка пароля для elastic (если еще не установлен)
echo Устанавливаю пароль для пользователя elastic...
curl -X POST "http://localhost:9200/_security/user/elastic/_password" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"elastic\"}"

REM Установка пароля для kibana_system
echo Устанавливаю пароль для пользователя kibana_system...
curl -X POST "http://localhost:9200/_security/user/kibana_system/_password" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"elastic\"}"

REM Установка пароля для logstash_system
echo Устанавливаю пароль для пользователя logstash_system...
curl -X POST "http://localhost:9200/_security/user/logstash_system/_password" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"elastic\"}"

echo.
echo ✅ Пароли установлены!
echo.
echo 📋 Системные пользователи:
echo    👑 elastic / elastic (суперпользователь)
echo    📊 kibana_system / elastic (для Kibana)
echo    📝 logstash_system / elastic (для Logstash)
echo.
echo 🔄 Теперь перезапустите Kibana для применения изменений
echo.
pause
