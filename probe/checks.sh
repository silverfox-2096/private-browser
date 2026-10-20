#!/usr/bin/env bash
set -euo pipefail
# Step 2 (14-automation-plan): headless browser checks -- UA, RFP, WebGL, exit IP,
# WebRTC, DNS leak (bash.ws), CreepJS fields. Grown from spike.sh; same method:
# a SECOND, headless Firefox on a COPY of the live profile (GUI untouched), driven
# by checks.mjs from a node sidecar in the VPN namespace.
#
# Usage: [OUT=dir] [RECORD=1] checks.sh [EXPECTED_FIREFOX_VERSION]
# Exit 0 = all PASS, 1 = any FAIL, 3 = INCOMPLETE (not a pass; RECORD=1 always ends 3).
# OUT defaults to the vault tmp/pbc (manual runs); pb-autoupdate.sh passes its own.
# Needs the stack up. Starts creepjs-server (compose profile "test") and removes it
# again unless it was already running.

here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
expect="${1:-}"
out="${OUT:-$here/../../tmp/pbc}"
mkdir -p "$out"
out="$(cd "$out" && pwd)"  # docker -v needs an absolute path (relative = named volume)
STACK="$HOME/docker/private-browser"
FF=private-firefox
NET=gluetun-proton
CJ=creepjs-server

policy_rc=0
python3 "$STACK/check-local-app-policy.py" --policy-file "$STACK/local-app-post-rules.txt" || policy_rc=$?
case "$policy_rc" in
  0) ;;
  1) exit 1 ;;
  3) exit 3 ;;
  *) echo "INCOMPLETE  local-app policy: checker unavailable (exit $policy_rc)" >&2; exit 3 ;;
esac

cj_was_up=0
[ "$(docker inspect -f '{{.State.Running}}' "$CJ" 2>/dev/null)" = true ] && cj_was_up=1

cleanup() {  # kill only the headless instance (its cmdline names hlprof), not this shell
  docker exec "$FF" sh -c 'for p in /proc/[0-9]*; do n=${p#/proc/};
    [ "$n" = "$$" ] && continue;
    grep -qs hlprof "$p/cmdline" && kill "$n"; done;
    rm -rf /tmp/hlprof /tmp/hlhome' 2>/dev/null || true
  if [ "$cj_was_up" -eq 0 ]; then
    (cd "$STACK" && docker compose --profile test rm -sf creepjs) >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "1/4 creepjs-server: (re)create in the current Gluetun namespace"
# Recreate even if running: after a Gluetun restart it sits in a dead namespace.
(cd "$STACK" && docker compose --profile test up -d --no-deps --force-recreate creepjs)

echo "2/4 copy the live profile once the FF_PREF_* handler is done (up to 60 s)"
# /config is a tmpfs, so each container (re)start rebuilds the profile, and verify.sh
# restarts the container just before this runs. jlesage's FF_PREF_* handler touches an
# empty prefs.js, then appends one pref at a time: "prefs.js exists" is not enough.
# Copying early lost resistFingerprinting (2026-10-07: rfpTimeZone UTC, cores 32).
# The handler is done when every pref it writes is there (its rules: empty value
# skipped, =UNSET removed), or when Firefox, which starts only after it, has saved
# prefs.js (header line). The second case matters: Firefox's save drops any pref equal
# to its default, so "every FF_PREF_* pref present" can stay false for good.
for i in $(seq 1 30); do
  docker exec -u 1000 "$FF" sh -c 'f=$(find /config -name prefs.js 2>/dev/null | head -n1);
    [ -n "$f" ] || exit 1;
    if grep -q "^// Mozilla User Preferences" "$f"; then how="Firefox has saved prefs.js";
    else
      env | grep "^FF_PREF_" | while IFS= read -r e; do
        v=${e#*=}; [ -n "$v" ] || continue;
        case "$v" in *=*) [ "${v#*=}" = UNSET ] && continue ;; esac;
        grep -qF "user_pref(\"${v%%=*}\"," "$f" || exit 1;
      done || exit 1;
      how="all present";
    fi;
    echo "   live profile: ${f%/prefs.js} ($(env | grep -c "^FF_PREF_") FF_PREF_* vars; handler done: $how)";
    rm -rf /tmp/hlprof /tmp/hlhome; cp -r "${f%/prefs.js}" /tmp/hlprof;
    rm -f /tmp/hlprof/lock /tmp/hlprof/.parentlock; mkdir -p /tmp/hlhome' && break
  [ "$i" -eq 30 ] && { echo "FAIL: prefs.js under /config missing, or FF_PREF_* handler not done, after 60 s"; exit 1; }
  sleep 2
done

echo "3/4 start headless Firefox"
docker exec -d -u 1000 -e HOME=/tmp/hlhome "$FF" \
  firefox --headless --no-remote --profile /tmp/hlprof --remote-debugging-port 9222

echo "4/4 checks via a node sidecar in the VPN namespace (~1-2 min)"
docker run --rm --user "$(id -u):$(id -g)" --network "container:$NET" \
  -e EXPECT="$expect" -e RECORD="${RECORD:-}" -v "$here:/w:ro" -v "$out:/out" \
  node:22-slim node /w/checks.mjs
