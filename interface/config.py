import os
from django.conf import settings

PNET_URL = 'http://172.18.4.160'

if settings.DEBUG:
    PNET_BASE_DIR = '/Practice work/Test_Labs/api_test_dir'
else:
    PNET_BASE_DIR = os.environ.get('PNET_BASE_DIR', '/Practice work/Test_Labs/api_test_dir')
