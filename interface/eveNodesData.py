server_params = {
    "template": "linux",
    "type": "qemu",
    "image": "linux-wordpress_CVE_ubuntu",
    "name": "Linux_created_by_api",
    "description": "Linux",
    "icon": "linux-1.png",
    "firstmac": "",
    "first_nic": "",
    "uuid": "",
    "cpulimit": 1,
    "cpu": 2,
    "ram": 4096,
    "console": "vnc",
    "map_port": "",
    "console_2nd": "",
    "map_port_2nd": "",
    "username": "",
    "password": "",
    "ethernet": 1,
    "qemu_arch": "x86_64",
    "qemu_nic": "virtio-net-pci",
    "qemu_version": "4.1.0",
    "qemu_options": "-machine type=pc,accel=kvm -vga virtio -usbdevice tablet -boot order=cd -cpu host",
    "config_script": "",
    "script_timeout": 1200,
    "config": 0,
    "delay": 0,
    "size": "",
    "left": 422,
    "top": 394,
    "shutdown": 1,
    "count": "1",
    "postfix": 0
}

kali_params = {
    "template": "linux",
    "type": "qemu",
    "image": "linux-wordpress_CVE_kali_v2",
    "name": "Kali-Linux",
    "description": "Linux",
    "icon": "Kali.png",
    "firstmac": "",
    "first_nic": "",
    "uuid": "",
    "cpulimit": 1,
    "cpu": 2,
    "ram": 2048,
    "console": "vnc",
    "map_port": "",
    "console_2nd": "",
    "map_port_2nd": "",
    "username": "",
    "password": "",
    "ethernet": 1,
    "qemu_arch": "x86_64",
    "qemu_nic": "virtio-net-pci",
    "qemu_version": "4.1.0",
    "qemu_options": "-machine type=pc,accel=kvm -vga virtio -usbdevice tablet -boot order=cd -cpu host",
    "config_script": "",
    "script_timeout": 1200,
    "config": 0,
    "delay": 0,
    "size": "",
    "left": 789,
    "top": 489,
    "shutdown": 1,
    "count": "1",
    "postfix": 0
}

NodesData = {
    "Wordpress US Army" : [server_params, kali_params]
}

ConnectorsData = {
    "Wordpress US Army" : [{"name" : "first_connnection","src" : "1", "srcif" : "0", "dest" : "2", "destif" : "0"}]
}
