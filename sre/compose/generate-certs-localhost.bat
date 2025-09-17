@echo off
chcp 65001 > nul
echo [CERT] Генерация SSL сертификатов для localhost
echo.

echo [INFO] Очистка старых сертификатов...
if exist certs rmdir /s /q certs

echo [INFO] Создание папки для сертификатов...
mkdir certs

echo [CERT] Генерация CA сертификата...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil ca --out /usr/share/elasticsearch/config/certs/ca.p12 --pass ""

echo [CERT] Генерация сертификата узла для localhost...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil cert --ca /usr/share/elasticsearch/config/certs/ca.p12 --ca-pass "" --out /usr/share/elasticsearch/config/certs/elasticsearch.p12 --pass "" --dns localhost --ip 127.0.0.1

echo [CERT] Конвертация в PEM формат...
docker run --rm -v "%cd%/certs:/certs" alpine/openssl pkcs12 -in /certs/ca.p12 -out /certs/ca.crt -nokeys -clcerts -passin pass:

docker run --rm -v "%cd%/certs:/certs" alpine/openssl pkcs12 -in /certs/elasticsearch.p12 -out /certs/elasticsearch.crt -nokeys -clcerts -passin pass:

docker run --rm -v "%cd%/certs:/certs" alpine/openssl pkcs12 -in /certs/elasticsearch.p12 -out /certs/elasticsearch.key -nocerts -nodes -passin pass:

echo [SUCCESS] Сертификаты для localhost сгенерированы!
echo [INFO] Файлы:
echo    - ca.crt (Certificate Authority)
echo    - elasticsearch.crt (Node certificate для localhost)  
echo    - elasticsearch.key (Node private key)
echo.
pause
