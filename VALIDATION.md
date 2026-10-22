# Validation at a glance

Recorded 22 October 2026. This is a navigation summary, not a new security audit.
Historical runtime results retain their original dates, artifacts and limits.
Onboarding changes are based on public main `013165caac3a30dccea22db0634138b45ed8f853`.

| Check | Recorded result | Scope and source |
|---|---|---|
| New onboarding regressions | PASS: 40 tests on 22 October | Credential-free local tests, real bcrypt hashing and real process-group interruption/recovery; Docker operations mocked. `python3 ci/test-onboard.py`. No real VPN installation inferred. |
| Actual pinned login helper | PASS, 22 October | Disposable Docker Official Image pinned by digest, synthetic stdin password, network disabled, no host mounts, bcrypt output validated. |
| Existing-installation protection | PASS, 22 October | Guided configure-only setup refused the current production containers before reading credentials or changing services. |
| Maintained script failure paths | PASS: 74 cases on 22 October | Docker/curl fixtures; `bash ci/test-scripts.sh`. |
| Compose/policy contracts | PASS on 22 October | Missing/writable mount mutations and checker controls; `python3 ci/check-policy-compose.py` and `python3 ci/test-local-app-policy.py`. Synthetic tests are not actual packet evidence. |
| Maintainer's deployed runtime | PASS: network4/4, browser7/7 and policy recovery, 22 October | Existing approved deployment, not this onboarding install. [Status register](FOLLOW-UP-PLAN.md#current-status-register), [VPN record](gluetun-patched/README.md). |
| Private/local-app containment | Scoped passing IPv4/IPv6, tunnel-down/restart and browser controls | [Policy evidence and maintained gate](LOCAL-APP-POLICY.md). Public-address remote relays remain outside universal prevention claims. |
| Actual host boot | Bounded guard-barrier finding supported, 21 October | [Boot report](BOOT-VALIDATION.md). Original recorder-wide INCOMPLETE remains; no forced absent-tunnel browser request or universal boot guarantee. |
| Exact deployed VPN vulnerability scan | No Critical/High/Medium/Low; one disclosed UNKNOWN, 22 October | Exact image `sha256:6a6694da23b832fcd6126dda1c513994d4a6fac13a237351a1b25479b3636c13`. [Artifact assessment](IMAGE-ASSESSMENT.md). Not a scan of a future release. |
| Firefox retained findings | 504 observations in 20 October assessment; bounded disposition retained | [Assessment and applicability limits](IMAGE-ASSESSMENT.md). Firefox was not freshly rescanned in the VPN follow-up; green fixable-only CI does not mean zero advisories. |
| Public builds | Consult the exact commit's CI and companion workflows | [Results and access](SECURITY.md#where-to-see-the-results). Builds and running immutable images are separate artifacts. |
| Clean-machine guided real-VPN setup | NOT RUN | Needs a separate provider configuration, clean supported host, measured installation and runtime checks; production credentials must not run concurrently in a fixture. |
| Unfamiliar-user trial | NOT RUN | A person unfamiliar with the repo must complete the documented setup without coaching; record friction and corrections. |
| Windows/macOS/ARM/Desktop/rootless support | NOT VALIDATED for guided setup | Initial target is a local rootful Linux x86-64 engine. |
| Configuration-only visual walkthrough | RECORDED, synthetic discovery/port fixture | [Actual wizard prompts and playback](QUICKSTART.md#visual-walkthrough-and-measured-acceptance); no VPN or browser success inferred. |
| Login/browser screenshots, full walkthrough and install measurements | NOT RECORDED | Browser certificate warning needs human handoff; clean-host measurements remain acceptance tasks. |
| Offline release packaging | PASS: 16 tests on22October | Frozen source archive, immutable image references, complete acceptance receipts, integrity/corruption controls, and resolved Compose equivalence. Fixtures are synthetic; no real release acceptance is inferred. |
| Versioned prebuilt release | NOT PUBLISHED | [Release path](RELEASING.md); source builds remain available. |

The older [verification sample](VERIFY-OUTPUT.md) is preserved. Follow its dates
rather than treating a sample transcript as evidence for a new installation.

## Repeat local onboarding checks

```bash
python3 ci/test-onboard.py
python3 ci/test-release.py
bash ci/test-scripts.sh
python3 ci/check-policy-compose.py
python3 ci/test-local-app-policy.py
shellcheck setup.sh pb launch.sh update.sh verify.sh
```

The onboarding suite requires Python 3.10 or newer on Linux. Its real bcrypt check
runs when host `htpasswd` is installed; otherwise that one case is explicitly
skipped. Fixture WireGuard values are synthetic. No production private key,
Docker socket, image build, VPN interruption or host permission change is needed.

The maintained upstream/runtime suites retain their separate prerequisites. Tests
added to the existing CI job do not replace policy, fingerprint or image scans.
