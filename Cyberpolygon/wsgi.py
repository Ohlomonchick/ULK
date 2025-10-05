"""
WSGI config for Cyberpolygon project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

# Monkey patching для gevent только в production (Gunicorn)
# В development (runserver) это не нужно и вызывает ошибки
if os.getenv('GUNICORN_WORKER', '') == 'true':
    from gevent import monkey
    monkey.patch_all()

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Cyberpolygon.settings')

application = get_wsgi_application()