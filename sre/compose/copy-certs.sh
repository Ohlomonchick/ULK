#!/bin/bash

echo "[COPY] Копирование сертификатов в правильные места"
echo ""

echo "[COPY] Копирование CA сертификата..."
cp "certs/ca/ca.crt" "certs/ca.crt"

echo "[COPY] Копирование сертификата узла..."
cp "certs/instance/instance.crt" "certs/elasticsearch.crt"

echo "[COPY] Копирование приватного ключа узла..."
cp "certs/instance/instance.key" "certs/elasticsearch.key"

# Установка правильных прав доступа
chmod 600 certs/*.key
chmod 644 certs/*.crt

echo "[SUCCESS] Сертификаты скопированы!"
echo "[INFO] Файлы в корне certs:"
echo "   - ca.crt (Certificate Authority)"
echo "   - elasticsearch.crt (Node certificate)"
echo "   - elasticsearch.key (Node private key)"
echo ""


