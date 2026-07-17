# strace y ltrace

## strace
```bash
strace -p PID
strace -f -o /tmp/trace.log comando
strace -e open,read,write comando
```

## ltrace
```bash
ltrace -p PID
ltrace -f comando
```
