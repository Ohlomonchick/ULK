#!/bin/bash
export PROD=True
export USE_POSTGRES=yes
export DB_HOST=192.168.100.5

#source /mnt/c/Users/Dmitry/PycharmProjects/Cyberpolygon/polygon_linux/bin/activate

python3 ../manage.py runapscheduler
