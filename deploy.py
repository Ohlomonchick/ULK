import os
import sys

with open('nginx.conf.template') as f:
    string = f.read()
    string = string.replace('{%media%}', os.path.abspath('media'))
    string = string.replace('{%static%}', os.path.abspath('static'))
    # ip = sys.argv[1]
    # string = string.replace('{%ip%}', ip)
    with open('nginx.conf', mode='w', encoding='utf-8') as write_f:
        write_f.write(string)