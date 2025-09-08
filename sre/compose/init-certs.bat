@echo off
echo 🔐 Initializing Elasticsearch certificates...

REM Create certificates directory
if not exist "certs" mkdir certs

echo 📜 Generating CA certificate...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" docker.elastic.co/elasticsearch/elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil ca --out /usr/share/elasticsearch/config/certs/ca.p12 --pass ""

echo 📜 Generating node certificate...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" docker.elastic.co/elasticsearch/elasticsearch:9.1.1 /usr/share/elasticsearch/bin/elasticsearch-certutil cert --ca /usr/share/elasticsearch/config/certs/ca.p12 --ca-pass "" --out /usr/share/elasticsearch/config/certs/elasticsearch.p12 --pass ""

echo 🔄 Converting certificates to PEM format...
docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" docker.elastic.co/elasticsearch/elasticsearch:9.1.1 openssl pkcs12 -in /usr/share/elasticsearch/config/certs/ca.p12 -out /usr/share/elasticsearch/config/certs/ca.crt -nokeys -clcerts -passin pass:

docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" docker.elastic.co/elasticsearch/elasticsearch:9.1.1 openssl pkcs12 -in /usr/share/elasticsearch/config/certs/elasticsearch.p12 -out /usr/share/elasticsearch/config/certs/elasticsearch.crt -nokeys -clcerts -passin pass:

docker run --rm -v "%cd%/certs:/usr/share/elasticsearch/config/certs" docker.elastic.co/elasticsearch/elasticsearch:9.1.1 openssl pkcs12 -in /usr/share/elasticsearch/config/certs/elasticsearch.p12 -out /usr/share/elasticsearch/config/certs/elasticsearch.key -nocerts -nodes -passin pass:

echo ✅ Certificates generated successfully!
echo 📁 Certificates location: ./certs/
echo 🔑 Files created:
echo    - ca.crt (Certificate Authority)
echo    - elasticsearch.crt (Node certificate)
echo    - elasticsearch.key (Node private key)
echo.
echo 🚀 You can now start ELK Stack with: docker-compose up -d
pause
