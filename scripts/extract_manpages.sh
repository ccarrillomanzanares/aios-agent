#!/bin/bash
set -euo pipefail
OUT="/home/ccmai/sre-copilot/data/external"
mkdir -p "$OUT"

man_to_md() {
    local name="$1"
    local file="$2"
    local out="$OUT/${file}"
    if man "$name" > /dev/null 2>&1; then
        echo "Extracting manpage: $name -> $file"
        {
            echo "# Manpage: $name"
            echo ""
            MANWIDTH=80 man "$name" | col -b || true
        } > "$out"
    else
        echo "Missing manpage: $name"
    fi
}

man_to_md systemctl man_systemctl.txt
man_to_md journalctl man_journalctl.txt
man_to_md systemd.service man_systemd.service.txt
man_to_md systemd.unit man_systemd.unit.txt
man_to_md systemd-networkd.service man_systemd-networkd.service.txt
man_to_md ss man_ss.txt
man_to_md lsof man_lsof.txt
man_to_md fail2ban man_fail2ban.txt
man_to_md rsyslogd man_rsyslogd.txt
man_to_md logrotate man_logrotate.txt
man_to_md xtables-nft man_xtables-nft.txt
man_to_md sshd_config man_sshd_config.txt
man_to_md ssh_config man_ssh_config.txt
man_to_md crontab man_crontab.txt
man_to_md chronyc man_chronyc.txt

echo "Done."
