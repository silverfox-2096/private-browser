# Local application access policy

The browser must not ask a reachable local application to fetch traffic through
that application's separate network. Even normal authenticated fetch/import
features can delegate traffic outside Gluetun. Compose therefore mounts
`local-app-post-rules.txt` read-only at Gluetun's supported `/iptables/post-rules.txt`.
The pinned stable implementation runs these rules before starting its health
server; the browser startup guard waits for that health check.

The rules reject original-direction connections to IPv4 private networks,
carrier-grade NAT, link-local, multicast, unspecified and loopback ranges when
routed outside loopback; and IPv6 unique-local/link-local addresses. They precede
general established and bridge allows, so already-established outgoing local-app
sessions are also blocked. Reply-direction traffic for incoming viewer/API
connections and namespace-local loopback remain available. The VPN transport and
public internet traffic through the tunnel remain under Gluetun's normal firewall.

Local dashboards, media servers and Docker peers will intentionally stop opening
inside Private Browser. Use a separate ordinary browser when you need those apps.
Do not add an outbound-subnet exemption expecting it to override this policy.
Keep the rules mount when updating the stack; removing it removes this boundary.

## Validation

Use a disposable network before rollout. Confirm that both IPv4 and IPv6 local
fixtures work without the rules, fail with them, and that an existing outgoing
connection is rejected. Incoming connections must still receive replies in both
families, and loopback must still work. Check installed kernel rules, not only the
file or startup log. Then, between browsing sessions with maintenance protection,
verify previously reachable host/peer application paths are blocked, public HTTPS
and DNS still work, viewer/API authentication remains enabled, and the rules persist
across both tunnel and container restarts. Repeat the browser checks.

The local test evidence is retained outside this public tree. These checks do not
prove a safe host-boot timing window or every possible forwarding mechanism.

## Recorded local validation — 19 October 2026

Isolated IPv4/IPv6 fixture controls passed before and after policy insertion:
local outgoing requests blocked, incoming replies and loopback preserved. An
already-connected outgoing TCP request was blocked with a matching REJECT counter
increase; the client timed out, rather than reporting a synchronous refusal.

On the authorized live deployment, three previously reachable host/peer service
paths were blocked after deployment, with the tunnel absent, after tunnel restart
and after a full VPN container restart. Host controls still reached all three.
Public HTTPS/DNS and API authentication passed; seven browser checks passed.
The viewer continued to require login over TLS. Images, explicit DNS, startup
guard, immutable image override, shared network and unrelated application
identities were preserved. No actual laptop boot test is claimed.

## Limits and recovery

This policy covers connections to local/private destinations. Public internet
services can still make requests on a user's behalf, including publicly exposed
applications reached at public addresses. Loopback here belongs to the shared
browser/VPN namespace, not to the host. The rules do not sandbox other applications
or route their independent traffic through this VPN.

A supported VPN provider requiring private-address tunnel endpoints would need a
narrow, reviewed transport exception; the current deployment uses a public endpoint.
Do not broadly allow a private subnet to accommodate a provider.

Retain the previous Compose file before deployment. If validation fails, stop the
browser, restore that file and recreate only the VPN/browser services with the same
images; preserve any shared network and other applications. Restoring the prior
configuration also restores its local-app delegation exposure. Never leave the
browser running while deliberately disabling its firewall.
