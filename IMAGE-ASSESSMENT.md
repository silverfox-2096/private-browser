# Retained advisories and exact-image assessment

Assessment date: 20 October 2026. This is a bounded package/path assessment,
not an exploit test or acceptance of material residual risk. Findings remain
visible; no scanner exclusion or alert dismissal was added.

## Artifact and scan scope

The current main Firefox scan has 504 observations: 1 CRITICAL, 115 HIGH,
213 MEDIUM, 167 LOW and 8 UNKNOWN. Dependabot separately returns no alerts;
it is a different advisory source. These are not 504 distinct exploits.

A fresh read-only scan of archives of the maintainer's exact running Firefox and
Gluetun images used Trivy 0.76.0, pinned by scanner-image digest, with vulnerability
DB updated `2026-10-20T01:16:59Z` and downloaded `2026-10-20T04:30:30Z`.
The archives' OCI index/manifest/config chains were checked against the deployed
image identities. Scanners ran without network, Docker socket, production keys or
browser/profile mounts. Only the separate database download used network access.

| Artifact | Complete result | Interpretation |
|---|---|---|
| Exact deployed Firefox | 504 findings; all advisory/package/version tuples match current main Code scanning | 116 High/Critical package rows reduce to 42 source-package/advisory groups across 14 source packages. No scanner-reported fixed High/Critical version. A matching finding set does not establish identical CI/live images. |
| Exact deployed Gluetun | One UNKNOWN (`GO-2026-5932` in x/crypto); no Low/Medium/High/Critical | Consistent with the retained [OpenPGP source assessment](gluetun-patched/README.md#beforeafter-and-applicability): no imported affected OpenPGP package in matching application source. No suppression. The original 31 HIGH findings remain remediated. |
| Fresh public-recipe builds | Separate [CI](SECURITY.md#where-to-see-the-results) artifacts, built at scan time | A green fixable-only gate does not scan an older running image continuously or establish zero retained advisories. |

Exact deployed IDs, archive checksums, complete JSON, scanner/database timestamps,
installed binary/source versions and per-advisory dispositions are retained in the
operator's private deployment register. Do not upload local image archives, host
inventory, environments or raw deployment evidence to a public issue or runner.

## Prioritized groups and remaining path evidence

All 42 priority groups remain open for trixie in the refreshed
[Debian tracker data](https://security-tracker.debian.org/tracker/data/json).
No compatible stable replacement is established by a newer testing/unstable
package. The deployment register records each advisory, binary/source version,
evidence or precise blocker, owner and review trigger.

| Source | Priority advisories | Bounded finding / unresolved evidence |
|---|---:|---|
| libxml2 | 8 | Python SAX binding path absent for CVE-2026-74860. Seven remain pending: internal DTD/entity handling (CVE-2026-6653), XInclude flags, output callbacks, XPointer lengths, element formatting, URI escaping and dictionary allocation. Installed librsvg imports the XML parser; actual hostile-input delivery/options require further evidence. |
| FFmpeg | 16 | Nine affected demuxer/muxer/filter paths belong to absent libavformat/libavfilter libraries. Six codec/encoder paths are outside the reviewed Firefox 158 MIME/codec mapping; installed code/other consumers are not universally excluded. NVDEC has no granted GPU device in this configuration; that is a restricted prerequisite, not a patch. |
| util-linux | 4 | Three mount-hook/fstab paths have no active fstab entries and UID1000 cannot gain setuid privilege under no-new-privileges. nsenter --join-cgroup needs privileged invocation against a hostile target. Root-init/alternate paths not exhaustively excluded. |
| systemd | 1 | CVE-2026-16742 requires systemd-homed; the daemon/package is absent, despite installed systemd libraries. |
| cups | 2 | cupsd shared-printer and IPP backend executables absent; installed libcups client library is not those executables. |
| perl | 1 | Archive::Tar is absent; perl-base remains installed. Reassess if modules are added. |
| tiff | 2 | tiffcrop tool absent for CVE-2026-52490. CVE-2026-36849 remains pending: GTK TIFF loader and libtiff are installed; hostile TIFF delivery and affected tag parsing need a consumer-specific check. |
| libX11, libXrender, libXtst | 3 | Malicious X-server reply prerequisites differ from a web-page attack. Local GUI uses X libraries; actual affected API use and hostile-server control remain unproved. |
| wget | 2 | CVE-2026-58471 concerns character-set conversion of server-supplied filenames; CVE-2026-58472 concerns HTML attribute entity encoding. Lack of --convert-links does not rule out the filename case. wget is installed for probes; actual response/charset/attribute caller conditions remain unresolved. |
| ncurses | 1 | infocmp is installed; attacker-controlled terminfo/entry processing by an actual caller remains unproved. |
| libsndfile | 1 | WAV IMA ADPCM code is installed; actual untrusted-WAV delivery to an installed consumer remains unproved. |
| acl | 1 | Pathname/symlink APIs are installed; a privileged caller crossing an attacker-controlled pathname remains unproved. Root GUI/init paths are not excluded by browser UID/no-new-privileges alone. |

The 42 groups comprise 15 named-feature-absent findings, 6 reviewed-browser-mapping
exclusions, 5 restricted-prerequisite cases and 16 unresolved applicability cases.
These categories are scoped findings, not blanket “not affected” decisions.
No malicious input was supplied to the live browser. Isolated fixtures only
inspected image files/dependencies; static source inspection is not runtime proof.

### Critical-labelled libxml2 example

[CVE-2026-6653](https://security-tracker.debian.org/tracker/CVE-2026-6653) remains
vulnerable in trixie's `2.12.7+dfsg+really2.9.14-2.1+deb13u3`; the `really2.9.14`
version must not be mistaken for a fully fixed 2.12 branch. Debian records a
no-DSA/minor disposition. That does not establish non-applicability or override
scanner severity by itself. The upstream [entity-handling change](https://github.com/GNOME/libxml2/commit/463bbeeca1805b5c4828f50d0fefc4eebaf620df)
is substantial, not a validated drop-in stable library update.

Matching Debian source still calls `xmlParseInternalSubset` from the document
parser for internal DTDs. Installed librsvg imports `xmlParseDocument`; libxul's
static dependency closure does not directly list libxml2. An actual attacker-input
route through GUI/librsvg plus relevant parser/error options remains unproved.
Neither the indirect dependency nor the lack of a direct libxul dependency closes
that question. Existing sandbox, viewer authentication and private-address firewall
do not repair XML/media parsing of content reached over the public internet.

## Repeatable manual exact-image scan

Inspect the current container's immutable `.Image`, export **that ID** with
`docker image save`, retain its checksum and verify its OCI index/manifest/config
chain. A Docker ID may be an OCI index while Trivy reports a child config ID;
record the chain rather than treating that normal difference as a different image.
The archive contains image layers, not the running container's mounts/profile.
Keep it private anyway. Do not start the target image or mount the Docker socket
into the scanner.

The following pattern scans an existing private archive. Run it in a new private
directory containing `image.tar`; retain the exact target ID/export record separately.
The pinned scanner must already be available locally. Stop on any command error.

```bash
set -eu
umask 077
mkdir cache results
scanner='aquasec/trivy@sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222'
# Download public advisory data only; no target archive mounted.
docker run --rm --user "$(id -u):$(id -g)" --cap-drop=ALL \
  --security-opt=no-new-privileges --read-only --cpus=2 --memory=2g \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g --network=bridge \
  -v "$PWD/cache:/cache" "$scanner" image --cache-dir /cache --download-db-only
docker run --rm --user "$(id -u):$(id -g)" --cap-drop=ALL \
  --security-opt=no-new-privileges --read-only --network=none \
  -v "$PWD/cache:/cache:ro" "$scanner" version --cache-dir /cache \
  > results/scanner-version.txt
# Full vulnerability report, all severities/unfixed findings; no secret scanner.
docker run --rm --user "$(id -u):$(id -g)" --cap-drop=ALL \
  --security-opt=no-new-privileges --read-only --cpus=2 --memory=2g \
  --tmpfs /tmp:rw,nosuid,nodev,size=1g --network=none \
  -v "$PWD/cache:/cache" -v "$PWD/image.tar:/input/image.tar:ro" \
  -v "$PWD/results:/output" "$scanner" image --cache-dir /cache \
  --skip-db-update --offline-scan --scanners vuln --input /input/image.tar \
  --format json --output /output/full.json --exit-code 0
sha256sum image.tar results/full.json > results/SHA256SUMS
```

A zero exit code here means scan execution completed, not zero findings or risk
acceptance. Missing/failed reports are INCOMPLETE. Compare installed versions with
the running package inventory and confirm the target ID did not change during
collection. Keep complete findings, then assess High/Critical groups separately.
This pattern was exercised with the two exact archives; it does not inspect
writable-container drift or prove every application call path.

## Ownership, review and deployment decision

The agent maintains the evidence assessment; the operator owns material
residual-risk acceptance and live replacement decisions. Findings remain open
while that decision is pending. No compatible patched candidate or live change
is proposed by this assessment.

Reassess on an exact-image/package/consumer/configuration change, a stable vendor
fix or new exploit/path evidence; otherwise manually review by 27 October 2026.
This is a review trigger, not a newly scheduled task. Existing daily updater,
monthly upkeep reminder and weekly recipe CI do not establish routine exact-live
scanning; no job or timer was added. Retaining the current artifacts with unresolved
applicability requires an explicit operator disposition; none is assumed here.

Any future candidate needs its own compatible package/build diff, exact image scan,
isolated browser/VPN/policy validation and rollback before separately authorized
live rollout. The tested immutable Gluetun override remains intentional.
