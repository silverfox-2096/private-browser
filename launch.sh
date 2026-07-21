#!/bin/bash
# Start the stack and open the VNC web UI once it responds.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
docker compose up -d
# wait for the web UI to respond before opening the browser
ready=0
for i in {1..30}; do
  curl -sk -o /dev/null https://127.0.0.1:7814 && { ready=1; break; }
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  echo "Stack did not become ready in 30s -- not opening the browser." >&2
  echo "Check:  docker ps   and   docker logs gluetun" >&2
  exit 1
fi
xdg-open https://127.0.0.1:7814 2>/dev/null || echo "Open https://127.0.0.1:7814"
