# Remaining validation plan

Updated 19 October 2026. This plan separates unverified coverage from demonstrated
faults. The startup guard, Docker DNS fix and checker reliability changes are
deployed. Reviewed module updates are published; the operator's running VPN image
remains pinned. No new bypass is established by the open items below.

## Order of work

| Priority | Question | Next bounded action | Evidence needed to close that specific test |
|---|---|---|---|
|1|Can an actual reachable local service forward a browser request outside the VPN?|Refresh the inventory of host/bridge listeners and peer services. Review only present request-forwarding mechanisms and their access controls. Select a harmless, non-mutating operation if one exists.|Record the concrete route, authorization behavior and operation executed. A rejected config request proves only that route's rejection; simple reachability does not prove forwarding.|
|2|Can a relevant IPv4-facing service regenerate traffic over IPv6?|If priority 1 identifies an applicable forwarding operation, exercise it against a controlled target using unique request identifiers and capture only that transaction.|Show actual request execution, applicable tunnel state, namespace/host egress correlation, a working IPv6 observation control and capture/drop counts. If no applicable operation or IPv6 route exists, record that limitation; do not declare general IPv6 safety.|
|3|Would independent process/socket attribution resolve an uncertain forwarding result?|For a specific transaction, inspect the available process/cgroup/socket information and use existing tracing access if available.|Tie the regenerated socket to the service/process and the test transaction. A cgroup name or unrelated socket listing is insufficient. Retain denied/disappeared-process observations as incomplete.|
|4|Does the guarded browser start safely during actual laptop boot?|First review the remaining timing claim against the isolated startup-guard evidence. If actual boot coverage is still needed, prepare a separate experiment with collection ready before Docker starts.|A common clock for container/process creation, firewall/readiness/tunnel transitions and identifiable executed operations during a tunnel-absent window, with namespace/physical observations, positive controls and loss counts. All-tunnel-present probes do not close this gap.|

## Current work record

The [19 October local forwarding review](FOLLOW-UP-RESULTS.md) records the refreshed
inventory, installed request-path review and seven anonymous configuration-route
rejections with reachability controls. It did not execute a forwarding transaction;
wider relay/IPv6/attribution coverage remains INCOMPLETE in
[issue #32](https://github.com/silverfox-2096/private-browser/issues/32).
The separately authorized boot design is tracked in
[issue #33](https://github.com/silverfox-2096/private-browser/issues/33); no reboot is
scheduled. These records do not close the evidence requirements below.

## First work package: local forwarding review

Start with read-only, sanitized inspection of the current host and shared bridge.
Record service identity, listening address and whether the implementation can
fetch or proxy a supplied destination. Keep private topology and raw evidence out
of the public repository. Do not sweep unrelated ports or collect unrelated traffic.

For each candidate, follow the actual request path through access checks to the
outbound operation. Where permitted, use a harmless controlled destination and a
unique token, with a non-forwarding request as a comparison. Do not retrieve or
reuse another application's credentials merely to make a forwarding test possible.
If an authenticated or state-changing action in another application would be
needed, prepare its exact scope and seek authorization before executing it.

If a path is confirmed, contain that specific mechanism, retain a before/after
reproduction and run recovery checks. Do not redesign the whole shared network
because a local service is merely reachable. If no applicable operation is found,
close only the named service/route review, retain the wider coverage limit, and
state the limits of the inventory.

## Observation rules

A useful negative result requires all of the following:

- The real operation executed, with a unique identifier and known source.
- The relevant tunnel/interface state was observed before and after it.
- Capture filters include that transaction and its applicable address family.
- A positive control proves the observation point can see comparable traffic.
- Packet/drop counts and unsuccessful attempts are retained.

Distinguish encrypted WireGuard transport from direct namespace traffic and
host/peer regeneration. No packets seen without working controls is incomplete.
A failed or unreadable observation is never a pass. Claims stay scoped to tested
services, routes, targets, states and host.

Process attribution is a supporting step, not a reason to install root tracing
software or broaden capture without a concrete unresolved transaction. The earlier
host proc-access denial remains a limit until a fresh observation supersedes it.

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
