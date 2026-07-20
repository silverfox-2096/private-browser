#!/bin/bash
# Stack updater -- replaces "docker compose pull", which no longer updates the
# custom-built Firefox image (it is built locally, not pulled).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
docker compose build --pull firefox
docker compose --profile test pull creepjs
docker compose up -d
echo
docker images jlesage/firefox --format 'base: {{.ID}} {{.CreatedAt}}'
echo
echo "UPDATED. The new Firefox base image may change your fingerprint."
echo "RE-AUDIT: docker compose --profile test up -d creepjs"
echo "  then open http://localhost:8080 in the container browser."
echo "Bump the 'Last verified' line in README.md once you have re-checked."
