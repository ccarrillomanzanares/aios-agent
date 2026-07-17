# zram y zswap

## zram
```bash
sudo modprobe zram num_devices=1
sudo zramctl /dev/zram0 --algorithm zstd --size 4G
sudo mkswap /dev/zram0
sudo swapon -p 100 /dev/zram0
```

## zswap
```bash
echo zstd | sudo tee /sys/module/zswap/parameters/compressor
echo 20 | sudo tee /sys/module/zswap/parameters/max_pool_percent
```
