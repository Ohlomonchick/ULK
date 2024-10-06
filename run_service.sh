#!/bin/bash
chmod 755 run_prod.sh
python3 deploy.py

sudo rm -rf /etc/systemd/system/cyberpolygon.service
sudo cp cyberpolygon.service /etc/systemd/system/cyberpolygon.service
sudo chmod 444 /etc/systemd/system/cyberpolygon.service

sudo chmod -R 777 media
sudo chmod -R 777 static

sudo systemctl daemon-reload
sudo systemctl enable cyberpolygon
sudo systemctl start cyberpolygon

