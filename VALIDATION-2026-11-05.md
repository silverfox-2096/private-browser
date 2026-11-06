# Update and security validation — 5 November 2026

This records local validation on one installation. CI rebuilds produce separate
artifacts and do not inherit a claim about a running installation. Raw captures,
profiles, addresses and credentials remain private.

## Changes and observed results

| Change | Validation |
|---|---|
| Create `/config/log` before Debian upgrades | Disposable base upgrade and full Firefox build passed; `/var/log` symlink preserved, `dpkg --audit` empty. APT/libapt 3.0.4 removed both High package entries for CVE-2026-109518. |
| Firefox 159.0.1 | Guarded updater passed image/version identity, network checks 4/4 and browser checks 7/7; failed-version marker cleared and daily timer remains active. |
| x/net 0.62.0, custom VPN pb3 | Pinned application source and Go 1.27.3 retained. Full upstream race tests, authentication/local-policy contracts and 14 real credential-free IPv4/IPv6 policy controls passed. Affected HTML Parse/Render source findings were removed. |
| Guarded VPN rollout | Separate real isolated and production network checks 4/4 and browser checks 7/7 each; local policy, HTTPS/DNS, API 401/200 and viewer login recovery passed. No concurrent VPN instances used the same account keys. Shared network/backend and optional-service state preserved; prior image retained for rollback. |
| Rollback housekeeping | 32 updater/wrapper controls passed, including retained tags/digests, failed validation/recovery, missing or unchanged rollback and refused removal. ShellCheck and Dockerfile lint passed. Cleanup never forces deletion or prunes parents. |

Before the update, read-only diagnosis found Firefox in a stale VPN network
namespace: the containers reported running but the viewer was unreachable. A
zero-viewer guarded restart restored the namespace and maintenance gate before
the existing updater ran. The build fix does not claim to prevent every future
namespace mismatch.

The first isolated VPN browser test lacked a copied helper and was refused; the
retained production VPN was restored and recovery verified. Helper/baseline
preflight was added and the corrected full retry passed. This failed attempt is
not counted as a successful candidate validation. No new actual-boot experiment
or universal leak/relay claim follows from these results.

## Exact images and scan scope

Trivy 0.76.0, pinned image digest
`sha256:2416d1f74045b57274df1a340eee6b510cacd73c66a6ccb8da092b117eb7d222`.
Database updated 2026-11-05 01:19:45 UTC; exported-image OCI/config chains and
archive hashes were verified against the scanner's image metadata. Scans ran
offline on exports, without a mounted Docker socket or production credentials.

| Local output | Immutable image/index identity | Critical | High | Medium | Low | UNKNOWN |
|---|---|---:|---:|---:|---:|---:|
| Firefox 159.0.1 | `sha256:d4f1b038173ba8f3569013c7dd352326757db0e1cbff17bfbf55d30e45f04693` | 1 | 121 | 259 | 166 | 12 |
| VPN pb3 | `sha256:267af9056e264cd1b610847d29515a2af76b526f509a8002e93004e9a0c758a9` | 0 | 0 | 0 | 0 | 1 |

Neither output has a reported fixable High/Critical entry in this database. The
VPN's retained UNKNOWN is GO-2026-5932 for abandoned crypto/openpgp; matching-source
analysis finds only the module match and no affected imported package. Stripped
binary/module metadata is not presented as recovered call-path proof.

The browser's 122 High/Critical package rows match the exact image inventory and
map to 48 advisory/source groups, all open in Debian stable. All 42 prior groups
persist; six new High cases concern Expat (three), SQLite (one) and libXi (two).
Fifteen named-feature absences and six Mozilla 159.0.1 codec mappings were
refreshed; five prerequisite restrictions remain bounded by the configuration,
and 22 cases retain precise applicability blockers. Findings are not suppressed
or treated as 122 proven exploits. The critical libxml2 route remains a priority.
The prior disposition ended 27 October and is not renewed by these checks.

See [current assessment](IMAGE-ASSESSMENT.md), [remaining work](FOLLOW-UP-PLAN.md)
and [VPN source/rollout record](gluetun-patched/README.md). Recipes remain rebuilds,
not byte-for-byte promises of these locally deployed outputs.
