#!/usr/bin/env bash
# Failure-path tests for the host scripts, with docker/curl stubbed as exported bash
# functions (no Docker, no network, nothing written outside a temp dir).
# Usage: ci/test-scripts.sh [DIR]   DIR holds verify.sh, update.sh, launch.sh and ci/ (default: repo root).
# Exit 0 = every case behaved as expected. Run against the pre-review-4 scripts, it fails.
# The stubs below are reached only through export -f, which ShellCheck cannot see.
# shellcheck disable=SC2317
set -uo pipefail

DIR="$(cd "${1:-$(dirname "$(readlink -f "$0")")/..}" && pwd)"
SD=$(mktemp -d)
trap 'rm -rf "$SD"' EXIT
export SD
HOST=198.51.100.7     # documentation addresses (RFC 5737), never real ones
EXIT_IP=203.0.113.9
REAL=192.0.2.44

# ---- stubs -------------------------------------------------------------------
docker() {
  echo "docker $*" >>"$SD/calls"
  case "$1" in
    inspect)
      case "$3" in
        *Health*) echo "${S_HEALTH:-healthy}" ;;
        *Image*) echo "${S_RUN_IMG-sha256:new}" ;;
        *Running*)
          case "$4" in
            private-firefox) if [ -f "$SD/stopped" ]; then echo "${S_FF_RUN_STOPPED:-true}"; else echo true; fi ;;
            creepjs-server) echo "${S_CREEP:-false}" ;;
            *) echo true ;;
          esac ;;
      esac ;;
    exec)
      case "$2 $3" in
        "gluetun-proton wget") printf "%s" "${S_EXIT_JSON-$DEF_JSON}"; return "${S_EXIT_RC:-0}" ;;
        "private-firefox cat") echo "nameserver ${S_NS:-127.0.0.1}" ;;
        "private-firefox firefox") printf '%s' "${S_FFVER-Mozilla Firefox 156.0.1}" ;;
        "private-firefox sh") [ "${S_WGET:-1}" = 1 ] ;;
        "pbfp-firefox firefox") echo "Mozilla Firefox 156.0.1" ;;
        "pbfp-firefox grep") return "${S_PREF_RC:-0}" ;;
        "private-firefox wget")
          if [ -f "$SD/stopped" ]; then return "${S_PROBE_DOWN:-4}"
          elif [ -f "$SD/restored" ]; then return "${S_PROBE_RESTORED:-0}"
          else return "${S_PROBE_UP:-0}"; fi ;;
      esac ;;
    stop)
      touch "$SD/stopped"
      [ "${S_INT:-0}" = 1 ] && kill -INT $$
      return 0 ;;
    compose)
      case "$*" in
        *build*) return "${S_BUILD_RC:-0}" ;;
        *pull*) return "${S_PULL_RC:-0}" ;;
        *--wait*)   # verify restore; S_INT_RESTORE = Ctrl+C while it runs
          [ "${S_INT_RESTORE:-0}" = 1 ] && kill -INT $$
          rm -f "$SD/stopped"; touch "$SD/restored"; return "${S_COMPOSE_RC:-0}" ;;
        *up*) return "${S_UP_RC:-0}" ;;
      esac ;;
    run) return "${S_NODE_RC:-0}" ;;                    # ci/fingerprint.sh: node checks.mjs
    image) echo "${S_BUILT_IMG-sha256:new}" ;;
    restart) echo "$2" >>"$SD/restarts" ;;
  esac
}
# The web UI (:7814) and the host-IP lookup share the curl stub. S_UI_SECS = seconds a
# UI request "takes" (a hung server bounded only by --max-time).
curl() {
  echo "curl $*" >>"$SD/calls"
  case "$*" in
    *7814*) SECONDS=$((SECONDS + ${S_UI_SECS:-0}))
      # An HTTP error status only fails curl when -f is given (real curl behaviour).
      if [ "${S_UI_HTTPERR:-0}" = 1 ]; then case " $* " in *" -f "*) return 22 ;; *) return 0 ;; esac; fi
      return "${S_UI_RC:-0}" ;;
    *codeload*) echo x >>"$SD/downloads"; printf tgz; return "${S_CJ_RC:-0}" ;;
    *) printf '%s' "${S_HOST_IP-$HOST}"; return "${S_HOST_RC:-0}" ;;
  esac
}
# tar -xz -C DIR ...: "extracts" creep.js unless S_CJ_EMPTY=1.
tar() { cat >/dev/null; [ "${S_CJ_EMPTY:-0}" = 1 ] || touch "$3/creep.js"; }
timeout() { echo "timeout $*" >>"$SD/calls"; shift; "$@"; }   # logged: bounded calls are checked
sleep() { SECONDS=$((SECONDS + ${1%%.*})); }   # simulated clock: deadlines expire, instantly
xdg-open() { echo "xdg-open $*" >>"$SD/calls"; }
export -f docker curl tar timeout sleep xdg-open
DEF_JSON=$(printf '{"ip": "%s", "country": "SG"}' "$EXIT_IP")
export HOST EXIT_IP DEF_JSON

