#!/bin/bash
# Start the stack and open the VNC web UI once it responds.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
docker compose up -d
# wait for the web UI to respond before opening the browser
for i in {1..30}; do
  curl -sk -o /dev/null https://127.0.0.1:7814 && break
  sleep 1
done
xdg-open https://127.0.0.1:7814 2>/dev/null || echo "Open https://127.0.0.1:7814"
