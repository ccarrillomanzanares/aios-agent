# Sysdig y Falco

## Sysdig
```bash
sudo sysdig -c topprocs_cpu
sudo sysdig proc.name=nginx
```

## Falco
```yaml
- rule: Terminal shell in container
  condition: spawned_process and container and shell_procs
  output: "Shell en contenedor"
  priority: WARNING
```
