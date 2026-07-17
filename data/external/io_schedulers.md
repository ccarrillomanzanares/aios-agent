# I/O schedulers

## Ver y cambiar
```bash
cat /sys/block/sda/queue/scheduler
echo mq-deadline | sudo tee /sys/block/sda/queue/scheduler
```

## Schedulers
- none: para NVMe
- mq-deadline: equilibrio
- kyber: latencia predecible
- bfq: interactivo
