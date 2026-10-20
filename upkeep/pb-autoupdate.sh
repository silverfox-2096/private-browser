#!/usr/bin/env bash
set -euo pipefail
# Rebuild the private browser when Mozilla ships a new Firefox (14-automation-plan, step 1).
#
# Daily via pb-autoupdate.timer. Does nothing unless Mozilla's current release differs
# from the one in private-firefox:mozilla. It never touches a browser that is in use:
# if a web-UI tab is connected, it sends one Pushover notice per version and retries
# the next day. Otherwise: tag the old image :prev, rebuild, start the stack, check the
# image identity + version, run verify.sh + the headless browser checks, roll back to :prev on any failure, put the
# stack back as it was (up or down), and send the result via Pushover.
#
# PUSHOVER_TOKEN / PUSHOVER_USER come from the systemd EnvironmentFile
# (~/.config/private-browser-upkeep.env, shared with the monthly reminder).
# Manual test run (browser closed; env loaded below):  FORCE=1 ~/.local/bin/pb-autoupdate.sh

STACK="$HOME/docker/private-browser"
IMG=private-firefox:mozilla
PREV=private-firefox:prev
FF=private-firefox
GLUETUN=gluetun-proton
COUNTRY=SG
STATE="$HOME/.local/state/pb-autoupdate"
CHECKS="$HOME/.local/share/pb-autoupdate/checks.sh"  # installed from probe/ by install-pba.sh
FORCE="${FORCE:-0}"
GATE="$STACK/maintenance/active"
gate_owned=0

# Run by hand (not via systemd): load the Pushover creds from the same file.
if [ -z "${PUSHOVER_TOKEN:-}" ]; then
  set -a
  # Runtime file outside the repo; nothing for shellcheck to follow.
  # shellcheck source=/dev/null
  . "$HOME/.config/private-browser-upkeep.env"
  set +a
fi

mkdir -p "$STATE"
exec 9>"$STATE/lock"
flock -n 9 || { echo "another run is in progress"; exit 0; }
cd "$STACK"
# Holding the lock proves any flag left by an earlier process is stale.
rm -f "$GATE"

# Token and user go through curl's stdin config, not argv (visible in ps).
notify() {  # $1 title, $2 message, $3 priority
  local fmt='form-string = "token=%s"\nform-string = "user=%s"\n'  # precommit-allow-secret: format string, no value
  # shellcheck disable=SC2059
  printf "$fmt" "$PUSHOVER_TOKEN" "$PUSHOVER_USER" |
    curl -s --max-time 20 -o /dev/null -K - \
      --form-string "title=$1" --form-string "message=$2" \
      --form-string "priority=${3:-0}" https://api.pushover.net/1/messages.json \
    || echo "pushover send failed"
}

ff_version() {  # $1 image -> "156.0"
  docker run --rm --network none --entrypoint firefox "$1" --version 2>/dev/null |
    sed -n 's/^Mozilla Firefox //p' || true
}

latest=$(curl -s --max-time 20 \
  https://product-details.mozilla.org/1.0/firefox_versions.json |
  sed -n 's/.*"LATEST_FIREFOX_VERSION": *"\([^"]*\)".*/\1/p' || true)
if [ -z "$latest" ]; then
  echo "could not read Mozilla's latest version (offline?); retry next run"
  exit 0
fi
current=$(ff_version "$IMG")
echo "installed=${current:-?} latest=$latest force=$FORCE"
if [ "$current" = "$latest" ] && [ "$FORCE" != 1 ]; then
  exit 0
fi
# One failed attempt per version: no daily rebuild + alert loop. FORCE=1 retries.
if [ "$(cat "$STATE/failed" 2>/dev/null)" = "$latest" ] && [ "$FORCE" != 1 ]; then
  echo "update to $latest already failed; fix, then run with FORCE=1"
  exit 0
fi

# Block new requests BEFORE checking for existing sessions. Existing WebSockets
# keep running and remain visible in /proc/net/tcp. The directory bind mount keeps
# the gate active through rebuilds, container restarts and verify.sh's kill test.
# A crash leaves a safe 503; the next lock-owning run removes its stale flag.
release_gate() { if [ "$gate_owned" = 1 ]; then rm -f "$GATE"; fi; }
trap release_gate EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "${GATE%/*}"
: > "$GATE"
gate_owned=1

