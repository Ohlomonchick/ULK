@echo off
chcp 65001 > nul
echo [CERT] Генерация SSL сертификатов для ELK Stack
echo.

echo [INFO] Очистка старых сертификатов...
Remove-Item -Recurse -Force certs -ErrorAction SilentlyContinue

echo [INFO] Создание папки для сертификатов...
mkdir certs

echo [CERT] Генерация CA сертификата в PEM формате...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil ca --pem --out /usr/share/elasticsearch/config/certs/ca.zip

echo [CERT] Распаковка CA сертификата...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 unzip -o /usr/share/elasticsearch/config/certs/ca.zip -d /usr/share/elasticsearch/config/certs/

echo [CERT] Генерация сертификата узла в PEM формате...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil cert --ca-cert /usr/share/elasticsearch/config/certs/ca/ca.crt --ca-key /usr/share/elasticsearch/config/certs/ca/ca.key --pem --out /usr/share/elasticsearch/config/certs/elasticsearch.zip

echo [CERT] Распаковка сертификата узла...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 unzip -o /usr/share/elasticsearch/config/certs/elasticsearch.zip -d /usr/share/elasticsearch/config/certs/

echo [CERT] Копирование файлов в корень папки certs...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" elasticsearch:9.1.1 sh -c "cp /usr/share/elasticsearch/config/certs/ca/ca.crt /usr/share/elasticsearch/config/certs/ && cp /usr/share/elasticsearch/config/certs/elasticsearch/elasticsearch.crt /usr/share/elasticsearch/config/certs/ && cp /usr/share/elasticsearch/config/certs/elasticsearch/elasticsearch.key /usr/share/elasticsearch/config/certs/"

echo [SUCCESS] Сертификаты сгенерированы успешно!
echo [INFO] Файлы:
echo    - ca.crt (Certificate Authority)
echo    - elasticsearch.crt (Node certificate)  
echo    - elasticsearch.key (Node private key)
echo.
pause
