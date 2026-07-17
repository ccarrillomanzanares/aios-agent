# perf y flame graphs

## perf
```bash
sudo perf record -g -p PID
sudo perf report -g graph
```

## Flame graph
```bash
sudo perf record -F 99 -a -g -- sleep 30
sudo perf script | stackcollapse-perf.pl | flamegraph.pl > perf.svg
```
