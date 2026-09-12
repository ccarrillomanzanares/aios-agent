#!/usr/bin/env python3
"""aio-download — download the AIOS local model with a real progress bar.

Used by setup.py (live and install) and runnable on its own.

  from aio_download import download_model, check_can_run_local, MODEL

Design notes:
  * Direct write to the FINAL destination (the target disk when installing, so
    the file is never copied twice; ~/models in live).
  * Downloads to <dest>.part and renames on completion, so an interrupted
    download never looks complete.
  * Resumes with an HTTP Range request if a .part file is already there.
  * Verifies the total size against Content-Length before renaming.
  * Pure stdlib (urllib) — no curl/wget dependency.
"""
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# --------------------------------------------------------------------------- #
# The model AIOS ships with
# --------------------------------------------------------------------------- #

MODEL = {
    "name": "Qwen3.6-35B-A3B",
    "file": "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf",
    "url": ("https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/"
            "resolve/main/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"),
    # 22 134 528 992 bytes (verified with curl -sIL 2026-09-12)
    "bytes": 22134528992,
    "size_label": "22.1 GB",
    # Reference machine where the speed below was measured
    "ref_cpu": "AMD EPYC, 16 cores @ 3.2 GHz",
    "ref_ram": "62 GB",
    "ref_speed": "~9 tokens/second",
    # Recommended minimum to offer it without being misleading
    "min_cores": 8,
    "min_ram_gb": 16,
}

# Where the model lives once installed / in live
MODELS_DIR = Path("/usr/local/share/aios/models")


# --------------------------------------------------------------------------- #
# Hardware check
# --------------------------------------------------------------------------- #

def detect_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024)
    except Exception:
        pass
    return 0


def detect_cores():
    return os.cpu_count() or 0


def _free_space_gb(path):
    try:
        p = Path(path)
        while not p.exists() and p != p.parent:
            p = p.parent
        return shutil.disk_usage(p).free / (1024 ** 3)
    except Exception:
        return 0.0


def check_can_run_local(dest_dir=None):
    """Decide whether to offer the local model on THIS machine.

    Returns (verdict, message) where verdict is:
      "ok"      — meets the recommended minimum
      "tight"   — below it, but might work (warn, let the user decide)
      "no"      — cannot work (too little RAM / not enough free space)
    """
    cores = detect_cores()
    ram = detect_ram_gb()
    need_gb = MODEL["bytes"] / (1024 ** 3)

    # Space: the model file must fit where it is going
    where = dest_dir or MODELS_DIR.parent
    free = _free_space_gb(where)
    if free and free < need_gb * 1.05:
        return "no", (f"Not enough free space: {free:.0f} GB available, "
                      f"{need_gb:.1f} GB needed.")

    # RAM: the model is streamed from disk, but the KV cache and the process
    # need room. Below ~8 GB there is no realistic chance.
    if ram < 8:
        return "no", (f"This computer has {ram} GB of RAM. The model needs at "
                      f"least {MODEL['min_ram_gb']} GB to run at all "
                      f"(recommended), and will not work with {ram} GB.")

    if cores < MODEL["min_cores"] or ram < MODEL["min_ram_gb"]:
        return "tight", (f"This computer has {cores} cores and {ram} GB of RAM. "
                         f"Recommended: {MODEL['min_cores']} cores and "
                         f"{MODEL['min_ram_gb']} GB. It may work, but it will be slow.")
    return "ok", (f"This computer has {cores} cores and {ram} GB of RAM "
                  f"(recommended: {MODEL['min_cores']}+ cores, "
                  f"{MODEL['min_ram_gb']}+ GB).")


# --------------------------------------------------------------------------- #
# Progress bar
# --------------------------------------------------------------------------- #

def _human(n):
    """Decimal units (1000-based), matching how HuggingFace and browsers report
    file sizes -- so the progress bar shows the same '22.1 GB' as the label."""
    if n < 1000:
        return f"{n:.1f} B"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1000
        if n < 1000:
            return f"{n:.1f} {unit}"
    return f"{n:.1f} PB"


def _bar(done, total, width=40):
    if not total:
        return f"[{'?' * width}]"
    frac = min(1.0, done / total)
    filled = int(frac * width)
    return f"[{'#' * filled}{'.' * (width - filled)}]"


