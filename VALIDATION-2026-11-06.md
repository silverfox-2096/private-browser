# Local candidate validation — 6 November 2026

This candidate combines the guided installer with the fixes merged in PR #49, and
adds the published Ubuntu libxml2 CVE-2026-6653 backport to Debian stable source.
It is not a production-deployment receipt or a prebuilt-release acceptance.

Candidate browser image:
`sha256:ff13f76c7caec4cdb5fdc8f1dbd4ffbf99926ffa8fcfede1eec7a2697bd15778`.
Firefox 159.0.1, libxml2 `2.12.7+dfsg+really2.9.14-2.1+deb13u3+pb1`.
The [input hashes and scoped results](libxml2-patched/evidence/validation-20261106.json)
bind this artifact to its actual image recipe and source inputs.

| Gate | Actual observation and limit |
|---|---|
| Upstream library checks | PASS: 3360 parser tests, 9 recursion tests, 280912 API cases. Debian-omitted fixtures restored from the checksum-pinned upstream v2.9.14 corpus; Debian changes preserved. W3C xmlconf has 0 tests because its optional corpus is absent. No W3C conformance claim; Python bindings absent/not built. |
| Runtime compatibility | PASS: consumer compiled against original Debian headers, ordinary internal entity, installed librsvg render, malformed SVG error return. GdkPixbuf SVG loader is absent in both baseline/candidate and is not counted as a loader pass. Public struct extensions retain an explicit compatibility boundary; see [backport notes](libxml2-patched/README.md). |
| Browser fingerprint | PASS: three declared preferences plus user agent, RFP time zone, blocked WebGL and four-field CreepJS baseline. Disposable browser without VPN; not a leak-test result. |
| Startup guard | PASS: 7 isolated readiness/tunnel-presence controls. Not a new actual-host boot observation. |
| Guided setup / packaging / lifecycle | PASS: 40/17/34 local regressions. Docker/VPN operations simulated; real private-file, bcrypt and process-control transitions retain their documented scope. |
| Maintained controls | PASS: script/policy/updater/module controls, ShellCheck and Dockerfile lint. Browser-verdict tests pass 57/57 with the project-pinned Node 22; failed restricted-environment host Node 24 attempt retained privately. |
| Existing installation | Installer refused foreign live containers before creating credentials or changing services. Production remains unchanged. |
| Clean first installation | NOT RUN. Independent Fedora 44 x86-64 clone prepared; inherited VPN-only filter blocked downloads. User approved a trial-only change to public IPv4 with LAN blocking retained; prerequisites are being prepared. |
| Novice trial, real installation/recovery, screenshots and resource measurements | NOT COMPLETE. These require actual observations; no synthetic result fills the blank trial worksheet. |
| Publication | Source published in draft PR #43; protected checks are rerun for the refreshed helper pin. No release, registry upload or merge. |

## Fresh complete scans

Pinned Trivy 0.76.0, database updated 6 November 2026 at 01:07:43Z. Scans run against
verified immutable image exports, with no scanner network or daemon socket.

| Exact artifact | Critical | High | Medium | Low | Unknown | Fixable High/Critical |
|---|---:|---:|---:|---:|---:|---:|
| Candidate Firefox image above | 1 | 122 | 256 | 166 | 12 | 0 |
| VPN `267af9056e264cd1b610847d29515a2af76b526f509a8002e93004e9a0c758a9` | 0 | 0 | 0 | 0 | 1 | 0 |

The scan still reports libxml2 CVE-2026-6653 for the custom Debian package. Its
published vendor patch is locally applied and the isolated tests above pass;
that is distinct from Debian's stable vendor status and from pending real-VPN
candidate acceptance. No suppression or alert dismissal is used.

Compared with 5 November, zlib CVE-2026-76844 adds one High package row. Debian's
[primary record](https://security-tracker.debian.org/tracker/CVE-2026-76844)
describes a gz_write/gzclearerr write-error path and still marks stable vulnerable.
The scanner's webpack title is mismatched metadata; do not use it to dismiss the
zlib finding. Actual consumer/error-path applicability remains pending. Three
Medium FFmpeg package rows for CVE-2026-6385 disappear in the refreshed database;
this is a database delta, not evidence that this patch fixes FFmpeg.

The candidate now has 49 advisory/source groups including the locally patched
critical case and the new zlib case. Remaining advisory disposition stays
**OPEN**. The acceptance that expired 27 October is not renewed by these tests.
Green fixable-only CI is not zero-advisory clearance or a release decision.

The earlier [5 November deployed checkpoint](VALIDATION-2026-11-05.md) remains
history for the currently running installation. This candidate has not replaced it.

## Password helper refresh

The old immutable helper image produced 12 fixable High package rows in the
initial companion workflow. The current official `httpd:2.4-alpine` image is now
pinned to `sha256:d72968666c0a6961b07036d85fc053bc3cf640583cb1ff8360e1617818f164dc`.
The real bcrypt accept/reject contract passes with network disabled and no host
mounts. The exact selected Linux/amd64 artifact scans with zero findings at every
severity using the same fresh database. [Identity and scoped evidence](ci/evidence/login-helper-20261106.json).
Other architectures are not claimed. Failed original workflow reports remain
available; this change fixes the pin rather than bypassing their gate.
