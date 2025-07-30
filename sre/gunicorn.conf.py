# gunicorn.conf.py
# Non logging stuff
bind = "0.0.0.0:8001"
workers = 2
# Access log - records incoming HTTP requests
accesslog = "/var/log/cyberpolygon.access.log"
# Error log - records Gunicorn server goings-on
errorlog = "/var/log/cyberpolygon.log"
# Whether to send Django output to the error log
capture_output = True
# How verbose the Gunicorn error logs should be
loglevel = "info"
