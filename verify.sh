#!/bin/bash
# verify.sh -- runtime checks for the private-browser stack.
#
# Automates the CONTAINER-NETWORK-LEVEL checks from the README "Verify it works":
#   1. the exit IP is the VPN's, not the host's (privacy property)
#   2. DNS is pointed at Gluetun's local DoT resolver, not the LAN (best-effort)
#   3. the kill switch blocks Firefox when the tunnel drops
#
# It deliberately does NOT test in-browser WebRTC or the browser-side DNS-leak page:
# those need a real browser running JS and stay MANUAL (see README). A script cannot
# honestly prove them, so it does not claim to.
#
# Usage (on the host, stack already up):   [REAL_IP=a.b.c.d] ./verify.sh [EXPECTED_COUNTRY_ISO]
#   e.g.  ./verify.sh SG    to also assert the exit country is Singapore.
#   REAL_IP: the IPv4 address your ISP gives you. Set it when the host itself is behind a
#   VPN, where the host's current public IP is not your real one. It is never printed.
# Each check ends PASS, FAIL, or INCOMPLETE. INCOMPLETE means the evidence could not be
# collected, and it is never counted as a pass. Exit codes: 0 = every check passed,
# 1 = at least one FAIL, 3 = no FAIL but at least one INCOMPLETE, 2 = stack not ready.
# It prints only the VPN exit IP (safe to publish) -- never the host IP or any secret --
# and stamps its own header in UTC (date -u), so committed output leaks no local timezone.
#
# NOTE: the kill-switch test stops the tunnel and restarts Firefox, closing anything you
# have open in the browser. Run this BETWEEN browsing sessions, not during one.

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")" || exit 1

GLUETUN=gluetun-proton
FIREFOX=private-firefox
CREEPJS=creepjs-server   # optional test profile; shares Gluetun's netns
PROBE=https://1.1.1.1
EXPECT_COUNTRY="${1:-}"   # optional ISO code (e.g. SG); if unset, country is informational

