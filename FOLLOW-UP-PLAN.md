# Remaining validation plan

Updated 19 October 2026 after the completed relay assessment and deployed local-app
restriction. The startup guard, explicit Docker DNS, checker fixes and local-app
policy are deployed. Published dependency maintenance does not replace the
operator's pinned running VPN image.

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
