# Ansible

## Inventario
```ini
[web]
web1 ansible_host=192.168.1.10

[web:vars]
ansible_user=admin
```

## Comando ad-hoc
```bash
ansible web -m ping
ansible web -a "uptime"
```

## Playbook
```yaml
- name: Instalar Nginx
  hosts: web
  become: yes
  tasks:
    - apt:
        name: nginx
        state: present
    - service:
        name: nginx
        state: started
        enabled: yes
```
