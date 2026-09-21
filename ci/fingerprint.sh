#!/usr/bin/env bash
set -euo pipefail
# Fingerprint regression check. Needs no VPN key, so it runs in CI and locally.
#
# Builds the image, starts it WITHOUT the tunnel (ci/compose.fingerprint.yml), then
# drives a second, headless Firefox on a copy of its profile over WebDriver BiDi:
# UA major = the installed Firefox, RFP time zone, WebGL off, Safe Browsing prefs off,
# and CreepJS fields (fonts, WebGL, time zone, cores) vs ci/creep-baseline.json.
# Leak tests (exit IP, DNS, WebRTC, kill switch) need the tunnel: see verify.sh.
#
# Usage: bash ci/fingerprint.sh        (SKIP_BUILD=1 reuses private-firefox:ci)
# Output: ci/out/checks-out.json + creep-full.json. Exit 0 = all PASS.

cd "$(dirname "$(readlink -f "$0")")/.."
CREEPJS_SHA=10aa6724cd33a1015db1574211890518cd04f0cc   # abrahamjuliot/creepjs master, 2026-06-11
NODE_IMG=node:22-slim@sha256:48e4b67d85f87bd551df43704e24d252f56cc5f8e9718841aace50f19948f0f9
FF=pbfp-firefox
out="$PWD/ci/out"

dc() { docker compose -p pbfp -f docker-compose.yml -f ci/compose.fingerprint.yml "$@"; }
cleanup() { dc --profile test down >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "1/5 CreepJS $CREEPJS_SHA (its repo ships the built page in docs/)"
if [ ! -f ci/creepjs-docs/creep.js ]; then
  mkdir -p ci/creepjs-docs
  curl -fsSL "https://codeload.github.com/abrahamjuliot/creepjs/tar.gz/$CREEPJS_SHA" |
    tar -xz -C ci/creepjs-docs --strip-components=2 "creepjs-$CREEPJS_SHA/docs"
fi
chmod -R a+rX ci/creepjs-docs   # nginx runs as its own user; a 077 umask hides the page

echo "2/5 build (~3-5 min, quiet; errors still print) + start the browser (no VPN)"
[ "${SKIP_BUILD:-0}" = 1 ] || dc build --quiet firefox
dc --profile test up -d firefox creepjs
version=$(docker exec "$FF" firefox --version | sed -n 's/^Mozilla Firefox //p')
echo "   Firefox ${version:?could not read the Firefox version}"

echo "3/5 copy the profile (waits up to 60 s for it to exist)"
for i in $(seq 1 30); do
  docker exec -u 1000 "$FF" sh -c '[ -f /config/profile/prefs.js ] || exit 1;
    rm -rf /tmp/hlprof /tmp/hlhome; cp -r /config/profile /tmp/hlprof;
    rm -f /tmp/hlprof/lock /tmp/hlprof/.parentlock; mkdir -p /tmp/hlhome' && break
  [ "$i" -eq 30 ] && { echo "FAIL: no /config/profile/prefs.js after 60 s"; exit 1; }
  sleep 2
done

echo "4/5 Safe Browsing prefs, as the FF_PREF_* handler wrote them"
fail=0
for p in malware phishing downloads; do
  if docker exec "$FF" grep -qF "user_pref(\"browser.safebrowsing.$p.enabled\", false);" \
      /tmp/hlprof/prefs.js; then
    echo "PASS  prefs: browser.safebrowsing.$p.enabled = false"
  else
    echo "FAIL  prefs: browser.safebrowsing.$p.enabled is not false"; fail=1
  fi
done

echo "5/5 headless Firefox + checks (node sidecar in the browser's network namespace)"
docker exec -d -u 1000 -e HOME=/tmp/hlhome "$FF" \
  firefox --headless --no-remote --profile /tmp/hlprof --remote-debugging-port 9222
mkdir -p "$out"
docker run --rm --user "$(id -u):$(id -g)" --network "container:$FF" \
  -e MODE=ci -e EXPECT="$version" -v "$PWD/ci:/w:ro" -v "$out:/out" \
  "$NODE_IMG" node /w/checks.mjs || fail=1

exit "$fail"
