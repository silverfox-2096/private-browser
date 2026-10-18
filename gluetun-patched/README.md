# Patched stable Gluetun candidate — 2026-10-18

**Ready for operator review; not deployed.** The default Compose pin and live VPN
remain upstream v3.41.3. No CVE suppression was added. The stable companion scan
therefore remains a failing security signal. The new candidate CI job and
Dependabot coverage are prepared on the review branch, not yet running on main.

## Identities and changes

- Original: `qmcgaw/gluetun:v3.41.3@sha256:fa19cc76b2af13d57a8d3dc3066f2ada061b1c761b8aecf989b3877c0486e027`.
  Registry index digest; linux/amd64 manifest
  `sha256:1baa76576dea1dfbafbd62bb635daf40fd87171f63273c2fdfe630418783011e`.
  Actual binary Go 1.25.11, x/crypto v0.45.0, x/net v0.47.0, x/text v0.31.0.
- Exact stable source: `3d1e20c5551e9cae1f9d938dc7b7214a6987f27e`.
  The original qdm12 repository redirects to passteque/gluetun; the stable image
  labels and release/tag API match that commit. v3.41.3 is still the latest stable
  release. Its registry digest is unchanged. The development digest is still
  `sha256:945d325be5c2abe50b89c84791b51a4e3d039737ed3703b2482c1e2b396e8fbe`;
  the recorded development comparison has five HIGH findings and was not adopted.
- Candidate local tag: `private-gluetun:v3.41.3-pb1`.
  Tested immutable image/index ID:
  `sha256:e8e565d3ca963f40239a7b0878681299ef0dc4ec5bfc5deca94402b554a25c06`.
  It is a local custom build, not an upstream release or a published registry image.
- Go 1.27.2; x/net v0.60.0; x/crypto v0.57.0; x/text v0.42.0;
  CIRCL v1.6.3. The module graph requires x/sys v0.48.0, x/mod v0.41.0,
  x/sync v0.23.0, x/tools v0.49.0, and minimum Go 1.26.0. Exact sums are committed.
  No application-source edits. Release display identifies the custom build as pb1.
- Runtime overlay preserves stable image configuration and its healthcheck, then
  upgrades Alpine packages and replaces the static Go binary. Actual packages:
  Alpine release 3.22.6-r0, libcrypto3/libssl3 3.5.9-r0, OpenVPN 2.6.20-r0.
  Trivy reports OS identity 3.22.5 from inherited release metadata; installed
  alpine-release identifies 3.22.6. The scanner selects the same v3.22 database.

## Before/after and applicability

Trivy 0.70.0 and 0.76.0 independently reproduce **31 HIGH / 28 distinct CVEs,
zero CRITICAL** on the original image. No HIGH additions, removals or changed fix
versions versus the historical filtered scan. The full refreshed baseline has
30 MEDIUM, 14 LOW and 2 UNKNOWN findings as well. Final candidate: **zero CRITICAL,
HIGH, MEDIUM or LOW; one UNKNOWN**. The intermediate candidate's LOW CIRCL issue
was patched before the final scan and runtime tests.

Database schema 2, updated 2026-10-18 07:12:07 UTC, downloaded 10:53:48 UTC.
Baseline scan timestamps: 10:53:49 UTC (0.70.0) and the retained current-scanner JSON.
Final candidate scan: 2026-10-18 11:02:27 UTC. Trivy 0.76.0 image:
`aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222`.
See [the complete per-finding assessment](applicability.md) and evidence JSON.

Matching-source govulncheck v1.9.0 uses Go 1.25.11 for the original and Go 1.27.2
for the final candidate. Twelve of the original 31 HIGH rows have static affected
symbol call paths. This includes code beyond the active WireGuard transport.
SSH is absent from the original executable's matching-source dependency closure;
this was checked rather than inferred from its title. The stripped actual binary
cannot independently establish function presence: govulncheck falls back to
module-level precision. No exploit or attacker-controlled runtime path was proven.

The remaining UNKNOWN `GO-2026-5932` concerns abandoned
`golang.org/x/crypto/openpgp`. It has no upstream fixed version; none of its packages
is imported in the matching-source executable. The maintained ProtonMail fork is
a different import path and is the alternative recommended by that advisory.
The UNKNOWN is retained without an exclusion. govulncheck also retains a module
match for `GO-2026-5841` (klauspost/compress v1.18.1, fix v1.18.7): affected s2.NewDict
is not imported; the executable uses zstd/flate. Neither remaining advisory has an
imported affected package or a source call finding in the final analysis. This is
source evidence, not a binary-symbol or live exploitability determination.

## Validation and limits

- Full upstream `go test -race -count=1 ./...` passed with final dependency graph.
- Actual final image scanned; full JSON kept, not only a severity filter.
- Isolated VPN healthy; inherited Docker healthcheck command passed. All routes
  tested on control API reject unauthenticated GET/PUT with 401; authenticated
  GET/stop/start work. Test uses a disposable API key, not the production key.
