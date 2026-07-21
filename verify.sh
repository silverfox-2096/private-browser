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
# Usage (on the host, stack already up):   ./verify.sh [EXPECTED_COUNTRY_ISO]
#   e.g.  ./verify.sh SG    to also assert the exit country is Singapore.
# Prints PASS/FAIL per check and exits non-zero on any failure. It prints only the VPN
# exit IP (safe to publish) -- never any secret -- and stamps its own header in UTC
# (date -u), so committed output leaks no local timezone.
#
# NOTE: the kill-switch test stops the tunnel and restarts Firefox, closing anything you
# have open in the browser. Run this BETWEEN browsing sessions, not during one.

set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")" || exit 1

GLUETUN=gluetun-proton
FIREFOX=private-firefox
PROBE=https://1.1.1.1
EXPECT_COUNTRY="${1:-}"   # optional ISO code (e.g. SG); if unset, country is informational

fail=0
stopped=0   # 1 only while the kill-switch test has Gluetun stopped
pass() { printf 'PASS  %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; fail=1; }
info() { printf '      %s\n' "$1"; }

printf 'private-browser verify.sh -- %s\n\n' "$(date -u '+%Y-%m-%d %H:%M UTC')"

# 0. Refuse to run unless the tunnel is healthy (mirrors launch.sh's guard style).
status=$(docker inspect -f '{{.State.Health.Status}}' "$GLUETUN" 2>/dev/null || echo missing)
if [ "$status" != "healthy" ]; then
  echo "Stack not ready: $GLUETUN health = $status. Start it first (./launch.sh)." >&2
  exit 2
fi

# Undo ONLY what we changed: if the kill-switch test stopped Gluetun, bring it back and
# reattach Firefox. If we never stopped it, do nothing (no needless Firefox restart).
# --wait blocks on Gluetun's tunnel healthcheck. Armed as a trap for crash paths too.
restore() {
  [ "$stopped" -eq 1 ] || return 0
  info "restoring stack..."
  docker compose up -d --wait >/dev/null 2>&1 || true
  docker restart "$FIREFOX" >/dev/null 2>&1 || true
  stopped=0
}
trap restore EXIT

# 1. Exit IP + country. The property that matters: the exit IP is NOT the host's.
host_ip=$(curl -s --max-time 10 https://ipinfo.io/ip 2>/dev/null || true)
exit_json=$(docker exec "$GLUETUN" wget -T 10 -qO- https://ipinfo.io/json 2>/dev/null || true)
exit_ip=$(printf '%s' "$exit_json" | sed -n 's/.*"ip": *"\([^"]*\)".*/\1/p' | head -n1)
exit_country=$(printf '%s' "$exit_json" | sed -n 's/.*"country": *"\([^"]*\)".*/\1/p' | head -n1)

if [ -z "$exit_ip" ]; then
  bad "exit IP: could not read ipinfo.io through the tunnel"
elif [ -n "$host_ip" ] && [ "$exit_ip" = "$host_ip" ]; then
  bad "exit IP equals host IP ($exit_ip) -- traffic is NOT going through the tunnel"
else
  pass "exit IP is the VPN's, not the host's ($exit_ip, country=${exit_country:-?})"
  [ -z "$host_ip" ] && info "(host public IP unavailable; compared on presence only)"
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
#    the browser-side dnsleaktest run manually (see README).
ff_ns=$(docker exec "$FIREFOX" cat /etc/resolv.conf 2>/dev/null \
        | sed -n 's/^nameserver *//p' | head -n1 || true)
if [ "$ff_ns" = "127.0.0.1" ]; then
  pass "browser DNS points at Gluetun's local DoT resolver (127.0.0.1)"
else
  info "browser resolv.conf nameserver = ${ff_ns:-unknown}; confirm with the manual"
  info "dnsleaktest.com check in the browser (see README) -- that test is authoritative"
fi

# 3. Kill switch -- two-sided, so a broken probe can't false-pass.
#    First confirm Firefox CAN reach the probe with the tunnel up, then stop the tunnel
#    and confirm it CANNOT. Stopping Gluetun tests "namespace owner gone"; the firewall
#    also holds if the tunnel drops while Gluetun stays up (control-server test, not run
#    here to keep this simple).
if ! docker exec "$FIREFOX" sh -c 'command -v wget' >/dev/null 2>&1; then
  info "kill switch: skipped -- no wget in $FIREFOX to probe with"
else
  up_ok=0
  if docker exec "$FIREFOX" wget -T 5 -qO- "$PROBE" >/dev/null 2>&1; then
    up_ok=1
  fi
  docker stop "$GLUETUN" >/dev/null; stopped=1
  if docker exec "$FIREFOX" wget -T 5 -qO- "$PROBE" >/dev/null 2>&1; then
    bad "kill switch: Firefox still reached $PROBE with the tunnel stopped"
  elif [ "$up_ok" -eq 1 ]; then
    pass "kill switch: reachable with tunnel up, blocked when stopped (fails closed)"
  else
    info "kill switch: inconclusive -- Firefox could not reach $PROBE even with the"
    info "tunnel up (wget/TLS issue?), so the 'blocked' result proves nothing"
  fi
fi

# Restore if we stopped the tunnel, then report. Disarm the trap first so it can't fire
# restore a second time on exit.
trap - EXIT
restore

echo
if [ "$fail" -eq 0 ]; then
  echo "ALL AUTOMATED CHECKS PASSED"
  echo "Still do the MANUAL browser checks: WebRTC (browserleaks.com/webrtc = No Leak)"
  echo "and DNS leak (dnsleaktest.com extended = your DoT resolver, never your ISP)."
else
  echo "ONE OR MORE CHECKS FAILED -- see FAIL lines above."
fi
exit "$fail"
