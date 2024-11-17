#!/bin/bash
export PROD=True
export USE_POSTGRES=yes
export DB_HOST=192.168.100.5
sudo python3 deploy.py
chmod 755 run_prod.sh
chmod 755 run_scheduler.sh

python3 manage.py collectstatic --noinput
python3 manage.py makemigrations --noinput
python3 manage.py migrate --noinput

sudo rm -rf /etc/systemd/system/cyberpolygon.service
sudo cp cyberpolygon.service /etc/systemd/system/cyberpolygon.service
sudo chmod 444 /etc/systemd/system/cyberpolygon.service

sudo rm -rf /etc/systemd/system/cyberpolygon-scheduler.service
sudo cp cyberpolygon-scheduler.service /etc/systemd/system/cyberpolygon-scheduler.service
sudo chmod 444 /etc/systemd/system/cyberpolygon-scheduler.service

sudo cp logrotate.conf /etc/logrotate.d/cyberpolygon
sudo chmod 644 /etc/logrotate.d/cyberpolygon
sudo logrotate --debug /etc/logrotate.d/cyberpolygon

sudo chmod -R 777 /media
sudo chmod -R 777 /static

sudo systemctl daemon-reload
sudo systemctl enable cyberpolygon
sudo systemctl start cyberpolygon
sudo systemctl restart cyberpolygon

sudo systemctl enable cyberpolygon-scheduler
sudo systemctl start cyberpolygon-scheduler
sudo systemctl restart cyberpolygon-scheduler
