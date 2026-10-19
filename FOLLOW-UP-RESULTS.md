# Local forwarding review — 19 October 2026

## Result and scope

The current read-only review did not establish an applicable anonymous forwarding
operation in the selected shared-peer paths. This closes only that inventory,
source review and anonymous configuration-access check. General local relay,
IPv6 regeneration and independent regenerated-socket attribution remain
**INCOMPLETE**, tracked in [issue #32](https://github.com/silverfox-2096/private-browser/issues/32).
This is not a universal service audit or a new packet-egress result.

## What was inspected

Refreshed host TCP/UDP listeners, the actual shared bridge membership, live VPN
firewall/listeners and host/namespace IPv6 routing. The firewall permits local
bridge traffic; the shared peer has request-generating scanner, HTTP-probe and
status-check functionality. The frontend proxy configuration uses fixed backend
destinations. Other wildcard-bound host applications were inventoried, not
exhaustively audited. Loopback-bound listeners and a relay on another bridge are
not evidence of a reachable arbitrary Internet-forwarding operation.

Reviewed the installed peer's 103 decorated API handlers, route mounting,
authentication dependencies, selected request-generating functions and public-route
exceptions. Scanner triggers, integration tests/imports/configuration and relevant
node mutations require authentication in the reviewed source. The normal auth
dependency accepts a configured service key, valid bearer token or applicable
session, and rejects anonymous access. No credential was retrieved or reused.
Public media serves validated local files; shared documentation/canvas routes
have separate key checks. OIDC uses a configured discovery destination; its login
flow was not exercised. This is a scoped request-path review, not proof that the
application's entire authentication implementation has no defects.

## Executed controls

An unprivileged UID1000 temporary client joined the existing VPN network namespace
using an already-installed immutable tool image. It made nine anonymous GETs with
unique header identifiers, with no cookies, bearer tokens or service keys. Response
bodies were not retained. The installed browser process did not execute these
requests; the client shared its network namespace.

| Operation | Observed result |
|---|---|
| Peer health GET | 200: positive reachability control |
| Public authentication-configuration GET | 200: public-route comparison |
| Seven configuration GETs for scanner, four integrations and two shared views | Each returned 401 |
| VPN interface and local readiness check before/after the sequence | Present/ready |

This extends the earlier single-route rejection observation to seven named route
categories. No scan trigger, authenticated test, configuration mutation or actual
forwarding transaction ran. HTTP statuses establish these routes' access behavior;
they do not prove absence of regenerated network traffic. No packet capture was
needed for this access check, and no packet/drop counts or packet-visibility
controls are claimed.

The first client attempts could not execute because Python/curl were absent from
the selected images. Those attempts remain unsuccessful evidence, separate from
the completed nine-request run. The installed Python tool image then completed the
checks; nothing was installed into the browser or VPN.

## Remaining transaction and boot work

The host has a public IPv6 route while the VPN namespace has no public IPv6 route.
An IPv4-facing service could still regenerate over IPv6. Without an applicable
forwarding operation, no regenerated IPv6 transaction or per-socket attribution
was tested. The next step is to identify a concrete reachable operation and its
access boundary before selecting a controlled destination and narrow observations.
Authenticated or state-changing operations in another application need their exact
scope authorized; do not acquire its credentials merely to make a test possible.

The separate actual host-boot design is tracked in
[issue #33](https://github.com/silverfox-2096/private-browser/issues/33). No collector
was installed and no reboot scheduled. A useful experiment must collect before
Docker starts, correlate process/firewall/tunnel/readiness on a common clock and
distinguish the guard's startup barrier from actual executed browser requests.
If no browser request executes during a tunnel-absent interval, do not call that a
negative packet-egress test. The completed old collector must not be rerun.
Separate authorization and the operational prerequisites in
[FOLLOW-UP-PLAN.md](FOLLOW-UP-PLAN.md) remain required.

## Preservation and evidence

Verified unchanged live container IDs/start times, immutable images, Compose and
override/guard hashes, shared bridge identity/membership, DNS upstreams and
unrelated backend. VPN/backend remain healthy, optional fingerprint server remains
absent and the maintenance flag remains inactive. The temporary client was removed.
No restart occurred; no disruptive network battery or new full browser battery was
run or claimed. Private inventory, source hashes/extracts, request identifiers,
unsuccessful attempts and before/after evidence stay outside this public repository.