# "In use" = a web-UI tab is connected, not just the container running (it stays up
# after the tab closes). Counts ESTABLISHED (01) sockets on local port 5800 (16A8) in
# the shared netns; tested 2026-09-21: tab open = 7, tab closed = 0.
was_up=0
tabs=0
if [ "$(docker inspect -f '{{.State.Running}}' "$FF" 2>/dev/null)" = true ]; then
  was_up=1
  # Refuse on an old image or a missing mount; do not claim the gate works.
  if ! docker exec "$FF" test -f /run/private-browser-maintenance/active ||
     ! docker exec "$FF" grep -qF 'include /opt/base/etc/nginx/private-browser-maintenance.conf;' /opt/base/etc/nginx/default_site.conf; then
    echo "maintenance gate unavailable; deploy the updated image and compose mount first" >&2
    exit 1
  fi
  # Verify a new request really is blocked. Connection: close avoids counting our
  # own check as a connected viewer. Any unreadable socket table aborts safely.
  code=$(curl -sk --max-time 5 -H 'Connection: close' -o /dev/null -w '%{http_code}' https://127.0.0.1:7814 || true)
  [ "$code" = 503 ] || { echo "maintenance gate did not return 503 (got ${code:-nothing})" >&2; exit 1; }
  sockets=$(docker exec "$FF" cat /proc/net/tcp /proc/net/tcp6) || { echo "cannot inspect connected viewers" >&2; exit 1; }
  tabs=$(printf '%s\n' "$sockets" |
    grep -cE '^ *[0-9]+: [0-9A-F]+:16A8 [0-9A-F]+:[0-9A-F]+ 01 ' || true)
fi
if [ "$tabs" -gt 0 ]; then
  release_gate
  gate_owned=0
  echo "browser in use ($tabs web-UI connections); not updating"
  if [ "$(cat "$STATE/notified" 2>/dev/null)" != "$latest" ]; then
    notify "Private Browser: Firefox $latest ready" \
      "Installed ${current:-?}. Close the private browser; the update runs at the next daily check, or run: systemctl --user start pb-autoupdate"
    echo "$latest" > "$STATE/notified"
  fi
  exit 0
fi

log="$STATE/run-$(date +%Y%m%d-%H%M).log"
echo "full log: $log"
docker tag "$IMG" "$PREV"

settle() {  # leave the stack as we found it; up -d recreates onto whatever $IMG is now
  # Checked, not assumed: a stack that was up and did not come back gets a priority-1
  # alert, even after a successful update.
  local ok=1 h='' end
  if [ "$was_up" -eq 1 ]; then
    docker compose up -d >>"$log" 2>&1 || ok=0
    end=$((SECONDS + 90))
    while [ "$ok" -eq 1 ] && [ "$SECONDS" -lt "$end" ]; do
      h=$(docker inspect -f '{{.State.Health.Status}}' "$GLUETUN" 2>/dev/null || true)
      [ "$h" = healthy ] && break
      sleep 2
    done
    [ "$h" = healthy ] && [ "$(docker inspect -f '{{.State.Running}}' "$FF" 2>/dev/null)" = true ] || ok=0
    if [ "$ok" -ne 1 ]; then
      echo "settle: stack is DOWN (gluetun=${h:-?})" | tee -a "$log"
      notify "Private Browser: stack is DOWN" \
        "It was running before this update run and did not come back (gluetun=${h:-?}). Run launch.sh. Log: $log" 1
    fi
  else
    if ! docker compose down >>"$log" 2>&1; then
      echo "settle: compose down failed" | tee -a "$log"
      notify "Private Browser: stack left running" \
        "It was stopped before this update run, and compose down failed. Log: $log" 1
    fi
  fi
}

fail() {  # roll back to :prev, restore the stack's up/down state, alert
  echo "FAIL: $1" | tee -a "$log"
  echo "$latest" > "$STATE/failed"
  docker tag "$PREV" "$IMG"
  settle
  notify "Private Browser: update FAILED" \
    "$1. Rolled back to Firefox ${current:-?}. Log: $log" 1
  exit "${2:-1}"
}

docker compose build --pull --no-cache firefox >>"$log" 2>&1 || fail "build failed"
new=$(ff_version "$IMG")
if [ "$new" = "$current" ] && [ "$FORCE" != 1 ]; then
  # Mozilla's APT repo can publish hours after product-details.
  echo "APT still serves $new; keeping it, retry next run" | tee -a "$log"
  exit 0
fi

docker compose up -d >>"$log" 2>&1 || fail "stack did not start"
health=starting
for _ in $(seq 1 45); do
  health=$(docker inspect -f '{{.State.Health.Status}}' "$GLUETUN" 2>/dev/null || true)
  [ "$health" = healthy ] && break
  sleep 2
done
[ "$health" = healthy ] || fail "gluetun not healthy after 90s ($health)"

# The running container must be the image just built (compose can say Started
# without recreating), and the browser inside must report the new version.
[ "$(docker inspect -f '{{.Image}}' "$FF")" = "$(docker image inspect -f '{{.Id}}' "$IMG")" ] \
  || fail "private-firefox is not running the new image"
running=$(docker exec "$FF" firefox --version 2>/dev/null | sed -n 's/^Mozilla Firefox //p')
[ "$running" = "$new" ] || fail "running Firefox reports ${running:-?}, built $new"

# Trust verify.sh's exit code, not its text: 0 = all PASS, 3 = INCOMPLETE (not a pass).
vrc=0
bash verify.sh "$COUNTRY" >>"$log" 2>&1 || vrc=$?
case "$vrc" in
  0) ;;
  3) fail "verify.sh INCOMPLETE (evidence missing, not a pass)" 3 ;;
  *) fail "verify.sh failed (exit $vrc)" ;;
esac

# Headless browser checks (step 2): UA, RFP, WebGL, exit IP, WebRTC, DNS leak, CreepJS
# fields vs baseline. Non-disruptive; a second Firefox on a copy of the profile.
brc=0
OUT="$STATE/checks-$(date +%Y%m%d-%H%M)" bash "$CHECKS" "$new" >>"$log" 2>&1 || brc=$?
case "$brc" in
  0) ;;
  3) fail "browser checks INCOMPLETE (evidence missing, not a pass)" 3 ;;
  *) fail "browser checks failed (exit $brc)" ;;
esac

settle
rm -f "$STATE/failed"
echo "$latest" > "$STATE/notified"
notify "Private Browser: Firefox $new installed" \
  "Was ${current:-?}. verify.sh passed (exit IP, $COUNTRY, DNS, kill switch); browser checks passed (WebRTC, DNS leak, CreepJS fields)."
echo "OK: $current -> $new" | tee -a "$log"
