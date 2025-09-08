#!/bin/bash

# Script to initialize Elasticsearch certificates for development
# This script generates self-signed certificates for ELK Stack

echo "🔐 Initializing Elasticsearch certificates..."

# Create certificates directory
mkdir -p ./certs

# Generate CA certificate
echo "📜 Generating CA certificate..."
docker run --rm -v "$(pwd)/certs:/usr/share/elasticsearch/config/certs" \
  docker.elastic.co/elasticsearch/elasticsearch:9.1.1 \
  /usr/share/elasticsearch/bin/elasticsearch-certutil ca \
  --out /usr/share/elasticsearch/config/certs/ca.p12 \
  --pass ""

# Generate node certificate
echo "📜 Generating node certificate..."
docker run --rm -v "$(pwd)/certs:/usr/share/elasticsearch/config/certs" \
  docker.elastic.co/elasticsearch/elasticsearch:9.1.1 \
  /usr/share/elasticsearch/bin/elasticsearch-certutil cert \
  --ca /usr/share/elasticsearch/config/certs/ca.p12 \
  --ca-pass "" \
  --out /usr/share/elasticsearch/config/certs/elasticsearch.p12 \
  --pass ""

# Convert certificates to PEM format
echo "🔄 Converting certificates to PEM format..."
docker run --rm -v "$(pwd)/certs:/usr/share/elasticsearch/config/certs" \
  docker.elastic.co/elasticsearch/elasticsearch:9.1.1 \
  openssl pkcs12 -in /usr/share/elasticsearch/config/certs/ca.p12 -out /usr/share/elasticsearch/config/certs/ca.crt -nokeys -clcerts -passin pass:

docker run --rm -v "$(pwd)/certs:/usr/share/elasticsearch/config/certs" \
  docker.elastic.co/elasticsearch/elasticsearch:9.1.1 \
  openssl pkcs12 -in /usr/share/elasticsearch/config/certs/elasticsearch.p12 -out /usr/share/elasticsearch/config/certs/elasticsearch.crt -nokeys -clcerts -passin pass:

docker run --rm -v "$(pwd)/certs:/usr/share/elasticsearch/config/certs" \
  docker.elastic.co/elasticsearch/elasticsearch:9.1.1 \
  openssl pkcs12 -in /usr/share/elasticsearch/config/certs/elasticsearch.p12 -out /usr/share/elasticsearch/config/certs/elasticsearch.key -nocerts -nodes -passin pass:

# Set proper permissions
chmod 600 ./certs/*.key
chmod 644 ./certs/*.crt

echo "✅ Certificates generated successfully!"
echo "📁 Certificates location: ./certs/"
echo "🔑 Files created:"
echo "   - ca.crt (Certificate Authority)"
echo "   - elasticsearch.crt (Node certificate)"
echo "   - elasticsearch.key (Node private key)"
echo ""
echo "🚀 You can now start ELK Stack with: docker-compose up -d"
