#!/bin/bash

# Nginx configuration: теперь используется полная конфигурация nginx вместо sites-available
# Конфигурация генерируется из nginx_full.conf.template и копируется в /etc/nginx/nginx.conf

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

find "$SCRIPT_DIR" -type f -name "*.sh" -exec dos2unix {} \;
cd "$SCRIPT_DIR"

export PROD=True
export USE_POSTGRES=yes
export DB_HOST=192.168.100.5
export NGINX_IP=192.168.100.10
# export NGINX_IP=127.0.0.1
# export PNET_IP=192.168.1.10
export PNET_IP=172.18.4.160
export WORKDIR="$PROJECT_ROOT"
python3 deploy.py
chmod 755 run_prod.sh
chmod 755 run_scheduler.sh

python3 "$PROJECT_ROOT/manage.py" collectstatic --noinput
python3 "$PROJECT_ROOT/manage.py" makemigrations --noinput
python3 "$PROJECT_ROOT/manage.py" migrate --noinput

sudo rm -rf /etc/systemd/system/cyberpolygon.service
sudo cp cyberpolygon.service /etc/systemd/system/cyberpolygon.service
sudo chmod 444 /etc/systemd/system/cyberpolygon.service

sudo rm -rf /etc/systemd/system/cyberpolygon-scheduler.service
sudo cp cyberpolygon-scheduler.service /etc/systemd/system/cyberpolygon-scheduler.service
sudo chmod 444 /etc/systemd/system/cyberpolygon-scheduler.service

sudo cp logrotate.conf /etc/logrotate.d/cyberpolygon
sudo chmod 644 /etc/logrotate.d/cyberpolygon
sudo logrotate -v /etc/logrotate.d/cyberpolygon

sudo chmod -R 777 /media
sudo chmod -R 777 /static

sudo systemctl daemon-reload
sudo systemctl enable cyberpolygon
sudo systemctl start cyberpolygon
sudo systemctl restart cyberpolygon

sudo systemctl enable cyberpolygon-scheduler
sudo systemctl start cyberpolygon-scheduler
sudo systemctl restart cyberpolygon-scheduler
