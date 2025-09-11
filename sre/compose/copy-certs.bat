@echo off
chcp 65001 > nul
echo [COPY] Копирование сертификатов в правильные места
echo.

echo [COPY] Копирование CA сертификата...
copy "certs\ca\ca.crt" "certs\ca.crt"

echo [COPY] Копирование сертификата узла...
copy "certs\instance\instance.crt" "certs\elasticsearch.crt"

echo [COPY] Копирование приватного ключа узла...
copy "certs\instance\instance.key" "certs\elasticsearch.key"

echo [SUCCESS] Сертификаты скопированы!
echo [INFO] Файлы в корне certs:
echo    - ca.crt (Certificate Authority)
echo    - elasticsearch.crt (Node certificate)  
echo    - elasticsearch.key (Node private key)
echo.
pause
