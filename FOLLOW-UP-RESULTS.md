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

## Additional exposed-host review — 19 October 2026

A second bounded pass reviewed the remaining wildcard host listeners and selected
installed web-application source/media API metadata. It did not establish a usable
anonymous caller-selected forwarding operation. It does not close issue #32.

| Surface and operation | Evidence | Limit |
|---|---|---|
| Host web server root | Two GET attempts from the VPN namespace timed out; a separate host-local GET returned 200 | No successful browser-namespace HTTP transaction; cause of the timeouts and alternate destinations were not established |
| Host frontend proxy | Health GET returned 200; protected backend configuration GET returned 401; inspected proxy destinations are fixed | Confirms this proxy path preserves the observed rejection, not that all backend routes are safe |
| Host media server | Health GET returned 200; installed API schema and XML documentation inspected | API metadata is supporting evidence, not a source audit of the running binary |
| Two media remote-image GET routes, using an all-zero synthetic item ID | Each returned 401 | No actual remote-image request executed |
| Media URL-based image download | Installed schema declares POST plus elevated authenticated access | Not invoked: it is an authenticated, state-changing operation |
| Synthetic audio/video stream GETs, no credentials and no external destination | Each returned 400 | Validation errors do not prove authorization rejection; playback helper behavior remains unresolved |
| Historical remote-image route without a URL argument | Returned 404 and absent from the current installed schema | Does not test other image/streaming routes or historical vulnerabilities |

The installed media server reports version 12.2.0; its own OpenAPI document has
364 declared operations. Candidate selection inspected 239 signatures mentioning
images, URLs, paths, streams, remote resources or related operations. Forty selected
operations omit a security declaration, including playback/image routes. Omission
is not evidence that they allow anonymous forwarding, and declared security is not
proof of runtime enforcement. No real media identifiers, media content, user list,
API keys or session tokens were requested. Query/body semantics, plugins and all
request-path helpers were not exhaustively audited.

Selected installed host web-application source shows gallery uploads and webhook
configuration requiring content/settings permissions, with webhook dispatch making
server requests to configured destinations. The application access middleware also
permits guest access when public mode is enabled; this review did not read runtime
settings or assume public mode is disabled. Exports have visibility/export-permission
checks; the reviewed contained-HTML image conversion attempts application storage
rather than fetching arbitrary external images. PDF engines, externally fetched
avatars and other downstream request paths remain outside the completed checks.
No exports, webhook changes, uploads, login flow or application configuration changes
were executed.

The enabled web-server virtual-host configuration was unreadable with ordinary
access, and a noninteractive read attempt required unavailable sudo authentication.
It remains unread, with no password requested or access workaround attempted.
Readable module/include directives alone do not establish the full virtual-host
policy. An initial media-schema path returned 404; the installed schema was obtained
at its current OpenAPI path. Upstream source-tag lookups were unavailable and were
not substituted for evidence about the installed binary.

Thirteen anonymous GET attempts in total used unique identifiers and an unprivileged
temporary client in the existing VPN namespace. Responses were reduced to statuses,
redirect paths and bounded error types; bodies were not retained. The two web-server
timeouts remain unsuccessful observations. Known peer/media health routes supplied
reachability controls, and tunnel/local readiness succeeded before and after each
sequence. No arbitrary-port sweep, supplied external destination, real forwarding
transaction, packet capture, IPv6 visibility control or per-socket attribution ran.
Therefore no negative packet-egress or IPv6-regeneration result is claimed.

Before/after checks again verified unchanged live container IDs/start times, images,
Compose/override/guard hashes, shared bridge identity/membership, explicit DNS and
healthy VPN/backend. The optional server stayed absent, maintenance stayed inactive
and both temporary clients were removed. No browser restart or reboot occurred.
The next useful step is a narrowly scoped implementation review of a specific
unresolved request-generating route, before choosing any controlled transaction.

## Preservation and evidence

Verified unchanged live container IDs/start times, immutable images, Compose and
override/guard hashes, shared bridge identity/membership, DNS upstreams and
unrelated backend. VPN/backend remain healthy, optional fingerprint server remains
absent and the maintenance flag remains inactive. The temporary client was removed.
No restart occurred; no disruptive network battery or new full browser battery was
run or claimed. Private inventory, source hashes/extracts, request identifiers,
unsuccessful attempts and before/after evidence stay outside this public repository.
