# Sample `verify.sh` run

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