# ---- runner ------------------------------------------------------------------
pass=0; failn=0
# t NAME WANT_RC [grep-pattern-that-must-appear] [pattern-that-must-NOT-appear] -- env...
t() {
  local name=$1 want=$2 must=${3:-} mustnot=${4:-}; shift 4
  rm -f "$SD"/stopped "$SD"/restored "$SD"/calls "$SD"/restarts
  local out rc
  # shellcheck disable=SC2086  # ARGS is empty or one word, split on purpose
  out=$(env "$@" bash "$W/$SCRIPT" $ARGS 2>&1); rc=$?
  local why=''
  [ "$rc" = "$want" ] || why="rc=$rc want $want"
  [ -z "$must" ] || printf '%s' "$out" | command grep -qE -- "$must" || why="$why; missing /$must/"
  [ -z "$mustnot" ] || ! printf '%s' "$out" | command grep -qE -- "$mustnot" || why="$why; found /$mustnot/"
  [ ! -f "$SD/stopped" ] || why="$why; tunnel left stopped"
  if [ -z "$why" ]; then pass=$((pass+1)); echo "ok    $name"
  else failn=$((failn+1)); echo "FAIL  $name: $why"; printf '%s\n' "$out" | sed 's/^/        | /'; fi
}
N=_=_   # placeholder env when a case needs none

# Scripts run from a scratch copy: launch.sh needs a webauth-htpasswd beside it.
W="$SD/w"; mkdir -p "$W"
for s in verify.sh update.sh launch.sh; do [ -f "$DIR/$s" ] && cp "$DIR/$s" "$W/"; done
touch "$W/webauth-htpasswd"
mkdir -p "$W/ci" && cp -r "$DIR/ci/fingerprint.sh" "$DIR/ci/pins" "$W/ci/"

echo "== verify.sh"
SCRIPT=verify.sh ARGS=SG

