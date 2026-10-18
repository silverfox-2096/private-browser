#!/bin/sh
# Gate ALL GUI initialization, including engine auto-restarts that bypass Compose.
# The pinned Gluetun implementation starts its health server after installing the
# firewall, and returns 200 only after a successful tunnel health check.
# Local requests only; no proxy, redirects, DNS lookup or external probe here.
set -eu
trap 'exit 143' TERM
trap 'exit 130' INT
printf '%s\n' 'Waiting for the local VPN tunnel readiness check before starting the browser.'
for _ in $(seq 1 60); do
    if [ -e /sys/class/net/tun0 ]; then
        # A literal loopback TCP request avoids HTTP-client redirect/proxy paths.
        # Ignore the body and require exactly the local health endpoint's status.
        # shellcheck disable=SC2016 # The status variable belongs to the child Bash.
        if timeout 3 /bin/bash --noprofile --norc -c '
            exec 3<>/dev/tcp/127.0.0.1/9999 || exit 1
            printf "GET / HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n" >&3
            IFS= read -r status <&3 || exit 1
            [[ "$status" =~ ^HTTP/1\.[01][[:space:]]200[[:space:]] ]]
        ' 2>/dev/null && [ -e /sys/class/net/tun0 ]; then
            printf '%s\n' 'VPN readiness confirmed; starting the browser.'
            exec /init
        fi
    fi
    sleep 1 &
    wait "$!"
done
printf '%s\n' 'VPN readiness was not established; browser initialization refused.' >&2
exit 1