- Browser checks 7/7 pass: Firefox 158, RFP, WebGL, Singapore exit, WebRTC,
  Cloudflare DNS resolver identity, four CreepJS baseline fields.
- UID 1000 HTTPS positive control succeeds with tunnel up. With tun0 absent but
  Gluetun/browser still running, wget exits 4. API restart restores connectivity.
  Stopping the namespace-owning VPN container also blocks the running browser.
- Capture: 34,338 packets; zero kernel drops; 14 direct control packets observed;
  zero direct candidate TCP/443 packets to 1.1.1.1. This is bounded IPv4/one-target
  evidence, not universal bypass proof. Firewall rules/routes saved.
- First runtime attempt was INCOMPLETE: unprotected control connection timed out
  before tunnel-down tests. It was not a PASS. Second attempt uses captured
  control packets to establish visibility and passed all required observations.
- Original live image restored; verify.sh 4/4 and browser checks 7/7 passed.
  Shared network ID unchanged, including homelable-backend-1. Gate released.
- Project failure-path tests 65/65; checker-verdict tests 21/21; ShellCheck,
  Hadolint and opt-in Compose validation pass. Remote branch CI has not run.
- No startup tunnel-absent boot observation or host-originated forwarding result
  is added. Both earlier gaps remain open. No clipboard or reboot work performed.

## Build, maintenance and rollout

Build independently: `docker build --target test gluetun-patched`, then
`docker build --provenance=mode=max -t private-gluetun:v3.41.3-pb1 gluetun-patched`.
FROM images are pinned; the stable source archive is checksum-verified; Go modules
are locked and verified. Build metadata retains resolved materials. Local
provenance is unsigned and does not imply an upstream attestation. Alpine package
repositories move: a future rebuild can produce different package versions and
image IDs. A rebuild must be rescanned/retested. The tested output is retained
by immutable image ID and a checksum-protected local image archive; byte-identical
rebuilding from moving Alpine repositories is not claimed.

An operator accepting this build assumes responsibility for Go, module and Alpine
updates until a maintained upstream stable image passes. Weekly CI/Dependabot
changes are prepared, not a guarantee of timely fixes. Every replacement needs
its own scan, upstream tests and isolated VPN/browser/firewall validation. Prefer
returning to a maintained upstream stable fix when available.

Production rollout requires explicit approval of this custom build and a closed
viewer. Use the existing updater exclusive lock, create/verify the maintenance
503 gate BEFORE reading viewer sockets, and abort if any remain or checks fail.
Keep the gate through rollout and rollback; release it on exit. Do not run the
candidate and original VPN concurrently with the same WireGuard key. Do not remove
or recreate the shared live network. For local rollout, render the reviewed immutable ID into an automatic
`docker-compose.override.yml` in the live directory (refuse an existing override).
This is necessary because verify.sh and the updater invoke default Compose;
an overlay passed only with `-f` would be lost by those callers. The repository's
`docker-compose.gluetun-candidate.yml` is a separate opt-in template for review,
not an automatically active file. `pull_policy: never` prevents a registry lookup.
Confirm the running image ID, health, authenticated API, verify.sh and browser
checks after the swap. The local rollout script is staged in task evidence and
has not been executed. Default public compose remains upstream stable pending
an explicit distribution/default-pin decision; this local image is not on a registry.

Rollback: under the same lock/gate, stop candidate VPN/browser, remove only the automatic override created by this rollout and run the original Compose definition, then restart Firefox so it joins
the restored namespace. Preserve any pre-existing optional CreepJS state. Verify
original image ID `fa19cc76...`, health, verify.sh and browser checks before releasing
the gate. This restoration path was exercised after both isolated runs. Its
security baseline remains 31 HIGH, which is why it is rollback rather than a fix.
Exact original/candidate images are retained in the local rollback archive;
verify its SHA256 before loading if Docker's local images have been removed.

## Primary sources

- [Official stable release](https://github.com/passteque/gluetun/releases/tag/v3.41.3)
- [Exact stable source](https://github.com/passteque/gluetun/tree/3d1e20c5551e9cae1f9d938dc7b7214a6987f27e)
- [Go release history](https://go.dev/doc/devel/release)
- [Go vulnerability tooling](https://go.dev/doc/security/vuln/)
- [OpenSSL advisory index](https://openssl-library.org/news/vulnerabilities/)
- [Alpine 3.22 security database](https://secdb.alpinelinux.org/v3.22/main.json)
- [Retained UNKNOWN advisory](https://pkg.go.dev/vuln/GO-2026-5932)
- [Remaining module-only s2 advisory](https://pkg.go.dev/vuln/GO-2026-5841)