t "all good"                        0 '^PASS  kill switch'         "$HOST"  $N
t "host IP unavailable"             3 '^INCOMPLETE  exit IP'       ''       S_HOST_IP= S_HOST_RC=6
t "exit IP = host IP"               1 'comparison FAILED'          "$HOST"  S_HOST_IP=$EXIT_IP
t "tunnel exit unreadable"          1 '^FAIL  exit IP'             ''       S_EXIT_JSON= S_EXIT_RC=1
t "wrong country"                   1 '^FAIL  exit country'        ''       "S_EXIT_JSON={\"ip\": \"$EXIT_IP\", \"country\": \"DE\"}"
t "resolv.conf not local"           3 '^INCOMPLETE  browser'       ''       S_NS=192.168.1.1
t "no wget"                         3 'no wget'                    '^PASS  kill' S_WGET=0
t "probe fails with tunnel up"      3 'even with the tunnel up'    ''       S_PROBE_UP=4
t "probe succeeds, tunnel down"     1 'still reached'              ''       S_PROBE_DOWN=0
t "Firefox gone after stop"         3 'is not running'             '^PASS  kill' S_FF_RUN_STOPPED=false
t "probe down rc not 4"             3 'exited 1, not a wget'       '^PASS  kill' S_PROBE_DOWN=1
t "restore compose fails"           1 '^FAIL  restore'             ''       S_COMPOSE_RC=1
t "host lookup returns IPv6"        3 'IPv4 unavailable'           '2001:db8' S_HOST_IP=2001:db8::1
t "tunnel exit is IPv6"             3 'not an IPv4 address'        ''       "S_EXIT_JSON={\"ip\": \"2001:db8::9\", \"country\": \"SG\"}"
t "REAL_IP malformed"               3 'REAL_IP is malformed'       '999\.1' REAL_IP=999.1.1.1
t "REAL_IP = exit IP"               1 'comparison FAILED'          ''       REAL_IP=$EXIT_IP
t "REAL_IP valid, differs"          0 'against REAL_IP'            "$REAL"  REAL_IP=$REAL
t "post-restore probe fails"        1 'post-restore connectivity check failed' '' S_PROBE_RESTORED=4
# The exit address is printed only on request, and only once it is shown to differ.
HOSTJSON=$(printf '{"ip": "%s", "country": "SG"}' "$HOST")
t "exit IP hidden by default"       0 '^PASS  exit IP'             "$EXIT_IP" $N
t "SHOW_EXIT_IP=1 prints it on PASS" 0 "^PASS  exit IP.*$EXIT_IP"  ''       SHOW_EXIT_IP=1
t "host lookup fails, exit = host"  3 '^INCOMPLETE  exit IP'       "$HOST"  S_HOST_IP= S_HOST_RC=6 "S_EXIT_JSON=$HOSTJSON"
t "REAL_IP malformed, exit = host"  3 'REAL_IP is malformed'       "$HOST"  REAL_IP=999.1.1.1 "S_EXIT_JSON=$HOSTJSON"
t "SHOW_EXIT_IP=1, not compared"    3 '^INCOMPLETE  exit IP'       "$HOST"  SHOW_EXIT_IP=1 S_HOST_IP= S_HOST_RC=6 "S_EXIT_JSON=$HOSTJSON"
# Only canonical dotted-quad IPv4 is compared: leading zeros would compare as unequal strings.
t "REAL_IP with leading zeros"      3 'REAL_IP is malformed'       '^PASS  exit IP' REAL_IP=203.000.113.009
t "host lookup with leading zeros"  3 'IPv4 unavailable'           '^PASS  exit IP' S_HOST_IP=203.000.113.009

# Cases that inspect the stub call log, not just the output.
rm -f "$SD"/calls "$SD"/restarts "$SD"/stopped
env S_CREEP=true bash "$W/verify.sh" SG >/dev/null 2>&1
if command grep -qx creepjs-server "$SD/restarts" 2>/dev/null; then pass=$((pass+1)); echo "ok    creepjs restarted after restore"
else failn=$((failn+1)); echo "FAIL  creepjs restarted after restore: not restarted"; fi

if command grep -q '^curl -4 ' "$SD/calls" 2>/dev/null; then pass=$((pass+1)); echo "ok    host IP lookup is IPv4-only (curl -4)"
else failn=$((failn+1)); echo "FAIL  host IP lookup is IPv4-only: no curl -4 call"; fi

rm -f "$SD"/calls
env REAL_IP=$REAL bash "$W/verify.sh" SG >/dev/null 2>&1
if ! command grep -q '^curl ' "$SD/calls" 2>/dev/null; then pass=$((pass+1)); echo "ok    REAL_IP set: no host lookup"
else failn=$((failn+1)); echo "FAIL  REAL_IP set: host lookup still made"; fi

# Ctrl+C in the middle of the kill-switch test: the tunnel must be restored.
rm -f "$SD"/stopped "$SD"/restored "$SD"/restarts
env S_INT=1 bash "$W/verify.sh" SG >/dev/null 2>&1; rc=$?
if [ "$rc" = 130 ] && [ ! -f "$SD/stopped" ] && command grep -qx private-firefox "$SD/restarts" 2>/dev/null; then
  pass=$((pass+1)); echo "ok    Ctrl+C mid kill switch restores the stack (rc 130)"
