#!/usr/bin/env bash
# Stub tests for the maintained updater and browser wrapper; no real Docker/notifications.
# docker/curl are exported bash functions; HOME is a temp dir, so nothing real is touched
# and no Pushover message is sent.
# Usage: bash test-pba.sh [path/to/pb-autoupdate.sh]   (default: beside this file)
set -uo pipefail
PBA="$(readlink -f "${1:-$(dirname "$(readlink -f "$0")")/pb-autoupdate.sh}")"
SD=$(mktemp -d)
trap 'rm -rf "$SD"' EXIT
export SD

docker() {
  echo "docker $*" >>"$SD/calls"
  case "$1" in
    run) case "$*" in
      *checks.mjs*) return "${S_NODE_RC:-0}" ;;           # probe/checks.sh node sidecar
      *) echo "Mozilla Firefox 157.0" ;;                 # ff_version of an image
    esac ;;
    tag) echo "$*" >>"$SD/tags" ;;
    compose)
      case "$*" in
        *build*) [ -f "$HOME/docker/private-browser/maintenance/active" ] || return 99
          return "${S_BUILD_RC:-0}" ;;
        *down*) return "${S_DOWN_RC:-0}" ;;
        *up*) echo x >>"$SD/ups"; return 0 ;;
      esac ;;
    inspect)
      local n; n=$(wc -l <"$SD/ups" 2>/dev/null || echo 0)
      case "$3" in
        *Health*)  # the 2nd "up" is settle's: S_SETTLE_HEALTH applies from then on
          if [ "$n" -ge 2 ]; then echo "${S_SETTLE_HEALTH:-healthy}"; else echo healthy; fi ;;
        *Running*) echo "${S_WAS_UP:-true}" ;;
        *Image*) echo sha256:new ;;
      esac ;;
    image) echo sha256:new ;;
    exec)
      case "$*" in
        *firefox\ --version*) echo "Mozilla Firefox 157.0" ;;
        *cat\ /proc/net/tcp*)
          [ "${S_SOCKETS_RC:-0}" = 0 ] || return "$S_SOCKETS_RC"
          if [ "${S_TABS:-0}" = 1 ]; then echo ' 0: 00000000:16A8 0100007F:1234 01 '; fi ;;
        *) return "${S_GATE_EXEC_RC:-0}" ;;                                             # /proc/net/tcp: no tabs
      esac ;;
  esac
}
curl() {
  case "$*" in
    *pushover*) cat >/dev/null; echo "$*" >>"$SD/notes" ;;
    *http_code*) echo "${S_GATE_CODE:-503}" ;;
    *product-details*) echo '{"LATEST_FIREFOX_VERSION": "157.0"}' ;;
  esac
}
sleep() { SECONDS=$((SECONDS + ${1%%.*})); }
export -f docker curl sleep

H="$SD/home"
mkdir -p "$H/docker/private-browser" "$H/.config" "$H/.local/share/pb-autoupdate"
printf 'PUSHOVER_TOKEN=t\nPUSHOVER_USER=u\n' >"$H/.config/private-browser-upkeep.env"  # precommit-allow-secret: fake stub values
# verify.sh / checks.sh stand-ins: print a line, exit with the requested code.
# shellcheck disable=SC2016 # Variables expand when the generated fixture runs.
printf '%s\n' 'echo "${S_VOUT:-PASS  all}"; exit "${S_VRC:-0}"' >"$H/docker/private-browser/verify.sh"
# shellcheck disable=SC2016 # Variables expand when the generated fixture runs.
printf '%s\n' 'echo "${S_COUT:-PASS  ua: ok}"; exit "${S_CRC:-0}"' >"$H/.local/share/pb-autoupdate/checks.sh"

cat > "$H/docker/private-browser/check-local-app-policy.py" <<'POLICY_STUB'
import os, sys
rc = int(os.environ.get("S_POLICY_RC", "0"))
print(("PASS" if rc == 0 else "FAIL" if rc == 1 else "INCOMPLETE") + "  local-app policy: fixture")
sys.exit(rc)
POLICY_STUB
pass=0; failn=0
# t NAME WANT_RC MUST_IN_NOTES MUST_NOT_IN_NOTES env...
t() {
  local name=$1 want=$2 must=$3 mustnot=$4; shift 4
  rm -rf "$SD"/calls "$SD"/ups "$SD"/notes "$SD"/tags "$H/.local/state"
  local out rc why=''
  out=$(env HOME="$H" FORCE=1 "$@" bash "$PBA" 2>&1); rc=$?
  [ "$rc" = "$want" ] || why="rc=$rc want $want"
  [ -z "$must" ] || command grep -qE -- "$must" "$SD/notes" 2>/dev/null || why="$why; no alert /$must/"
  [ -z "$mustnot" ] || ! command grep -qE -- "$mustnot" "$SD/notes" 2>/dev/null || why="$why; unwanted alert /$mustnot/"
  if [ -z "$why" ]; then pass=$((pass+1)); echo "ok    $name"
  else failn=$((failn+1)); echo "FAIL  $name: $why"; printf '%s\n' "$out" | sed 's/^/        | /'
    sed 's/^/        notes| /' "$SD/notes" 2>/dev/null; fi
}
N=_=_

