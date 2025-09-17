@echo off
chcp 65001 > nul
echo [COPY] Copying certificates into Kibana container...
echo.

echo [INFO] Stopping Kibana...
docker-compose stop kibana

echo [INFO] Copying certificates to container...
docker run --rm -v "%cd%/certs:/certs" -v "%cd%/elk-configs/kibana:/config" alpine sh -c "cp /certs/*.crt /certs/*.key /config/ && chmod 644 /config/*.crt && chmod 600 /config/*.key"

echo [INFO] Starting Kibana...
docker-compose up -d kibana

echo [SUCCESS] Certificates copied to container!
echo [INFO] Check Kibana logs:
echo    docker-compose logs kibana
echo.
pause
