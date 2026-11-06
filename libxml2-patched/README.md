# Debian-stable libxml2 backport

This build adds Ubuntu's published CVE-2026-6653 patch to the exact Debian stable
source used by the browser. It retains Debian's other patches and compiler
hardening. It does not install a testing/unstable library or an Ubuntu binary.

Sources:

- [Debian advisory and stable version](https://security-tracker.debian.org/tracker/CVE-2026-6653)
- [Ubuntu fixed-version record](https://ubuntu.com/security/CVE-2026-6653)
- [Ubuntu source package](https://launchpad.net/ubuntu/+archive/primary/+sourcefiles/libxml2/2.9.14+dfsg-1.3ubuntu3.8/)
- [Upstream entity-accounting change](https://github.com/GNOME/libxml2/commit/463bbeeca1805b5c4828f50d0fefc4eebaf620df)

`CVE-2026-6653.patch` is copied unchanged from that Ubuntu source package's
`debian/patches/`. Its SHA-256 is pinned in `patch.sha256`. The Debian source files
and the matching upstream v2.9.14 test corpus are pinned in `source.sha256` and
fetched using HTTPS. These checked hashes establish the reviewed input identity;
the build does not claim independent verification of the source package's PGP
signature. Debian's DFSG archive omits the upstream test/result corpus, so the
build restores only missing fixtures from the matching upstream release while
preserving Debian's changed fixtures.

`Dockerfile.firefox` builds this package in a discarded compiler stage, then runs
`make check` with networking disabled. Any failure stops the browser build. Python
bindings are not built: the runtime does not contain them. The optional external
W3C xmlconf corpus is not supplied; a zero-test xmlconf report is not conformance
acceptance. Build inventories and input/package hashes are retained in the final
image under `/usr/share/doc/libxml2/private-browser-build/`.

The version suffix is `+pb1`, after the current `+deb13u3` and before a future
`+deb13u4`. The final installation step refuses to downgrade a newer distribution
library. A future stable revision therefore needs a fresh review or removal of
this backport; it cannot silently lose newer Debian fixes.

## Compatibility boundary

The vendor patch appends fields to public entity/input structs. Existing member
offsets and the exported symbol set are retained, but this is not a claim of
universal binary compatibility for arbitrary software allocating those structs
itself. Debian's symbol gate and a consumer compiled against the original Debian
headers are checked. That consumer parses an ordinary internal entity, renders
SVG through the actual installed librsvg, checks the optional GdkPixbuf SVG loader
if installed, and verifies ordinary malformed-SVG error handling. An absent SVG
loader is reported explicitly, not counted as a loader pass. Browser fingerprint,
startup, scan and real-VPN installation evidence remain separate gates.

```sh
python3 ci/test-libxml2-consumer.py private-firefox:ci
```

The compiler fixture uses no VPN configuration. The runtime test uses the exact
browser image ID, no network, no Linux capabilities and a read-only filesystem
with disposable temporary cache space. No proof-of-concept exploit is downloaded
or executed by this compatibility test. Scanner entries for a custom package may
remain until the vendor database recognizes a stable fix: retain the complete
scan and distinguish the locally applied fix from vendor scanner status. Do not
suppress the advisory or extend an expired residual-risk decision.