t "success, stack back up"            0 'title=Private Browser: Firefox 157.0 installed' 'DOWN|FAILED' $N
t "success, stack does NOT come back" 0 'stack is DOWN.*priority=1'  ''        S_SETTLE_HEALTH=unhealthy
t "verify INCOMPLETE rolls back"      3 'verify.sh INCOMPLETE'       'installed' S_VRC=3
t "verify FAIL rolls back"            1 'verify.sh failed \(exit 1\)' 'installed' S_VRC=1
t "old grep gone: exit 0 is enough"   0 'installed'                  'FAILED'  "S_VOUT=PASS        kill switch (new spacing)"
t "checks INCOMPLETE is named"        3 'browser checks INCOMPLETE'         'installed' "S_COUT=INCOMPLETE  dnsLeak: no resolver identity" S_CRC=3
t "fail + stack does not come back"   1 'stack is DOWN'              ''        S_VRC=1 S_SETTLE_HEALTH=unhealthy
t "was down, compose down fails"      0 'stack left running'         ''        S_WAS_UP=false S_DOWN_RC=1

t "open viewer defers"                0 'Firefox 157.0 ready' 'installed|FAILED' S_TABS=1
env HOME="$H" FORCE=1 S_TABS=1 bash "$PBA" >/dev/null 2>&1
if [ "$(wc -l < "$SD/notes")" = 1 ] && [ ! -e "$H/docker/private-browser/maintenance/active" ] && ! command grep -q 'compose build' "$SD/calls"; then
  pass=$((pass+1)); echo 'ok    deferred notification once per version; no build; gate released'
else failn=$((failn+1)); echo 'FAIL deferred notification repeated or session disturbed'; fi
t "gate not active aborts"             1 '' 'installed' S_GATE_CODE=200
t "old image aborts"                   1 '' 'installed' S_GATE_EXEC_RC=1
t "unreadable sockets aborts"          1 '' 'installed' S_SOCKETS_RC=1
if [ -e "$H/docker/private-browser/maintenance/active" ]; then
  failn=$((failn+1)); echo 'FAIL gate leaked after abort'
else pass=$((pass+1)); echo 'ok    gate removed after abort'; fi

# Rollback must re-tag :prev as the live image.
rm -rf "$SD"/tags "$SD"/ups "$H/.local/state"
env HOME="$H" FORCE=1 S_VRC=3 bash "$PBA" >/dev/null 2>&1
if command grep -q 'tag private-firefox:prev private-firefox:mozilla' "$SD/tags" 2>/dev/null; then
  pass=$((pass+1)); echo "ok    rollback re-tags :prev"
else failn=$((failn+1)); echo "FAIL  rollback did not re-tag :prev"; fi

# probe/checks.sh must pass checks.mjs's exit code through (3 = INCOMPLETE, not a pass).
CS="$(dirname "$PBA")/../probe/checks.sh"
for want in 0 1 3; do
  env HOME="$H" OUT="$SD/out" S_NODE_RC=$want bash "$CS" >/dev/null 2>&1; rc=$?
  if [ "$rc" = "$want" ]; then pass=$((pass+1)); echo "ok    checks.sh passes exit $want through"
  else failn=$((failn+1)); echo "FAIL  checks.sh: checks.mjs exit $want became $rc"; fi
done

for want in 1 3; do
  env HOME="$H" OUT="$SD/out" S_POLICY_RC=$want S_NODE_RC=0 bash "$CS" >"$SD/policy-out" 2>&1; rc=$?
  if [ "$rc" = "$want" ] && ! command grep -q '4/4 checks' "$SD/policy-out"; then
    pass=$((pass+1)); echo "ok    broken policy verdict $want survives wrapper despite healthy browser stub"
  else failn=$((failn+1)); echo "FAIL policy wrapper verdict $want became $rc"; fi
done

echo
echo "pb-autoupdate: $pass passed, $failn failed"
[ "$failn" -eq 0 ]
