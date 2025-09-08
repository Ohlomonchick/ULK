@echo off
echo 👥 Setting up users and roles for Kibana...

echo ⏳ Waiting for Elasticsearch to be ready...
:wait_loop
curl -k -u elastic:elastic https://localhost:9200/_cluster/health > nul 2>&1
if %errorlevel% neq 0 (
    echo Waiting for Elasticsearch...
    timeout /t 5 > nul
    goto wait_loop
)

echo ✅ Elasticsearch is ready!

echo 🔐 Creating roles...

REM Superuser role
curl -k -X POST "https://localhost:9200/_security/role/superuser" -H "Content-Type: application/json" -u elastic:elastic -d "{\"cluster\": [\"all\"], \"indices\": [{\"names\": [\"*\"], \"privileges\": [\"all\"]}]}"

REM Kibana user role
curl -k -X POST "https://localhost:9200/_security/role/kibana_user" -H "Content-Type: application/json" -u elastic:elastic -d "{\"cluster\": [\"monitor\"], \"indices\": [{\"names\": [\".kibana*\", \".reporting*\"], \"privileges\": [\"all\"]}, {\"names\": [\"logstash-*\", \"filebeat-*\"], \"privileges\": [\"read\", \"view_index_metadata\"]}]}"

REM Read-only user role
curl -k -X POST "https://localhost:9200/_security/role/readonly_user" -H "Content-Type: application/json" -u elastic:elastic -d "{\"cluster\": [\"monitor\"], \"indices\": [{\"names\": [\"logstash-*\", \"filebeat-*\"], \"privileges\": [\"read\", \"view_index_metadata\"]}]}"

echo ✅ Roles created!

echo 👤 Creating users...

REM Admin user
curl -k -X POST "https://localhost:9200/_security/user/admin" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"admin123\", \"roles\": [\"superuser\"], \"full_name\": \"Administrator\", \"email\": \"admin@cyberpolygon.local\"}"

REM Kibana user
curl -k -X POST "https://localhost:9200/_security/user/kibana_user" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"kibana123\", \"roles\": [\"kibana_user\"], \"full_name\": \"Kibana User\", \"email\": \"kibana@cyberpolygon.local\"}"

REM Read-only user
curl -k -X POST "https://localhost:9200/_security/user/readonly" -H "Content-Type: application/json" -u elastic:elastic -d "{\"password\": \"readonly123\", \"roles\": [\"readonly_user\"], \"full_name\": \"Read Only User\", \"email\": \"readonly@cyberpolygon.local\"}"

echo ✅ Users created!

echo.
echo 🎉 Setup completed successfully!
echo.
echo 📋 Created users:
echo    👑 admin / admin123 (Superuser - full access)
echo    📊 kibana_user / kibana123 (Kibana user - can create dashboards)
echo    👁️  readonly / readonly123 (Read-only user - can only view data)
echo.
echo 🌐 Access Kibana at: https://localhost:5601
echo 🔐 Use any of the above credentials to log in
echo.
echo ⚠️  Note: These are development credentials. Change them for production!
pause
