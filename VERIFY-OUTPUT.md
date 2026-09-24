# Sample `verify.sh` run

Recorded 2026-09-24 on the author's machine, with the stack as published in this release (branch `review-4a`, parent `9d3f8bf`). The host IP is never printed; the exit IP shown is the VPN's.

```
verify.sh sha256: 953e451656e11b44
Firefox: Mozilla Firefox 156.0.1
Gluetun: qmcgaw/gluetun:v3.41.3@sha256:fa19cc76b2af13d57a8d3dc3066f2ada061b1c761b8aecf989b3877c0486e027
Docker Engine 29.8.1, Compose 5.5.1
```

```
private-browser verify.sh -- 2026-09-24 14:43 UTC

      comparing against this host's current public IPv4 (not printed). If the host
      is itself behind a VPN, set REAL_IP= to your ISP-assigned address instead.
PASS  exit IP differs from the host/REAL_IP address (159.26.115.68, country=SG)
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