else failn=$((failn+1)); echo "FAIL  Ctrl+C mid kill switch: rc=$rc, stopped=$([ -f "$SD/stopped" ] && echo yes || echo no)"; fi

# Ctrl+C while the stack is being restored: recovery must finish before the exit, both on
# the normal path and inside the EXIT trap (a second Ctrl+C after one mid kill switch).
for v in S_INT_RESTORE=1 "S_INT=1 S_INT_RESTORE=1"; do
  rm -f "$SD"/stopped "$SD"/restored "$SD"/restarts
  # shellcheck disable=SC2086  # $v is one or two VAR=value words, split on purpose
  env $v bash "$W/verify.sh" SG >/dev/null 2>&1; rc=$?
  if [ "$rc" = 130 ] && [ ! -f "$SD/stopped" ] && command grep -qx private-firefox "$SD/restarts" 2>/dev/null; then
    pass=$((pass+1)); echo "ok    Ctrl+C during restore ($v): restore finished, rc 130"
  else failn=$((failn+1)); echo "FAIL  Ctrl+C during restore ($v): rc=$rc, stopped=$([ -f "$SD/stopped" ] && echo yes || echo no)"; fi
done

# Once the tunnel is down, every docker call must be bounded: the stub logs "timeout ..."
# on the line before each call it wraps.
rm -f "$SD"/calls "$SD"/stopped "$SD"/restarts
env S_CREEP=true bash "$W/verify.sh" SG >/dev/null 2>&1
unb=$(awk '/^docker (stop|restart|compose|exec private-firefox wget)/ && prev !~ /^timeout / {print} {prev=$0}' "$SD/calls")
if [ -z "$unb" ] && command grep -q '^docker restart' "$SD/calls"; then pass=$((pass+1)); echo "ok    stop/restore/probe docker calls are bounded by timeout"
else failn=$((failn+1)); echo "FAIL  unbounded docker calls:"; printf '%s\n' "$unb" | sed 's/^/        | /'; fi

echo
echo "== update.sh"
SCRIPT=update.sh ARGS=
t "update: all good"                0 '^UPDATED'                   ''         $N
t "update: build fails"             1 'FAILED: image build'        '^UPDATED' S_BUILD_RC=1
t "update: creepjs pull fails"      1 'FAILED: pull'               '^UPDATED' S_PULL_RC=1
t "update: compose up fails"        1 'FAILED: docker compose up'  '^UPDATED' S_UP_RC=1
t "update: gluetun never healthy"   1 'not healthy after 90 s'     '^UPDATED' S_HEALTH=starting
t "update: old image still running" 1 'not running the image just built' '^UPDATED' S_RUN_IMG=sha256:old
t "update: no built image"          1 'not running the image just built' '^UPDATED' S_BUILT_IMG= S_RUN_IMG=
t "update: firefox --version empty" 1 'firefox --version returned nothing' '^UPDATED' S_FFVER=
t "update: web UI never answers"    1 'did not answer within 30 s' '^UPDATED' S_UI_HTTPERR=1

