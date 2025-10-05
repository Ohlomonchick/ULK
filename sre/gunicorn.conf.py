# gunicorn.conf.py
import os

# Устанавливаем флаг для wsgi.py чтобы он знал что запущен через Gunicorn
os.environ['GUNICORN_WORKER'] = 'true'

# Non logging stuff
bind = "0.0.0.0:8002"
workers = 3
worker_class = "gevent"
worker_connections = 1000
timeout = 90
# Access log - records incoming HTTP requests
accesslog = "/var/log/cyberpolygon.access.log"
# Error log - records Gunicorn server goings-on
errorlog = "/var/log/cyberpolygon.log"
# Whether to send Django output to the error log
capture_output = True
# How verbose the Gunicorn error logs should be
loglevel = "info"
