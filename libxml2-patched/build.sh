#!/usr/bin/env bash
set -euo pipefail
# Rebuild Debian stable, retaining its existing security patches. Only the
# published Ubuntu backport below is added; no testing/unstable binary is used.
cd /build
base=https://deb.debian.org/debian/pool/main/libx/libxml2
version=2.12.7+dfsg+really2.9.14-2.1+deb13u3
for file in "libxml2_${version}.dsc" "libxml2_${version}.debian.tar.xz" libxml2_2.12.7+dfsg+really2.9.14.orig.tar.xz; do
    curl --fail --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 "$base/$file" -o "$file"
done
curl --fail --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 \
    https://codeload.github.com/GNOME/libxml2/tar.gz/refs/tags/v2.9.14 -o libxml2-upstream-tests.tar.gz
sha256sum -c /pb-libxml2/source.sha256
sha256sum -c /pb-libxml2/patch.sha256
mkdir -p /src /out
dpkg-source -x "libxml2_${version}.dsc" /src/libxml2
mkdir /upstream-tests
tar -xzf libxml2-upstream-tests.tar.gz --strip-components=1 -C /upstream-tests
cd /src/libxml2
# Debian's DFSG source omits the upstream corpus. Fill only missing fixtures;
# preserve all fixture additions/changes supplied by Debian's security patches.
cp -rn /upstream-tests/test/. test/
cp -rn /upstream-tests/result/. result/
cp /pb-libxml2/CVE-2026-6653.patch debian/patches/
printf '\nCVE-2026-6653.patch\n' >> debian/patches/series
# Keep the built sources patched for the later explicit test stage. This local
# dpkg option affects build-tree cleanup, not the produced library package.
printf 'no-unapply-patches\n' > debian/source/local-options
dpkg-source --before-build .
# Reject an inexact application rather than silently adapting a changed source.
test ! -e parser.c.rej
printf '%s\n' \
    "libxml2 (${version}+pb1) trixie; urgency=high" '' \
    '  * Apply Ubuntu vendor CVE-2026-6653 entity accounting backport.' '' \
    ' -- Private Browser maintainers <noreply@private-browser.invalid>  Fri, 06 Nov 2026 08:00:00 +0000' '' > /tmp/pb-changelog
cat debian/changelog >> /tmp/pb-changelog
cp /tmp/pb-changelog debian/changelog
# Keep Debian hardening, symbol checks and the full enabled upstream test suite.
# Python bindings are absent in the runtime and are not built into this package.
DEB_BUILD_PROFILES=nopython dpkg-buildpackage -B -us -uc -P nopython -j4 > /out/build.log 2>&1 || { tail -100 /out/build.log; exit 1; }
cp /src/*.deb /out/
cp /pb-libxml2/source.sha256 /pb-libxml2/patch.sha256 /out/
dpkg-query -W > /out/build-packages.txt
sha256sum /out/*.deb > /out/packages.sha256
