@echo off

python -m venv venv

call .\venv\Scripts\activate

pip install -r requirements.txt

python manage.py makemigrations --noinput
python manage.py migrate --noinput
python manage.py collectstatic --noinput

pause