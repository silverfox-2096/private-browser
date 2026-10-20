# Current remediation status and validation plan

Updated 20 October 2026. This is the public current-status register. Dated reports
in [FOLLOW-UP-RESULTS.md](FOLLOW-UP-RESULTS.md) and the README changelog retain
their original scope; their earlier next steps do not supersede this register.

## Current status register

| Package / category | Current state | Next action or closure evidence |
|---|---|---|
| Completed baseline | Explicit Docker DNS, startup/checker fixes and private/local-address policy deployed and published | [DNS evidence](HOST-FORWARDING.md), [policy validation](LOCAL-APP-POLICY.md), [bounded relay closeout](FOLLOW-UP-RESULTS.md#completed-assessment-and-containment), [dated changelog](README.md#changelog). These scoped results do not close R1/R2/R4. |
| R3 — Documentation/status/publication | Source corrections complete in this revision; publication recorded separately | Current introduction, register and historical-report pointers agree. Closure also requires protected PR checks/merge, successful exact-main checks and synchronized local publication snapshots; consult the PR/check history and operator checkpoint for those stages. |
| R1 — Retained advisories / exact deployed artifacts | DONE — assessment and time-bounded operator disposition recorded | [Exact-image assessment](IMAGE-ASSESSMENT.md): complete live-artifact scans, 42 prioritized source/advisory groups, scoped path evidence and named blockers. No supported stable High/Critical fix identified; no suppression or replacement. Operator accepted retention of the assessed exact artifacts until manual reassessment by 27 October 2026, earlier on image/package/consumer/configuration changes, stable fixes or relevant exploit/path evidence. Applicability uncertainties and scanner findings remain visible; no acceptance for future images. |
| R2 — Maintained local-app policy gates | Implemented and installed; live validation passed, protected publication recorded separately | [Trusted policy gate](LOCAL-APP-POLICY.md#maintained-policy-acceptance-gate), Compose/mutation checks, real dual-stack fixture and maintained updater/browser wrapper distinguish policy PASS from browser7/7. Missing protection or evidence cannot PASS. Authorized host-script installation and live recovery passed on 20 October: policy assertions, network4/4, browser7/7, public HTTPS/DNS, authenticated API and viewer login redirect. Exact images, policy/Compose and shared network were preserved; gate cleared. Closure also requires protected checks/merge and snapshots. |
| R4 — Residual actual-boot validation | OPEN — new guarded observer preparation selected; execution needs separate authorization | Reuse [issue #33](https://github.com/silverfox-2096/private-browser/issues/33) after R1/R2 work. Existing collection did not observe a tunnel-absent executed-request window. Design alone does not close validation; operator acceptance of remaining uncertainty must be explicit. |
| Deliberately parked / accepted | Clipboard/private-viewer persistence tests parked; Safe Browsing off accepted | Optional inactive-collector removal and publicity/Projects/Discussions/Releases/Tags remain deferred. Wider forensic, multi-host and public-address relay limits are explicit scope limits, not additional automatic work packages. |

Next: complete R2 protected publication/snapshots, then prepare the new R4 guarded boot observer selected by the operator. No new schedule, live image
replacement, interruption, root installation, collector run or reboot is authorized
by this plan. Material residual-risk decisions belong to the operator.

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

## Separate remaining question: actual host-boot timing

[Issue #33](https://github.com/silverfox-2096/private-browser/issues/33) tracks whether
the guarded browser starts safely during actual laptop boot. Existing startup-guard
and controlled restart tests do not establish an actual boot-time tunnel-absent
window. No new reboot or collector run is requested or scheduled.

If separately authorized, first prepare a concrete experiment with collection ready
before Docker starts. Require a common clock for process/container creation,
firewall/readiness/tunnel transitions and identifiable executed operations during
a tunnel-absent interval, with namespace/physical visibility controls and loss
accounting. If no browser request executes during that interval, do not call the
capture a negative packet-egress test. Review the narrower evidence before deciding
whether another boot experiment is needed.

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
