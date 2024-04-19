server_params = {
    "template": "linux",
    "type": "qemu",
    "image": "linux-wordpress_CVE_ubuntu",
    "name": "Ubuntu-server",
    "description": "Linux",
    "icon": "linux-1.png",
    "firstmac": "",
    "first_nic": "",
    "uuid": "",
    "cpulimit": 1,
    "cpu": 1,
    "ram": 1024,
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
    "left": 312,
    "top": 474,
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
    "left": 888,
    "top": 543,
    "shutdown": 1,
    "count": "1",
    "postfix": 0
}

router_params = {
    "template": "mikrotik",
    "type": "qemu",
    "image": "mikrotik-student2",
    "name": "Mikrotik",
    "description": "MikroTik RouterOS",
    "icon": "Router.png",
    "firstmac": "",
    "first_nic": "",
    "uuid": "",
    "cpulimit": 1,
    "cpu": 1,
    "ram": 256,
    "console": "telnet",
    "map_port": "",
    "console_2nd": "",
    "map_port_2nd": "",
    "username": "",
    "password": "",
    "ethernet": 4,
    "qemu_arch": "x86_64",
    "qemu_nic": "e1000",
    "qemu_version": "2.12.0",
    "qemu_options": "-machine type=pc,accel=kvm -serial mon:stdio -nographic -no-user-config -nodefaults -display none -vga std -rtc base=utc",
    "config_script": "config_mikrotik.py",
    "script_timeout": 1200,
    "config": 0,
    "delay": 0,
    "size": "",
    "left": 639,
    "top": 426,
    "count": "1",
    "postfix": 0
}

net_params = {
  "count": "1",
  "visibility": "1",
  "name": "Net",
  "type": "nat0",
  "left": 597,
  "top": "183",
  "size": "",
  "icon": "global.png",
  "postfix": 0
}

p2Cloud_params = {
  "node_id": "1",
  "data": {
    "0": "1"
  }
}

p2p_server = {
    "name": "p2p_server",
    "src_id": "1",
    "src_if": "2",
    "dest_id": "2",
    "dest_if": "0"
}

p2p_kali = {
    "name": "p2p_kali",
    "src_id": "1",
    "src_if": "1",
    "dest_id": "3",
    "dest_if": "0"
}

NodesData = {
    "Wordpress" : [router_params, server_params, kali_params]
}

ConnectorsData = {
    "Wordpress" : [p2p_server, p2p_kali]
}

Connectors2CloudData = {
    "Wordpress" : [p2Cloud_params]
}

NetworksData = {
    "Wordpress" : [net_params]
}
