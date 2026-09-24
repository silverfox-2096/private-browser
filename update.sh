#!/bin/bash
# Stack updater -- replaces "docker compose pull", which no longer updates the
# custom-built Firefox image (it is built locally, not pulled).
# Prints UPDATED only after every step below has been confirmed; otherwise it names
# the step that failed and exits 1.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")" || exit 1

GLUETUN=gluetun-proton
FIREFOX=private-firefox
IMG=private-firefox:mozilla
UI=https://127.0.0.1:7814

die() { echo "FAILED: $1" >&2; echo "Not updated. Check: docker ps; docker logs $GLUETUN" >&2; exit 1; }

# --no-cache: Firefox is installed from Mozilla's APT repo in a RUN step, and the
# layer cache would otherwise reuse that step and never pick up a new release.
docker compose build --pull --no-cache firefox || die "image build"
docker compose --profile test pull creepjs || die "pull of the creepjs test image"
docker compose up -d || die "docker compose up"

# One overall deadline per wait (SECONDS), including sleeps and request time.
end=$((SECONDS + 90)); health=starting
while [ "$SECONDS" -lt "$end" ]; do
  health=$(docker inspect -f '{{.State.Health.Status}}' "$GLUETUN" 2>/dev/null || echo missing)
  [ "$health" = healthy ] && break
  sleep 2
done
[ "$health" = healthy ] || die "$GLUETUN not healthy after 90 s ($health)"

# Compose can report Started without recreating: the running container must be the
# image just built.
built=$(docker image inspect -f '{{.Id}}' "$IMG" 2>/dev/null || true)
run=$(docker inspect -f '{{.Image}}' "$FIREFOX" 2>/dev/null || true)
if [ -z "$built" ] || [ "$run" != "$built" ]; then die "$FIREFOX is not running the image just built"; fi

ver=$(docker exec "$FIREFOX" firefox --version 2>/dev/null || true)
[ -n "$ver" ] || die "firefox --version returned nothing inside $FIREFOX"

end=$((SECONDS + 30)); ui=0
while [ "$SECONDS" -lt "$end" ]; do
  curl -sk -f -o /dev/null --max-time 2 "$UI" && { ui=1; break; }
  sleep 1
done
[ "$ui" -eq 1 ] || die "web UI at $UI did not answer within 30 s"

echo
echo "$ver"
echo
echo "UPDATED. A new Firefox or base image may change your fingerprint."
echo "RE-AUDIT: docker compose --profile test up -d creepjs"
echo "  then open http://localhost:8080 in the container browser, and run ./verify.sh."
echo "Once re-checked, bump \"Runtime & leak-tested\" at the top of README.md."
