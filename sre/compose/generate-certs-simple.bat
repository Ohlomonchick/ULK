@echo off
chcp 65001 > nul
echo [CERT] Простая генерация SSL сертификатов
echo.

echo [INFO] Очистка старых сертификатов...
Remove-Item -Recurse -Force certs -ErrorAction SilentlyContinue

echo [INFO] Создание папки для сертификатов...
mkdir certs

echo [CERT] Генерация CA сертификата...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil ca --out /usr/share/elasticsearch/config/certs/ca.p12 --pass ""

echo [CERT] Генерация сертификата узла...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil cert --ca /usr/share/elasticsearch/config/certs/ca.p12 --ca-pass "" --out /usr/share/elasticsearch/config/certs/elasticsearch.p12 --pass ""

echo [CERT] Конвертация в PEM формат...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 openssl pkcs12 -in /usr/share/elasticsearch/config/certs/ca.p12 -out /usr/share/elasticsearch/config/certs/ca.crt -nokeys -clcerts -passin pass:

docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 openssl pkcs12 -in /usr/share/elasticsearch/config/certs/elasticsearch.p12 -out /usr/share/elasticsearch/config/certs/elasticsearch.crt -nokeys -clcerts -passin pass:

docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 openssl pkcs12 -in /usr/share/elasticsearch/config/certs/elasticsearch.p12 -out /usr/share/elasticsearch/config/certs/elasticsearch.key -nocerts -nodes -passin pass:

echo [SUCCESS] Сертификаты сгенерированы!
echo [INFO] Файлы:
echo    - ca.crt (Certificate Authority)
echo    - elasticsearch.crt (Node certificate)  
echo    - elasticsearch.key (Node private key)
echo.
pause
