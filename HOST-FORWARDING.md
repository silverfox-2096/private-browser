# Docker DNS forwarding: observed path and containment

2026-10-18, one Linux host, Docker Engine 29.9.1, patched stable-source Gluetun
v3.41.3-pb1 and Firefox 158.0. This is an operator-run investigation, not an
independent audit. The Compose change here is a review candidate, not evidence
that an existing deployment has adopted it.

## Observed before change

Normal resolution uses Gluetun at 127.0.0.1, but Docker's 127.0.0.11 resolver is
still listening. Its inherited external server was a host-loopback resolver.
Uniquely named A queries from UID 1000 in the browser network namespace, sent
to Docker DNS over UDP and TCP, reappeared on host loopback and then as plaintext
DNS on the physical uplink outside WireGuard. This also occurred with tun0
absent before and after the negative probes. HTTPS simultaneously failed.

Gluetun's local DNS middleware delegates local names to the original Docker
resolver. Synthetic .lan/.internal queries through 127.0.0.1 also appeared on
host egress; a wget process inside the browser container reproduced the .lan
case. A DNS NXDOMAIN result does not prevent disclosure of the question.
Tested fully qualified public-name queries used Gluetun's normal DoT path.

This is DNS disclosure, not a demonstrated arbitrary HTTPS proxy or browser
JavaScript exploit. Explicit nameserver selection was demonstrated with a
container process; ordinary local-name delegation needs no explicit selection.

## Change and validation

Set `services.gluetun.dns` to `[1.1.1.1, 1.0.0.1]`. Docker creates upstream
sockets in the container network namespace for explicit servers. Gluetun's
firewall and routing then constrain them. Normal local DNS still uses DoT;
queries explicitly sent to Docker DNS use plain DNS inside WireGuard.
Docker service-name resolution remains local. No image change is required.

Controls and observations:

- Two disposable namespaces, each OUTPUT DROP except loopback: inherited host
  DNS answered an external question; explicit upstreams returned SERVFAIL.
- Sequential isolated VPN projects avoided simultaneous use of one WireGuard
  key. With inherited DNS, both UDP and TCP Docker-DNS questions escaped with
  the tunnel up and absent. With explicit upstreams, both worked through tun0
  while up and failed while absent; DNS for example.com returned A records while
  up. UID 1000 HTTPS succeeded up and failed down (wget exit 4).
- Each phase included a uniquely named direct host DNS control. Those questions
  were visible on host egress even when fixed candidate questions were absent.
  Namespace captures showed the candidate requests actually ran and, while up,
  showed Docker's upstream DNS on tun0. Source namespace capture alone was not
  treated as host attribution.
- A deliberately unprotected Docker peer generated five TCP SYNs visible before
  and after host masquerading, including on the physical uplink. Its connection
  timed out; this is a packet visibility control, not successful HTTPS service.
- A further fixed-candidate test covered default-resolver .lan and .internal
  requests with the tunnel up and absent, plus a wget process inside its browser
  container. Namespace captures recorded the requests; host captures contained
  none of those names, while the host DNS control was visible. NXDOMAIN results
  for these names are expected and are not treated as successful web navigation.
- The first candidate recovery probe failed immediately after API restart.
  That attempt was INCOMPLETE. A retained repeat required real HTTPS recovery
  rather than a possibly cached health response and succeeded after two initial
  failed probes. Initial browser recovery checks encountered a remote DNS-test
  service database error; a later restoration run passed all seven checks.

The exact immutable live image, Compose files and shared network were restored
rather than deploying the candidate during the investigation. A deployment needs
its own review and browser closure safeguards. Rollback restores the original
Compose DNS field and the forwarding exposure; do not remove any automatic
immutable-image override.

## Attribution and limits

Question names, IDs, timestamps, namespace capture, host-loopback capture,
physical-interface capture and matching Docker source establish the DNS path
strongly. Direct process-FD/cgroup attribution was unavailable because host proc
access was denied. It is not claimed to have been independently traced by eBPF
or ptrace. Host resolver forwarding also used an unrelated host overlay network;
that overlay is not Gluetun's WireGuard tunnel.

All retained captures reported zero kernel drops. Snap length was 160 bytes;
query fields, relevant headers and unique names were checked, not encrypted
application contents. Captures were narrow and kept private. Coverage is bounded
by the tested names, protocols, states and host. Arbitrary host/bridge services,
IPv6 proxy behavior, every startup instant and a tunnel-absent reboot window
remain outside the completed claim. No new reboot was performed.

Primary references:

- [Docker DNS services](https://docs.docker.com/engine/network/#dns-services)
- [Installed Engine resolver source](https://github.com/moby/moby/blob/b26fb77/daemon/libnetwork/resolver.go),
  `dialExtDNS`: host-loopback dialing versus sandbox ExecFunc.
- [Docker bridge NAT and service reachability](https://docs.docker.com/engine/network/drivers/bridge/)
- [Gluetun exact stable DNS setup](https://github.com/passteque/gluetun/blob/3d1e20c5551e9cae1f9d938dc7b7214a6987f27e/internal/dns/settings.go),
  local-DNS middleware and auto-detected original resolvers.
