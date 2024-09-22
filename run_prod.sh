export PROD=True
gunicorn --workers 3 --bind 0.0.0.0:8000 Cyberpolygon.wsgi:application \
--access-logfile gunicorn-access.log \
--error-logfile gunicorn-error.log --daemon
sudo rm -rf /etc/nginx/sites-available/django_project
sudo cp nginx.conf /etc/nginx/sites-available/django_project
sudo chmod 777 /etc/nginx/sites-available/django_project
sudo ln -s /etc/nginx/sites-available/django_project /etc/nginx/sites-enabled
sudo systemctl restart nginx