echo "== launch.sh"
SCRIPT=launch.sh ARGS=
t "launch: all good"                0 ''                           'did not become ready' $N
t "launch: compose fails, old UI answers" 1 'compose up failed'    ''         S_UP_RC=1
t "launch: gluetun never healthy"   1 'did not become ready in 30s' ''        S_HEALTH=starting
t "launch: UI returns HTTP error"   1 'did not become ready in 30s' ''        S_UI_HTTPERR=1
t "launch: UI hangs (2 s per try)"  1 'did not become ready in 30s' ''        S_UI_RC=28 S_UI_SECS=2
# The hung-UI case must stop on the clock, not on a try count: at 2 s + 1 s sleep per
# try, a 30 s deadline allows at most 10 tries (the old 30-try loop would make 30).
n=$(command grep -c 7814 "$SD/calls" || true)
if [ "$n" -ge 1 ] && [ "$n" -le 11 ]; then pass=$((pass+1)); echo "ok    launch: hung UI bounded by the deadline ($n tries)"
else failn=$((failn+1)); echo "FAIL  launch: hung UI made $n tries; the deadline is not bounding it"; fi
if command grep -q -- '--max-time' "$SD/calls"; then pass=$((pass+1)); echo "ok    launch: UI probe has --max-time"
else failn=$((failn+1)); echo "FAIL  launch: UI probe has no --max-time"; fi
rm -f "$SD/calls"; bash "$W/launch.sh" >/dev/null 2>&1
if command grep -q '^xdg-open' "$SD/calls"; then pass=$((pass+1)); echo "ok    launch: opens the UI when ready"
else failn=$((failn+1)); echo "FAIL  launch: did not open the UI when ready"; fi

echo "== ci/fingerprint.sh"
SCRIPT=ci/fingerprint.sh ARGS=
CJ="$W/ci/creepjs-docs"
SHA=$(sed -n 's/^CREEPJS_SHA=\([0-9a-f]*\).*/\1/p' "$W/ci/fingerprint.sh")
t "fp: all good"                    0 '^PASS  prefs'               '^FAIL'    $N
t "fp: checks.mjs INCOMPLETE -> 3"  3 ''                           ''         S_NODE_RC=3
t "fp: checks.mjs FAIL -> 1"        1 ''                           ''         S_NODE_RC=1
t "fp: pref FAIL beats INCOMPLETE"  1 '^FAIL  prefs'               ''         S_PREF_RC=1 S_NODE_RC=3
t "fp: node crash (rc 137) -> 1"    1 ''                           ''         S_NODE_RC=137
# CreepJS cache keyed on the pinned SHA.
rm -rf "$CJ" "$SD/downloads"
t "fp: download fails (curl rc)"   22 ''                           ''         S_CJ_RC=22
if [ ! -f "$CJ/.sha" ]; then pass=$((pass+1)); echo "ok    fp: failed download leaves no .sha"
else failn=$((failn+1)); echo "FAIL  fp: failed download wrote .sha"; fi
t "fp: tarball without creep.js"    1 'has no docs/creep.js'       ''         S_CJ_EMPTY=1
rm -f "$SD/downloads"
t "fp: first run downloads"         0 ''                           ''         $N
t "fp: same SHA reuses the cache"   0 ''                           ''         $N
n=$(wc -l <"$SD/downloads" 2>/dev/null || echo 0)
if [ "$n" -eq 1 ] && [ "$(cat "$CJ/.sha" 2>/dev/null)" = "$SHA" ]; then pass=$((pass+1)); echo "ok    fp: one download for two runs, .sha = pin"
else failn=$((failn+1)); echo "FAIL  fp: $n downloads for two runs, .sha=$(cat "$CJ/.sha" 2>/dev/null)"; fi
echo 0000000000000000000000000000000000000000 >"$CJ/.sha"; touch "$CJ/stale-file"
t "fp: pin changed"                 0 ''                           ''         $N
if [ "$(wc -l <"$SD/downloads")" -eq 2 ] && [ "$(cat "$CJ/.sha")" = "$SHA" ] && [ ! -e "$CJ/stale-file" ]; then
  pass=$((pass+1)); echo "ok    fp: changed pin re-downloads into a clean dir"
else failn=$((failn+1)); echo "FAIL  fp: changed pin did not re-download cleanly"; fi

rm -f "$SD/calls"; env RECORD=1 bash "$W/ci/fingerprint.sh" >/dev/null 2>&1
if command grep -q '^docker run .*-e RECORD=1 ' "$SD/calls"; then pass=$((pass+1)); echo "ok    fp: RECORD=1 reaches checks.mjs"
else failn=$((failn+1)); echo "FAIL  fp: RECORD=1 not passed to the node container"; fi

echo
echo "scripts: $pass passed, $failn failed"
[ "$failn" -eq 0 ]
