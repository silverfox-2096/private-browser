#!/bin/bash
# Stack updater -- replaces "docker compose pull", which no longer updates the
# custom-built Firefox image (it is built locally, not pulled).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
# --no-cache: Firefox is installed from Mozilla's APT repo in a RUN step, and the
# layer cache would otherwise reuse that step and never pick up a new release.
docker compose build --pull --no-cache firefox
docker compose --profile test pull creepjs
docker compose up -d
echo
docker exec private-firefox firefox --version 2>/dev/null
echo
echo "UPDATED. A new Firefox or base image may change your fingerprint."
echo "RE-AUDIT: docker compose --profile test up -d creepjs"
echo "  then open http://localhost:8080 in the container browser."
echo "Bump the 'Last verified' line in README.md once you have re-checked."
