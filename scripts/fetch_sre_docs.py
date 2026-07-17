#!/usr/bin/env python3
"""Descarga documentación SRE de fuentes públicas permitidas.

Descarga selectiva, respetando rate limits, para construir el corpus RAG.
Fuentes: systemd.io, ArchWiki (selectivo), TLDP (selectivo), docker docs.
"""
import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlparse

import requests


USER_AGENT = "SRE-Copilot-Dataset-Bot/0.1 (educational; private VPS)"
TIMEOUT = 30

SOURCES = {
    "systemd.md": "https://raw.githubusercontent.com/systemd/systemd/main/README.md",
    "systemd-networkd.md": "https://raw.githubusercontent.com/systemd/systemd/main/man/systemd.network.xml",
    "nginx.md": "https://raw.githubusercontent.com/nginx/nginx/master/README.md",
    "docker.md": "https://raw.githubusercontent.com/docker/docs/main/content/manuals/engine/_index.md",
    "prometheus.md": "https://raw.githubusercontent.com/prometheus/prometheus/main/README.md",
    "linux-kernel-sysctl.md": "https://raw.githubusercontent.com/torvalds/linux/master/Documentation/admin-guide/sysctl/kernel.rst",
    "bash_scripting_safe.md": "local",
    "sre_copilot_metadata.md": "local",
    "command_examples.md": "local",
    "proc_filesystem.md": "https://raw.githubusercontent.com/torvalds/linux/master/Documentation/filesystems/proc.rst",
    "nftables.md": "https://wiki.nftables.org/wiki-nftables/index.php/Main_Page",
    "fail2ban.md": "https://raw.githubusercontent.com/fail2ban/fail2ban/master/README.md",
    "ansible.md": "https://raw.githubusercontent.com/ansible/ansible-documentation/main/docs/docsite/rst/getting_started/index.rst",
}


def fetch(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="/home/ccmai/sre-copilot/data/external")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    for filename, url in SOURCES.items():
        if url == "local":
            # Archivos gestionados manualmente, no descargar
            continue
        try:
            text = fetch(url)
            (out_dir / filename).write_text(text, encoding="utf-8")
            manifest[filename] = {"url": url, "bytes": len(text.encode("utf-8"))}
            print(f"✓ {filename}")
            time.sleep(1)
        except Exception as e:
            print(f"✗ {filename}: {e}")
            manifest[filename] = {"url": url, "error": str(e)}

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nDescargados {len([v for v in manifest.values() if 'error' not in v])}/{len(SOURCES)}")


if __name__ == "__main__":
    main()
