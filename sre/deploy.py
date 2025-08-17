import os
import sys
from jinja2 import Template

# Configuration dictionary - общий контекст для всех шаблонов
context = {
    'ip': os.environ.get("NGINX_IP", "192.168.100.10"),
    'workdir': os.environ.get('WORKDIR', os.getcwd()),
    'run_script': os.path.abspath('run_prod.sh'),
    'scheduler_script': os.path.abspath('run_scheduler.sh'),
    'gunicorn_conf': os.path.abspath('gunicorn.conf.py'),
    'use_postgres': os.environ.get('USE_POSTGRES', 'yes'),
    'db_host': os.environ.get('DB_HOST', '192.168.100.5'),
    'pnet_ip': os.environ.get('PNET_IP', '192.168.100.10'),
    'user': 'root',
    'group': 'root',
    'log_dir': '/var/log',
    'static_dir': '/static',
    'media_dir': '/media',
    'proxy_port': '8002'
}

# Override IP from command line argument
if len(sys.argv) > 1:
    context['ip'] = sys.argv[1]

def render_template(template_path, output_path):
    """Render a Jinja2 template and write to output file"""
    with open(template_path, 'r', encoding='utf-8') as f:
        template = Template(f.read())
    
    rendered = template.render(**context)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rendered)
    
    print(f"Generated: {output_path}")

# Список шаблонов для обработки
templates = [
    ('nginx_full.conf.template', 'nginx.conf'),
    ('cyberpolygon.service.template', 'cyberpolygon.service'),
    ('cyberpolygon-scheduler.service.template', 'cyberpolygon-scheduler.service'),
    ('run_prod.sh.template', 'run_prod.sh'),
    ('run_scheduler.sh.template', 'run_scheduler.sh')
]

# Render all templates
for template_file, output_file in templates:
    render_template(template_file, output_file)

# Set permissions
os.chmod('run_prod.sh', 0o755)
os.chmod('run_scheduler.sh', 0o755)

# Copy nginx configuration to system directory
import subprocess
import shutil

try:
    # Backup existing nginx config if it exists
    if os.path.exists('/etc/nginx/nginx.conf'):
        shutil.copy2('/etc/nginx/nginx.conf', '/etc/nginx/nginx.conf.backup')
        print("Backed up existing nginx.conf")
    
    # Copy our generated nginx config
    shutil.copy2('nginx.conf', '/etc/nginx/nginx.conf')
    print("Copied nginx.conf to /etc/nginx/nginx.conf")
    
    # Test nginx configuration
    result = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    if result.returncode == 0:
        print("Nginx configuration test passed")
        # Reload nginx
        subprocess.run(['systemctl', 'reload', 'nginx'], check=True)
        print("Nginx reloaded successfully")
    else:
        print(f"Nginx configuration test failed: {result.stderr}")
        
except Exception as e:
    print(f"Error configuring nginx: {e}")

print("Deployment configuration completed!")
print(f"IP: {context['ip']}")
print(f"Working directory: {context['workdir']}")
