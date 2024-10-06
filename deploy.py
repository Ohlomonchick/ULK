import os
import sys

with open('nginx.conf.template') as f:
    string = f.read()
    string = string.replace('{%media%}', os.path.abspath('media'))
    string = string.replace('{%static%}', os.path.abspath('static'))

    ip = '192.168.100.10:80'
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
