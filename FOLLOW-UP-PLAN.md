# Current remediation status and validation plan

Updated 21 October 2026. This is the public current-status register. Dated reports
in [FOLLOW-UP-RESULTS.md](FOLLOW-UP-RESULTS.md) and the README changelog retain
their original scope; their earlier next steps do not supersede this register.

## Current status register

| Package / category | Current state | Next action or closure evidence |
|---|---|---|
| Completed baseline | Explicit Docker DNS, startup/checker fixes and private/local-address policy deployed and published | [DNS evidence](HOST-FORWARDING.md), [policy validation](LOCAL-APP-POLICY.md), [bounded relay closeout](FOLLOW-UP-RESULTS.md#completed-assessment-and-containment), [dated changelog](README.md#changelog). These scoped results do not close R1/R2/R4. |
| R3 — Documentation/status/publication | DONE | Current entry points were corrected through protected PR #37; exact-main checks and snapshots recorded. Dated results retain their original scope. |
| R1 — Retained advisories / exact deployed artifacts | DONE — time-bounded operator disposition | [Exact-image assessment](IMAGE-ASSESSMENT.md):42 source/advisory groups assessed; current exact artifacts retained by explicit operator decision through manual reassessment by27October2026, earlier on the recorded change/fix/path triggers. Findings and applicability uncertainties remain visible; no acceptance for future images. |
| R2 — Maintained local-app policy gates | DONE — installed/live validated and published | [Trusted policy gate](LOCAL-APP-POLICY.md#maintained-policy-acceptance-gate), mutation/dual-stack controls and wrapper verdicts shipped through protected PR #40. Installed copies match; policy/network4/4/browser7/7/public HTTPS/DNS/viewer/API recovery passed. Exact images/configuration/network preserved, gate cleared, snapshots synchronized. |
| R4 — Residual actual-boot validation | DONE for the selected bounded guard-barrier claim | [Actual boot evidence and recovery](BOOT-VALIDATION.md): process/namespace/policy/readiness/Firefox timeline, supplementary guard-log clock correlation and verified recovery. Original whole-recording analyzer remains INCOMPLETE and its limitations are retained. No absent-tunnel executed-request or universal boot claim. |
| Deliberately parked / accepted | Clipboard/private-viewer persistence tests parked; Safe Browsing off accepted | Optional inactive-collector removal and publicity/Projects/Discussions/Releases/Tags remain deferred. Wider forensic, multi-host and public-address relay limits are explicit scope limits, not additional automatic work packages. |

No R1–R4 remediation action is carried forward from this round. The R1 manual
reassessment date/triggers remain in force; ordinary future maintenance and the
explicit scope limits below do not become newly inferred live work. No new reboot,
image replacement, schedule or collector run is authorized by this register.
Material residual-risk decisions belong to the operator.

Deployment, public publication and post-merge verification are separate stages.
For each package retain exact source/image identities, tests (PASS/FAIL/INCOMPLETE),
failed attempts, rollback/recovery if touched, PR/exact-head checks, merge and
exact-main checks, then synchronize the clean checkout/changelog/snapshots. A
prepared or published change alone is not a completed live validation.

## Completed local relay scope

The [consolidated assessment](FOLLOW-UP-RESULTS.md#completed-assessment-and-containment)
demonstrated normally authenticated fetch capability in an isolated instance of
unchanged deployed code and attributed its requested external SYN outside Gluetun.
Completed external HTTPS timed out; successful IPv6 fetches were loopback-only.
No anonymous arbitrary-destination relay was established in reviewed live paths.
These limits remain part of the result, not new standalone work packages.

The operator then authorized blocking this delegation. The deployed
[local-app policy](LOCAL-APP-POLICY.md) rejects private/local destinations, with
before/after IPv4/IPv6 controls, live tunnel-down/restart tests and browser7/7.
Publicly addressed internet services remain reachable through the VPN. This closes
the configuration-specific review/containment scope in
[issue #32](https://github.com/silverfox-2096/private-browser/issues/32), not every
possible relay vulnerability or future configuration.

## Completed bounded actual-boot question

The separately authorized21October boot supplied a verified guard-barrier
observation, documented in [BOOT-VALIDATION.md](BOOT-VALIDATION.md). The old
collector was not rerun. The new recorder reached its later64MiB cap and its
independent health poll completed just after init; its original INCOMPLETE result
is retained. Additional guard stdout/clock metadata resolves the actual startup
ordering without calling that automated result PASS. Recovery passed and the
viewer/updater were restored. No executed absent-tunnel packet result is claimed.

Any future broader boot experiment is a new assessment decision, with its own
concrete collection/probe controls and separate disruptive authorization. No such
experiment is requested or scheduled by this closeout.

## Operational boundaries

Read-only inventory and documentation need no browser interruption. Before any
VPN/browser stop, restart or replacement, obtain fresh browser-closure confirmation,
hold the updater lock, verify the maintenance gate before checking viewers, and
fail closed on unreadable or nonzero viewer state. Preserve optional-service state,
immutable images/override, the live shared network and unrelated applications.

Use a disposable project for destructive network tests. Never run two VPN
instances with the same WireGuard credentials. Restore the live stack and verify
network/browser recovery before releasing the gate. Raw captures and credentials
remain private.

The old one-shot reboot collector already completed. Do not reinstall it, repeat
it, or ask for a routine reboot to analyze its existing results. Any new actual
host-boot experiment needs a concrete reviewable design and separate operator
authorization; none is requested or scheduled by this plan.

## Separate maintenance decisions

Adopting a new running VPN build is a separate deliberate maintenance window:
review exact build identity, run scans and isolated VPN/browser/firewall checks,
then retain the old image for rollback. Published dependency updates alone do not
change the running immutable image or establish that candidate's VPN runtime
behavior. Current package findings do not require replacing it merely to synchronize
with the build recipe.

Removing the inactive root-owned collector is optional cleanup. Clipboard testing
and publicity remain outside the current work. This plan makes no universal boot,
relay, IPv6 or anonymity guarantee.

## Records

After each work package, record what ran, the result (PASS/FAIL/INCOMPLETE), controls,
failures, exact scope, live recovery if applicable, and the next decision. Publish
only sanitized conclusions. Link new completed evidence from the README's test
coverage and changelog; leave historical test dates intact.

Related: [README](README.md#remaining-work),
[demonstrated Docker DNS path and containment](HOST-FORWARDING.md),
[source-aware VPN maintenance](gluetun-patched/README.md#source-aware-module-maintenance).
