# Verification and build evidence

Build-only observation, 2026-10-18, public source `c101041` (before the maintenance-gate change): Firefox package `158.0~build2`. BuildKit resolved these linux/amd64 inputs:

- jlesage/baseimage-gui:debian-13-v4.14.0: `sha256:887c603e603eb14f9dc18a0d8076b465a38504da0b57317c1fb402f3bc7ebd05`
- jlesage/firefox:v26.09.1: `sha256:302aa068dcfa46a2d248771c998f67377383554df8940252caef42b99c13eb65`
- debian:13-slim: `sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f`

These are observed platform-manifest digests, not assertions about a newer build.
The Firefox Trivy job now records equivalent evidence for each actual CI build in
its summary. The historical runtime sample below remains dated September 24.

## Sample `verify.sh` run

Recorded 2026-09-24 on the author's machine, with the stack as published in this release (branch `review-4a1`, parent `f0336bc`). By default the script prints no IP address; run it with `SHOW_EXIT_IP=1` to see the exit address on a PASS.

```
verify.sh sha256: 4d9f71da9dc68a0d
Firefox: Mozilla Firefox 156.0.1
Gluetun: qmcgaw/gluetun:v3.41.3@sha256:fa19cc76b2af13d57a8d3dc3066f2ada061b1c761b8aecf989b3877c0486e027
Docker Engine 29.8.1, Compose 5.5.1
```

```
private-browser verify.sh -- 2026-09-24 15:24 UTC

      comparing against this host's current public IPv4 (not printed). If the host
      is itself behind a VPN, set REAL_IP= to your ISP-assigned address instead.
PASS  exit IP differs from the host/REAL_IP address (country=SG)
PASS  exit country = SG (matches expected SG)
PASS  browser DNS points at Gluetun's local DoT resolver (127.0.0.1)
PASS  kill switch: reachable with tunnel up; with it stopped, the request failed
      at the network level (wget exit 4; cause not identified)
      restoring stack...
      stack restored; Firefox reaches https://1.1.1.1 again

ALL AUTOMATED CHECKS PASSED
Still do the MANUAL browser checks: WebRTC (browserleaks.com/webrtc = No Leak)
and DNS leak (dnsleaktest.com extended = your DoT resolver, never your ISP).
```

Exit code: 0 (every check passed).
