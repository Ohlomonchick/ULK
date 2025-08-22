@echo off
echo 🚀 Starting ELK Stack 9.1.1 for Cyberpolygon (Simplified without SSL)...

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
echo    Elasticsearch: http://localhost:9200 (no authentication required)
echo    Kibana: http://localhost:5601 (no authentication required)
echo    Logstash API: http://localhost:9600
echo.
echo 📝 To view logs: docker-compose logs [service_name]
echo 📝 To stop: docker-compose down
echo.
pause
