#!/bin/bash
# Esperar a que la red responda DE VERDAD antes de sincronizar la base de paquetes.
#
# Medido: con systemd-networkd + resolved, sven-sync arrancaba 5 s despues del arranque y el
# DNS todavia no respondia -> los 3 repos caian con "Temporary failure in name resolution".
# `network-online.target` no ayuda aqui porque systemd-networkd-wait-online no esta instalado.
#
# Se comprueba resolucion de nombres Y una descarga real: hay redes donde el DNS responde
# antes que el trafico. Nunca se sale con error: si la red no llega, se deja intentar el sync
# igualmente (sven se queja mejor de lo que podemos hacerlo nosotros, y no queremos un
# ExecStartPre que bloquee el arranque para siempre).
HOSTS="mirror.rackspace.com archlinux.org geo.mirror.pkgbuild.com"
MAX_ESPERA="${SVEN_ESPERA_MAX:-90}"

resuelve() {
    for h in $HOSTS; do
        getent hosts "$h" >/dev/null 2>&1 && return 0
    done
    return 1
}

hay_red() {
    resuelve || return 1
    # una peticion minima y con tope de tiempo: si el DNS miente, esto lo delata
    curl -fsS --max-time 8 -o /dev/null https://archlinux.org/ 2>/dev/null && return 0
    return 1
}

t0=$(date +%s)
while :; do
    if hay_red; then
        echo "sven-esperar-red: red lista tras $(( $(date +%s) - t0 ))s"
        exit 0
    fi
    if [ $(( $(date +%s) - t0 )) -ge "$MAX_ESPERA" ]; then
        echo "sven-esperar-red: la red no respondio en ${MAX_ESPERA}s; se intenta el sync igual"
        exit 0
    fi
    sleep 2
done
