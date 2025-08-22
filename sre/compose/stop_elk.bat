@echo off
echo 🛑 Stopping ELK Stack 9.1.1...

REM Stop ELK services
docker-compose stop elasticsearch logstash kibana filebeat

echo.
echo ✅ ELK Stack stopped
echo.
echo 🔍 Current services status:
docker-compose ps

echo.
echo 💡 To start again: run_elk.bat
echo 💡 To remove containers: docker-compose down
echo.
pause