def format_progress(done, total, elapsed, width=40):
    """One status line: bar, percent, downloaded/total, speed, ETA."""
    bar = _bar(done, total, width)
    pct = (done / total * 100) if total else 0.0
    speed = done / elapsed if elapsed > 0 else 0
    line = (f"  {bar} {pct:5.1f}%  {_human(done)}"
            f"{'/' + _human(total) if total else ''}")
    if speed > 0:
        line += f"  {_human(speed)}/s"
        if total and done < total:
            eta = (total - done) / speed
            if eta < 3600:
                line += f"  ETA {int(eta // 60)}m{int(eta % 60):02d}s"
            else:
                line += f"  ETA {eta / 3600:.1f}h"
    return line


# --------------------------------------------------------------------------- #
# Download
# --------------------------------------------------------------------------- #

def download_model(dest_dir=None, url=None, expected_bytes=None, label=None):
    """Download the model into dest_dir. Returns (ok, path_or_error).

    Writes to <file>.part first, resumes if it exists, verifies the final size
    and only then renames. Prints a live progress line.
    """
    url = url or MODEL["url"]
    expected = expected_bytes if expected_bytes is not None else MODEL["bytes"]
    fname = label or MODEL["file"]

    dest_dir = Path(dest_dir or MODELS_DIR)
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"cannot create {dest_dir}: {e}"

    final = dest_dir / fname
    part = dest_dir / (fname + ".part")

    if final.exists():
        size = final.stat().st_size
        if not expected or size == expected:
            return True, str(final)
        # Wrong size: start over
        final.unlink()

    resume = part.stat().st_size if part.exists() else 0
    req = urllib.request.Request(url, headers={"User-Agent": "AIOS-Downloader/1.0"})
    if resume:
        req.add_header("Range", f"bytes={resume}-")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = expected
            if resp.headers.get("Content-Length"):
                cl = int(resp.headers["Content-Length"])
                total = cl + resume if resume and resp.status == 206 else cl
            if resume and resp.status != 206:
                # Server ignored the Range: restart from scratch
                resume = 0
                total = expected

            mode = "ab" if resume else "wb"
            done = resume
            t0 = time.time()
            last = 0.0
            with open(part, mode) as f:
                while True:
                    chunk = resp.read(1024 * 512)   # 512 KB
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    if now - last >= 0.2:          # refresh ~5x/second
                        last = now
                        line = format_progress(done, total, now - t0)
                        sys.stdout.write("\r" + line + " " * 8)
                        sys.stdout.flush()
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} {e.reason}"
    except urllib.error.URLError as e:
        return False, f"network error: {e.reason}"
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        return False, "cancelled by the user (partial file kept, it will resume)"
    except OSError as e:
        return False, f"write error: {e}"

    done = part.stat().st_size
    sys.stdout.write("\r" + format_progress(done, total or done, time.time() - t0) + "\n")
    sys.stdout.flush()

    if expected and done != expected:
        return False, (f"incomplete download: got {done} bytes, expected {expected}. "
                       f"The partial file was kept; run again to resume.")

    try:
        part.replace(final)
    except OSError as e:
        return False, f"cannot move into place: {e}"
    return True, str(final)


def describe_model():
    """The spec text shown before downloading."""
    m = MODEL
    return [
        "  AIOS uses a local AI model that runs on your own computer.",
        "  No GPU is needed.",
        "",
        f"  Model:      {m['name']}",
        f"  Download:   {m['size_label']} ({m['bytes']:,} bytes)".replace(",", " "),
        "",
        "  Recommended minimum:",
        f"    CPU:  {m['min_cores']} cores",
        f"    RAM:  {m['min_ram_gb']} GB",
        "",
        "  Reference machine (where the speed below was measured):",
        f"    {m['ref_cpu']}, {m['ref_ram']} RAM  ->  {m['ref_speed']}",
        "",
        "  Below that minimum AIOS still works, but it will be slow.",
        "  Cloud mode needs no download and no minimum hardware.",
    ]


if __name__ == "__main__":
    # Standalone: show specs + machine check, then download.
    dest = sys.argv[1] if len(sys.argv) > 1 else str(MODELS_DIR)
    print("\n".join(describe_model()))
    verdict, msg = check_can_run_local(dest)
    print(f"\n  {msg}\n")
    if verdict == "no":
        print("  This machine cannot run the local model.")
        sys.exit(1)
    ok, res = download_model(dest)
    if ok:
        print(f"  Saved to {res}")
        sys.exit(0)
    print(f"  FAILED: {res}")
    sys.exit(1)
