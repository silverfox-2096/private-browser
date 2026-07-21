#!/bin/bash
# Start the stack and open the VNC web UI once it responds.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
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
docker compose up -d
# wait for the web UI to respond before opening the browser
ready=0
for _ in {1..30}; do
  curl -sk -o /dev/null https://127.0.0.1:7814 && { ready=1; break; }
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "Stack did not become ready in 30s -- not opening the browser." >&2
  echo "Check:  docker ps   and   docker logs gluetun" >&2
  exit 1
fi
xdg-open https://127.0.0.1:7814 2>/dev/null || echo "Open https://127.0.0.1:7814"