fail=0
incomplete=0
stopped=0   # 1 from just BEFORE Gluetun is stopped until it is restored
pass() { printf 'PASS  %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; fail=1; }
inc()  { printf 'INCOMPLETE  %s\n' "$1"; incomplete=1; }
info() { printf '      %s\n' "$1"; }
running() { [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]; }
retry() { "$@" || { sleep 2; "$@"; }; }   # one retry for flaky lookups
is_ipv4() {
  local IFS=. o
  [[ "$1" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] || return 1
  for o in $1; do [ "$((10#$o))" -le 255 ] || return 1; done
}
probe() { docker exec "$FIREFOX" wget -T 5 -qO- "$PROBE" >/dev/null 2>&1; }

printf 'private-browser verify.sh -- %s\n\n' "$(date -u '+%Y-%m-%d %H:%M UTC')"

# 0. Refuse to run unless the tunnel is healthy (mirrors launch.sh's guard style).
status=$(docker inspect -f '{{.State.Health.Status}}' "$GLUETUN" 2>/dev/null || echo missing)
if [ "$status" != "healthy" ]; then
  echo "Stack not ready: $GLUETUN health = $status. Start it first (./launch.sh)." >&2
  exit 2
fi

# Undo ONLY what we changed: if the kill-switch test stopped Gluetun, bring it back and
# reattach Firefox (and CreepJS, which is left in the dead namespace otherwise). If we
# never stopped it, do nothing. Every step is checked, and Firefox must reach the probe
# again: a stack left down or offline after a "passing" run is itself a failure.
restore() {
  [ "$stopped" -eq 1 ] || return 0
  stopped=0
  info "restoring stack..."
  local ok=1 i
  timeout 180 docker compose up -d --wait >/dev/null 2>&1 || ok=0
  docker restart "$FIREFOX" >/dev/null 2>&1 || ok=0
  if running "$CREEPJS"; then docker restart "$CREEPJS" >/dev/null 2>&1 || ok=0; fi
  running "$FIREFOX" || ok=0
  if [ "$ok" -ne 1 ]; then
    bad "restore: the stack did not come back cleanly. Run by hand:"
    info "docker compose up -d --wait && docker restart $FIREFOX"
    return 0
  fi
  for i in 1 2 3 4 5 6; do   # Firefox's container needs a few seconds after restart
    probe && { info "stack restored; Firefox reaches $PROBE again"; return 0; }
    [ "$i" -lt 6 ] && sleep 5
  done
  bad "post-restore connectivity check failed: Firefox could not reach $PROBE"
}
# EXIT covers normal ends and set -e aborts; INT/TERM are routed through EXIT so an
# interrupted run (Ctrl+C mid kill-switch test) still restores the tunnel.
trap 'exit 130' INT TERM
trap 'restore' EXIT

# 1. Exit IP + country. The property that matters: the exit IP is NOT the host's.
#    Both sides are compared as IPv4, so a v4 host IP is never compared with a v6 exit.
#    Without a valid comparison address there is nothing to compare against: INCOMPLETE.
exit_json=$(retry docker exec "$GLUETUN" wget -T 10 -qO- https://ipinfo.io/json 2>/dev/null || true)
exit_ip=$(printf '%s' "$exit_json" | sed -n 's/.*"ip": *"\([^"]*\)".*/\1/p' | head -n1)
exit_country=$(printf '%s' "$exit_json" | sed -n 's/.*"country": *"\([^"]*\)".*/\1/p' | head -n1)

cmp_ip=''
if [ -n "${REAL_IP:-}" ]; then
  if is_ipv4 "$REAL_IP"; then
    cmp_ip=$REAL_IP
    info "comparing the exit IP against REAL_IP (not printed)"
  else
    info "REAL_IP is set but is not a valid IPv4 address; it was not used"
  fi
else
  cmp_ip=$(retry curl -4 -s --max-time 10 https://ipinfo.io/ip 2>/dev/null || true)
  is_ipv4 "$cmp_ip" || cmp_ip=''
  info "comparing against this host's current public IPv4 (not printed). If the host"
  info "is itself behind a VPN, set REAL_IP= to your ISP-assigned address instead."
fi

if [ -z "$exit_ip" ]; then
  bad "exit IP: could not read ipinfo.io through the tunnel"
elif ! is_ipv4 "$exit_ip"; then
  inc "exit IP: the tunnel exit is not an IPv4 address, so it was not compared"
elif [ -n "${REAL_IP:-}" ] && [ -z "$cmp_ip" ]; then
  inc "exit IP: REAL_IP is malformed, so the tunnel exit ($exit_ip) was not compared"
elif [ -z "$cmp_ip" ]; then
  inc "exit IP: host public IPv4 unavailable, so the tunnel exit ($exit_ip) was not compared"
elif [ "$exit_ip" = "$cmp_ip" ]; then
  # Do not print the address: here it IS the real IP.
  bad "exit IP equals the host/REAL_IP address: comparison FAILED, traffic may not be tunnelled"
else
  pass "exit IP differs from the host/REAL_IP address ($exit_ip, country=${exit_country:-?})"
fi

if [ -n "$EXPECT_COUNTRY" ]; then
  if [ "$exit_country" = "$EXPECT_COUNTRY" ]; then
    pass "exit country = $exit_country (matches expected $EXPECT_COUNTRY)"
  else
    bad "exit country = ${exit_country:-?}, expected $EXPECT_COUNTRY"
  fi
fi

# 2. DNS -- best effort. The browser's own resolv.conf should point at Gluetun's local
#    DoT proxy (127.0.0.1). This is a sanity check, not proof: the authoritative test is
#    the browser-side dnsleaktest run manually (see README). Anything else is unproven.
ff_ns=$(docker exec "$FIREFOX" cat /etc/resolv.conf 2>/dev/null \
        | sed -n 's/^nameserver *//p' | head -n1 || true)
if [ "$ff_ns" = "127.0.0.1" ]; then
  pass "browser DNS points at Gluetun's local DoT resolver (127.0.0.1)"
else
  inc "browser resolv.conf nameserver = ${ff_ns:-unreadable}, expected 127.0.0.1"
  info "confirm with the manual dnsleaktest.com check in the browser (see README)"
fi

# 3. Kill switch -- two-sided, so a broken probe can't false-pass.
#    First confirm Firefox CAN reach the probe with the tunnel up, then stop the tunnel
#    and confirm it CANNOT. "Cannot" must be a network-level failure from wget itself
#    (GNU wget exit 4) inside a Firefox container that is still running. Any other
#    result -- the container gone, docker exec failing, wget missing -- proves nothing,
#    so INCOMPLETE. Stopping Gluetun tests "namespace owner gone"; the firewall also
#    holds if the tunnel drops while Gluetun stays up (control-server test, not run here).
if ! docker exec "$FIREFOX" sh -c 'command -v wget' >/dev/null 2>&1; then
  inc "kill switch: no wget in $FIREFOX to probe with"
elif ! probe; then
  inc "kill switch: Firefox could not reach $PROBE even with the tunnel up, so a"
  info "'blocked' result would prove nothing (not tested)"
else
  stopped=1
  docker stop "$GLUETUN" >/dev/null
  rc=0; probe || rc=$?
  if [ "$rc" -eq 0 ]; then
    bad "kill switch: Firefox still reached $PROBE with the tunnel stopped"
  elif ! running "$FIREFOX"; then
    inc "kill switch: $FIREFOX is not running, so the failed probe proves nothing"
  elif [ "$rc" -eq 4 ]; then
    pass "kill switch: reachable with tunnel up; with it stopped, the request failed"
    info "at the network level (wget exit 4; cause not identified)"
  else
    inc "kill switch: probe exited $rc, not a wget network failure (4); not a proof"
  fi
fi

# Restore if we stopped the tunnel, then report. Disarm the trap first so it can't fire
# restore a second time on exit.
trap - EXIT
restore

echo
if [ "$fail" -ne 0 ]; then
  echo "ONE OR MORE CHECKS FAILED -- see FAIL lines above."
  exit 1
elif [ "$incomplete" -ne 0 ]; then
  echo "INCOMPLETE -- not a pass. See INCOMPLETE lines above."
  exit 3
fi
echo "ALL AUTOMATED CHECKS PASSED"
echo "Still do the MANUAL browser checks: WebRTC (browserleaks.com/webrtc = No Leak)"
echo "and DNS leak (dnsleaktest.com extended = your DoT resolver, never your ISP)."
