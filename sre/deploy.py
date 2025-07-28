import os
import sys

with open('nginx.conf.template') as f:
    string = f.read()

    ip = '192.168.100.10:80'
    # ip = '0.0.0.0:80'
    if len(sys.argv) > 1:
        ip = sys.argv[1]
    string = string.replace('{%ip%}', ip)

    with open('nginx.conf', mode='w', encoding='utf-8') as write_f:
        write_f.write(string)

with open('cyberpolygon.service.template') as f:
    string = f.read()
    string = string.replace('{%workdir%}', os.getcwd())
    string = string.replace('{%run_script%}', os.path.abspath('run_prod.sh'))
    with open('cyberpolygon.service', mode='w', encoding='utf-8') as write_f:
        write_f.write(string)


with open('cyberpolygon-scheduler.service.template') as f:
    string = f.read()
    string = string.replace('{%workdir%}', os.getcwd())
    string = string.replace('{%run_script%}', os.path.abspath('run_scheduler.sh'))
    with open('cyberpolygon-scheduler.service', mode='w', encoding='utf-8') as write_f:
        write_f.write(string)


with open('run_prod.sh.template') as f:
    string = f.read()
    string = string.replace('{%gunicorn.conf.py%}', os.path.abspath('gunicorn.conf.py'))
    with open('run_prod.sh', mode='w', encoding='utf-8') as write_f:
        write_f.write(string)

os.chmod('run_prod.sh', 0o666)
