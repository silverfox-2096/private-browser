private-browser verify.sh -- 2026-07-21 17:08 UTC

PASS  exit IP is the VPN's, not the host's (149.34.253.246, country=SG)
PASS  browser DNS points at Gluetun's local DoT resolver (127.0.0.1)
PASS  kill switch: reachable with tunnel up, blocked when stopped (fails closed)
      restoring stack...

ALL AUTOMATED CHECKS PASSED
Still do the MANUAL browser checks: WebRTC (browserleaks.com/webrtc = No Leak)
and DNS leak (dnsleaktest.com extended = your DoT resolver, never your ISP).
