#!/bin/bash
# Start the stack and open the VNC web UI once it responds.
# Ready = Gluetun healthy AND Firefox running AND the web UI answering, all within one
# 30 s deadline. An old UI still answering does not count if compose itself failed.
set -uo pipefail
cd "$(dirname "$(readlink -f "$0")")" || exit 1

GLUETUN=gluetun-proton
FIREFOX=private-firefox
UI=https://127.0.0.1:7814

# Web auth needs the htpasswd file to exist first. If it is missing, Docker would
# create an empty directory at the mount point and the web login would break confusingly.
if [ -d webauth-htpasswd ]; then
  echo "webauth-htpasswd is a DIRECTORY, not a file -- Docker created it from a" >&2
  echo "missing-file mount on an earlier run. Remove it, then regenerate the credential:" >&2
  echo "  rm -r webauth-htpasswd   (then follow README Setup)" >&2
  exit 1
fi
if [ ! -f webauth-htpasswd ]; then
  echo "Missing webauth-htpasswd -- generate it first (see README Setup)." >&2
  exit 1
fi
if ! docker compose up -d; then
  echo "docker compose up failed -- not opening the browser." >&2
  exit 1
fi

# One overall deadline (SECONDS), including sleeps and request time.
end=$((SECONDS + 30)); ready=0
while [ "$SECONDS" -lt "$end" ]; do
  if [ "$(docker inspect -f '{{.State.Health.Status}}' "$GLUETUN" 2>/dev/null)" = healthy ] &&
     [ "$(docker inspect -f '{{.State.Running}}' "$FIREFOX" 2>/dev/null)" = true ] &&
     curl -sk -f -o /dev/null --max-time 2 "$UI"; then
    ready=1; break
  fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "Stack did not become ready in 30s -- not opening the browser." >&2
  echo "Check:  docker ps   and   docker logs $GLUETUN" >&2
  exit 1
fi
xdg-open "$UI" 2>/dev/null || echo "Open $UI"
