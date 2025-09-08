@echo off
echo 🚀 Starting ELK Stack 9.1.1 for Cyberpolygon (With Authentication)...

REM Check if certificates exist
if not exist "certs\ca.crt" (
    echo ❌ Certificates not found!
    echo 🔐 Please run init-certs.bat first to generate certificates
    pause
    exit /b 1
)

echo 🔐 Starting Elasticsearch, Logstash, Kibana, and Filebeat...

REM Start ELK services
docker-compose up -d elasticsearch logstash kibana filebeat

echo.
echo 📊 ELK Stack is starting...
echo.
echo 🔍 Services status:
docker-compose ps elasticsearch logstash kibana filebeat

echo.
echo 🌐 Access URLs:
echo    Elasticsearch: https://localhost:9200 (username: elastic, password: elastic)
echo    Kibana: https://localhost:5601 (authentication required)
echo    Logstash API: http://localhost:9600
echo.
echo 👥 To setup users and roles, run: setup-users.bat
echo 📝 To view logs: docker-compose logs [service_name]
echo 📝 To stop: docker-compose down
echo.
pause
